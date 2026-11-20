#!/usr/bin/env bash
# ------------------------------------------------------------------------------
#  Filename: audit-includes.sh
#
#  Purpose:  Reports direct C++ includes that can be removed together, verified in a scratch copy.
#
#  Usage:    ./scripts/audit-includes.sh
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

# --- Guards -------------------------------------------------------------------

if [ -z "${BASH_VERSION:-}" ]; then
  echo "[venimapping] ERROR: audit-includes.sh must be run with Bash." >&2
  exit 1
fi

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  echo "[venimapping] ERROR: execute this file instead of sourcing it:" >&2
  echo "  ${BASH_SOURCE[0]}" >&2
  return 1
fi

set -Eeuo pipefail

# --- Configuration ------------------------------------------------------------

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly script_dir

project_root="$(cd -- "${script_dir}/.." && pwd -P)"
readonly project_root

readonly analyzer="${script_dir}/support/audit_includes.py"
readonly report_dir="${project_root}/build/include-audit"
readonly report="${report_dir}/report.txt"
readonly placeholder="The audit has not finished."

# Only these variables reach the scratch environment, so a project overlay
# sourced in the calling shell cannot leak into the scratch build.
readonly passthrough=(
  HOME USER LOGNAME LANG LC_ALL TERM TMPDIR NO_COLOR GENICAM_GENTL64_PATH CC CXX
)

started="$(date '+%Y-%m-%d %H:%M:%S %z')"
readonly started

# --- Diagnostics --------------------------------------------------------------

if [[ -t 1 && -t 2 && -z "${NO_COLOR:-}" ]]; then
  C_RED=$'\033[31m' C_RESET=$'\033[0m'
else
  C_RED="" C_RESET=""
fi

info() { printf '[venimapping] %s\n' "$*"; }

error() {
  printf '%s[venimapping] ERROR: %s%s\n' "${C_RED}" "$*" "${C_RESET}" >&2
}

step() {
  printf '\n[venimapping] ==> %s\n' "$*"
}

usage() {
  cat <<EOF
Usage: ${BASH_SOURCE[0]}

Finds direct #include directives under src/ that can be removed together. The
audit copies the working tree to a scratch workspace, tries each removal there,
and verifies the combined set with standalone header checks and a clean full
build. Your checkout is not edited.

Report: build/include-audit/report.txt
EOF
}

# The report is replaced first, so a stale success never outlives a newer run.
write_report() {
  local result="$1" stage="$2" detail="$3"

  mkdir -p -- "${report_dir}"
  {
    printf 'VeniMapping include audit\n=========================\n\n'
    printf '  %-14s%s\n' Result "${result}" Started "${started}"
    if [[ -n "${stage}" ]]; then
      printf '  %-14s%s\n' "Failed stage" "${stage}"
    fi
    printf '\n%s\n' "${detail}"
    printf '\nNo removal in this report is verified.\n'
  } >"${report}.tmp"
  mv -f -- "${report}.tmp" "${report}"
}

fail() {
  local stage="$1" message="$2" detail="${3:-}"
  error "${message}"
  write_report FAILED "${stage}" "${message}${detail:+$'\n'${detail}}"
  error "report: ${report#"${project_root}/"}"
  exit 1
}

# --- Preconditions ------------------------------------------------------------

if (( $# > 0 )); then
  case "$1" in
    -h | --help)
      usage
      exit 0
      ;;
  esac
  error "unexpected argument: $1"
  usage >&2
  exit 2
fi

write_report INCOMPLETE "" "${placeholder} If no audit is running, the last run stopped early."

for tool in git python3 tar; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    fail environment "${tool} was not found"
  fi
done

if ! git -C "${project_root}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  fail snapshot "project root is not a Git working tree: ${project_root}"
fi

# --- Scratch workspace --------------------------------------------------------

step "copying the working tree to a scratch workspace"

scratch_parent="$(cd -- "${TMPDIR:-/tmp}" && pwd -P)"
case "${scratch_parent}/" in
  "${project_root}/"*) fail snapshot "TMPDIR is inside the checkout: ${scratch_parent}" ;;
esac

scratch="$(mktemp -d "${scratch_parent}/venimapping-include-audit.XXXXXX")"
readonly scratch
trap 'rm -rf -- "${scratch}"' EXIT

readonly workspace="${scratch}/ws"
mkdir -p -- "${workspace}"

# Tracked and untracked files, without ignored build output. Tracked files
# deleted from the working tree stay deleted in the copy.
if ! git -C "${project_root}" ls-files -z --cached --others --exclude-standard |
  while IFS= read -r -d '' path; do
    if [[ -e "${project_root}/${path}" || -L "${project_root}/${path}" ]]; then
      printf '%s\0' "${path}"
    fi
  done |
  tar -C "${project_root}" --null --no-recursion -T - -cf - |
  tar -C "${workspace}" -xf -; then
  fail snapshot "could not copy the working tree to ${workspace}"
fi
info "scratch workspace: ${workspace}"

# --- Environment --------------------------------------------------------------

step "loading the environment (scripts/env.sh from the snapshot)"

env_args=()
for name in "${passthrough[@]}"; do
  if [[ -n "${!name+x}" ]]; then
    env_args+=("${name}=${!name}")
  fi
done

clean_path=""
IFS=: read -r -a path_entries <<<"${PATH}"
for entry in "${path_entries[@]}"; do
  case "${entry}/" in
    "${project_root}/"*) ;;
    *) clean_path="${clean_path:+${clean_path}:}${entry}" ;;
  esac
done
env_args+=("PATH=${clean_path}")

readonly env_file="${scratch}/environment"
readonly env_log="${scratch}/environment.log"

# Disable nounset while sourcing ROS setup scripts that may read unset variables.
# shellcheck disable=SC2016
if ! (
  cd -- "${workspace}" &&
    env -i "${env_args[@]}" bash --noprofile --norc -c '
      set +u
      source scripts/env.sh && env -0 >"$1"
    ' bash "${env_file}"
) 2>&1 | tee "${env_log}"; then
  fail environment "scripts/env.sh failed in the scratch workspace" \
    "$(tail -n 20 -- "${env_log}")"
fi

mapfile -d '' audit_env <"${env_file}"

# --- Audit --------------------------------------------------------------------

rc=0
(
  cd -- "${workspace}"
  exec env -i "${audit_env[@]}" python3 -B "${analyzer}" \
    --checkout "${project_root}" \
    --workspace "${workspace}" \
    --scratch "${scratch}" \
    --report "${report}" \
    --started "${started}"
) || rc=$?

if (( rc != 0 )) && grep -qF -- "${placeholder}" "${report}"; then
  write_report FAILED audit "audit_includes.py exited with status ${rc} before it wrote a result."
fi

exit "${rc}"
