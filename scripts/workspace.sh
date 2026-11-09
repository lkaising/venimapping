#!/usr/bin/env bash
# ------------------------------------------------------------------------------
#  Filename: workspace.sh
#
#  Purpose:  Builds workspace and IDE config (setup); adds tests and clang-tidy (check).
#
#  Usage:    ./scripts/workspace.sh setup|check
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

# --- Guards -------------------------------------------------------------------

if [ -z "${BASH_VERSION:-}" ]; then
  echo "[venimapping] ERROR: workspace.sh must be run with Bash." >&2
  exit 1
fi

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  echo "[venimapping] ERROR: execute this file instead of sourcing it:" >&2
  echo "  ${BASH_SOURCE[0]}" >&2
  return 1
fi

set -Eeuo pipefail

# --- Configuration ------------------------------------------------------------

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly script_dir

project_root="$(cd -- "${script_dir}/.." && pwd)"
readonly project_root

readonly camera_src="${project_root}/src/venimapping_camera/"
readonly camera_build="${project_root}/build/venimapping_camera"
readonly compile_db="${camera_build}/compile_commands.json"
readonly tidy_report="${camera_build}/tidy/report.txt"
readonly colcon_defaults="${project_root}/.devcontainer/colcon-defaults.yaml"

# --- Diagnostics --------------------------------------------------------------

if [[ -t 1 && -t 2 && -z "${NO_COLOR:-}" ]]; then
  C_RED=$'\033[31m' C_GREEN=$'\033[32m' C_RESET=$'\033[0m'
else
  C_RED="" C_GREEN="" C_RESET=""
fi

info() { printf '[venimapping] %s\n' "$*"; }

error() {
  printf '%s[venimapping] ERROR: %s%s\n' "${C_RED}" "$*" "${C_RESET}" >&2
}

usage() {
  cat <<EOF
Usage: ${BASH_SOURCE[0]} setup|check

  setup  Load the environment, build the workspace, check the compilation
         database and generate the VS Code config. Runs on container create.
  check  Everything in setup, plus colcon test and clang-tidy. This is what
         CI runs.
EOF
}

step() {
  printf '\n[venimapping] ==> %s\n' "$*"
}

# --- Preconditions ------------------------------------------------------------

if (( $# != 1 )); then
  usage >&2
  exit 2
fi

mode="$1"

case "${mode}" in
  setup | check) ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    error "unknown mode: ${mode}"
    usage >&2
    exit 2
    ;;
esac

cd -- "${project_root}"

# --- Environment --------------------------------------------------------------

# Disable nounset while sourcing ROS setup scripts that may read unset variables.
step "loading the environment (scripts/env.sh)"
set +u
if ! source "${script_dir}/env.sh"; then
  set -u
  error "failed to load the environment"
  exit 1
fi
set -u

# --- Build --------------------------------------------------------------------

# Only the image sets COLCON_DEFAULTS_FILE. Native hosts need this fallback for
# the compilation database checked below.
export COLCON_DEFAULTS_FILE="${COLCON_DEFAULTS_FILE:-${colcon_defaults}}"

step "building the workspace (colcon build --symlink-install)"
colcon build --symlink-install

step "checking the compilation database"
if [[ ! -s "${compile_db}" ]]; then
  error "missing or empty compilation database: ${compile_db}"
  exit 1
fi
if ! grep -qF -- "${camera_src}" "${compile_db}"; then
  error "compilation database does not reference ${camera_src}"
  exit 1
fi
info "ok: ${compile_db#"${project_root}/"}"

# --- Tests --------------------------------------------------------------------

if [[ "${mode}" == "check" ]]; then
  step "running the tests (colcon test)"
  colcon test
  colcon test-result --verbose
fi

# --- IDE ----------------------------------------------------------------------

step "generating the VS Code config (scripts/ide.sh)"
"${script_dir}/ide.sh"

# --- clang-tidy ---------------------------------------------------------------

if [[ "${mode}" == "check" ]]; then
  step "running clang-tidy (scripts/tidy.sh check)"
  "${script_dir}/tidy.sh" check

  if ! grep -qF -- "${camera_src}" "${tidy_report}"; then
    error "clang-tidy report does not reference ${camera_src}"
    exit 1
  fi

  # grep: 0 = findings, 1 = no findings, >1 = search failure.
  findings_rc=0
  grep -E ": (warning|error): " "${tidy_report}" || findings_rc=$?
  case "${findings_rc}" in
    0)
      error "clang-tidy reported findings: ${tidy_report#"${project_root}/"}"
      exit 1
      ;;
    1) ;;
    *)
      error "cannot search the clang-tidy report (grep exit ${findings_rc}): ${tidy_report}"
      exit 1
      ;;
  esac
fi

# --- Summary ------------------------------------------------------------------

printf '\n%s[venimapping] workspace %s passed in %ss%s\n' \
  "${C_GREEN}" "${mode}" "${SECONDS}" "${C_RESET}"
