#!/usr/bin/env bash
# ------------------------------------------------------------------------------
#  Filename: clean.sh
#
#  Purpose:  Cleans generated workspace output and VS Code configuration.
#
#  Usage:    ./scripts/clean.sh [-n|--dry-run] [-y|--yes] [--settings]
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

# --- Guards -------------------------------------------------------------------

if [ -z "${BASH_VERSION:-}" ]; then
  echo "[venimapping] ERROR: clean.sh must be run with Bash." >&2
  exit 1
fi

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  echo "[venimapping] ERROR: execute this file instead of sourcing it:" >&2
  echo "  ${BASH_SOURCE[0]}" >&2
  return 1
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "[venimapping] ERROR: clean.sh runs in the dev container or on Linux, not on $(uname -s)." >&2
  echo "  Run it from a terminal inside the dev container." >&2
  exit 1
fi

set -Eeuo pipefail

# --- Configuration ------------------------------------------------------------

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly script_dir

project_root="$(cd -- "${script_dir}/.." && pwd)"
readonly project_root

# Only their contents are removed: in the dev container these folders are
# Docker volume mount points.
readonly output_dirs=(build install log)

readonly vscode_dir="${project_root}/.vscode"
readonly vscode_generated=(
  c_cpp_properties.json ros.env
  c_cpp_properties.json.tmp ros.env.tmp settings.json.tmp
)
# Preserve settings.json by default; it may contain user edits.
readonly vscode_settings="settings.json"

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

rel() {
  printf '%s\n' "${1#"${project_root}/"}"
}

refuse() {
  local line
  for line in "$@"; do
    error "${line}"
  done
  error "nothing was deleted"
  exit 1
}

access_hint() {
  local path="${project_root}/$1"
  printf 'fix it, then rerun: sudo chown -R -- %q %q && chmod -R u+rwX -- %q' \
    "$(id -un):$(id -gn)" "${path}" "${path}"
}

usage() {
  cat <<EOF
Usage: ${BASH_SOURCE[0]} [-n|--dry-run] [-y|--yes] [--settings]

Removes generated build output and VS Code configuration. Run by hand only.

  build/ install/ log/  Their contents are removed and the folders stay (in the
                        dev container they are Docker volume mount points).
                        Symlinks are removed, never followed.
  .vscode/              Generated c_cpp_properties.json, ros.env, and known
                        temporary files. Other files stay; see --settings.

Options:
  -n, --dry-run  Show what would be removed, then exit without deleting.
  -y, --yes      Delete without asking. Required when there is no terminal.
      --settings Also remove .vscode/settings.json, which may contain your
                 own edits.
  -h, --help     Show this help.

Never touched: src/ and .venv/. Docker volumes, their mount points and the
containers are kept; only the contents of build/ install/ log/ are cleaned.
EOF
}

# --- Arguments ----------------------------------------------------------------

dry_run=0
assume_yes=0
with_settings=0

while (( $# > 0 )); do
  case "$1" in
    -n | --dry-run) dry_run=1 ;;
    -y | --yes) assume_yes=1 ;;
    --settings) with_settings=1 ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      error "unknown argument: $1"
      usage >&2
      exit 2
      ;;
  esac
  shift
done

# --- Preflight ----------------------------------------------------------------

# Every target is validated before anything is deleted, and no check follows a
# symlink. The access checks are best effort, not a guard against concurrent
# changes.

clean_dirs=()
vscode_files=()

inspect_output_dir() {
  local dir="$1"
  local path="${project_root}/${dir}"
  local first locked
  local find_rc=0

  if [[ -L "${path}" ]]; then
    refuse "${dir}/ is a symlink; not cleaning through it: ${dir}/ -> $(readlink -- "${path}")"
  fi
  if [[ ! -e "${path}" ]]; then
    return 0
  fi
  if [[ ! -d "${path}" ]]; then
    refuse "${dir} is not a folder: ${path}"
  fi

  if ! first="$(find "${path}" -mindepth 1 -print -quit 2>/dev/null)"; then
    refuse "${dir}/: cannot read the folder (owner $(stat -c '%U:%G' -- "${path}"))" \
      "$(access_hint "${dir}")"
  fi
  if [[ -z "${first}" ]]; then
    return 0
  fi

  # Removing an entry needs write access to its folder, and reaching it needs
  # read and search access to every folder above it.
  locked="$(
    find "${path}" -type d \( ! -writable -o ! -readable -o ! -executable \) \
      -print -quit 2>/dev/null
  )" || find_rc=$?
  if [[ -n "${locked}" ]]; then
    refuse "${dir}/: no read, write or search access to $(rel "${locked}")/ (owner $(stat -c '%U:%G' -- "${locked}"))" \
      "$(access_hint "${dir}")"
  fi
  if (( find_rc != 0 )); then
    refuse "${dir}/: cannot inspect the contents (find exit ${find_rc})" \
      "$(access_hint "${dir}")"
  fi

  clean_dirs+=("${dir}")
}

inspect_vscode() {
  local name file
  local names=("${vscode_generated[@]}")

  if [[ -L "${vscode_dir}" ]]; then
    refuse ".vscode/ is a symlink; not cleaning through it: .vscode/ -> $(readlink -- "${vscode_dir}")"
  fi
  if [[ ! -e "${vscode_dir}" ]]; then
    return 0
  fi
  if [[ ! -d "${vscode_dir}" ]]; then
    refuse ".vscode is not a folder: ${vscode_dir}"
  fi
  if [[ ! -x "${vscode_dir}" ]]; then
    refuse ".vscode/: no search access, so its files cannot be checked (owner $(stat -c '%U:%G' -- "${vscode_dir}"))" \
      "$(access_hint .vscode)"
  fi

  if (( with_settings )); then
    names+=("${vscode_settings}")
  fi
  for name in "${names[@]}"; do
    file="${vscode_dir}/${name}"
    if [[ -L "${file}" || -f "${file}" ]]; then
      vscode_files+=("${file}")
    elif [[ -e "${file}" ]]; then
      refuse ".vscode/${name} is not a file; not removing it (move it away if it is not needed)"
    fi
  done

  if (( ${#vscode_files[@]} > 0 )) && [[ ! -w "${vscode_dir}" ]]; then
    refuse ".vscode/: no write access to remove its generated files (owner $(stat -c '%U:%G' -- "${vscode_dir}"))" \
      "$(access_hint .vscode)"
  fi
}

if [[ ! -d "${project_root}/src" || ! -f "${project_root}/scripts/workspace.sh" ]]; then
  refuse "${project_root} does not look like the venimapping project root"
fi

cd -- "${project_root}"

for dir in "${output_dirs[@]}"; do
  inspect_output_dir "${dir}"
done
inspect_vscode

if (( ${#clean_dirs[@]} == 0 && ${#vscode_files[@]} == 0 )); then
  info "nothing to clean in ${project_root}"
  exit 0
fi

info "will clean ${project_root}:"
for dir in "${clean_dirs[@]}"; do
  info "  ${dir}/ (contents)"
done
for file in "${vscode_files[@]}"; do
  info "  $(rel "${file}")"
done
if (( ! with_settings )) && [[ -e "${vscode_dir}/${vscode_settings}" ]]; then
  info "keeping .vscode/${vscode_settings} (pass --settings to remove it)"
fi

if (( dry_run )); then
  info "dry run: nothing was deleted"
  exit 0
fi

# --- Confirmation -------------------------------------------------------------

if (( ! assume_yes )); then
  if [[ ! -t 0 ]]; then
    refuse "no terminal to confirm on; rerun with --yes (or --dry-run to preview)"
  fi
  answer=""
  read -r -p "[venimapping] delete the above? [y/N] " answer || true
  case "${answer}" in
    y | Y | yes | Yes | YES) ;;
    *)
      info "aborted; nothing was deleted"
      exit 1
      ;;
  esac
fi

# --- Clean --------------------------------------------------------------------

# find without -L removes symlinks themselves and never touches their targets.
rc=0
for dir in "${clean_dirs[@]}"; do
  if find "${project_root}/${dir}" -mindepth 1 -delete; then
    info "emptied ${dir}/"
  else
    error "could not remove everything in ${dir}/"
    rc=1
  fi
done

for file in "${vscode_files[@]}"; do
  if rm -f -- "${file}"; then
    info "removed $(rel "${file}")"
  else
    error "could not remove $(rel "${file}")"
    rc=1
  fi
done

if (( ${#vscode_files[@]} > 0 )) && rmdir -- "${vscode_dir}" 2>/dev/null; then
  info "removed the empty .vscode/"
fi

if (( rc != 0 )); then
  error "clean incomplete: some files may already be deleted; fix the errors above and rerun"
  exit 1
fi

# --- Summary ------------------------------------------------------------------

printf '\n%s[venimapping] clean finished in %ss%s\n' "${C_GREEN}" "${SECONDS}" "${C_RESET}"
