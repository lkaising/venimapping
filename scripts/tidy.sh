#!/usr/bin/env bash
# ------------------------------------------------------------------------------
#  Filename: tidy.sh
#
#  Purpose:  Runs clang-tidy 20 for venimapping_camera and applies optional automatic fixes.
#
#  Usage:    scripts/tidy.sh [check|fix]
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

# --- Guards -------------------------------------------------------------------

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

readonly build_dir="${project_root}/build/venimapping_camera"
readonly output_dir="${build_dir}/tidy"
readonly report="${output_dir}/report.txt"
readonly fixes="${output_dir}/fixes.yaml"

readonly run_clang_tidy="run-clang-tidy"
readonly clang_tidy="/usr/bin/clang-tidy-20"
readonly apply_replacements="/usr/bin/clang-apply-replacements-20"
readonly header_filter='venimapping_camera'

# --- Diagnostics --------------------------------------------------------------

error() {
  printf '[venimapping] ERROR: %s\n' "$*" >&2
}

usage() {
  cat <<EOF
Usage: ${BASH_SOURCE[0]} [check|fix]

  check  Run clang-tidy and export its report and suggested fixes (default).
  fix    Regenerate the fixes, apply every available fix-it, then check again.
EOF
}

print_summary() {
  local findings

  findings="$(
    grep -E '\[[a-z0-9,.-]+\]$' "${report}" |
      sort -u |
      grep -oE '\[[a-z0-9,.-]+\]$' |
      sort |
      uniq -c |
      sort -rn || true
  )"

  if [[ -n "${findings}" ]]; then
    printf '\n[venimapping] findings by check:\n%s\n' "${findings}"
  else
    printf '\n[venimapping] no findings\n'
  fi

  printf '\n[venimapping] report: %s\n' "${report#"${project_root}/"}"
  printf '[venimapping] fixes: %s\n' "${fixes#"${project_root}/"}"
}

# --- Preconditions ------------------------------------------------------------

mode="${1:-check}"

if (( $# > 1 )); then
  usage >&2
  exit 2
fi

case "${mode}" in
  check | fix) ;;
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

if [[ ! -f "${build_dir}/compile_commands.json" ]]; then
  error "missing compilation database: ${build_dir}/compile_commands.json"
  error "build venimapping_camera before running this script"
  exit 1
fi

if ! command -v "${run_clang_tidy}" >/dev/null 2>&1; then
  error "${run_clang_tidy} was not found"
  exit 1
fi

if [[ ! -x "${clang_tidy}" ]]; then
  error "clang-tidy 20 was not found: ${clang_tidy}"
  exit 1
fi

if [[ "${mode}" == "fix" && ! -x "${apply_replacements}" ]]; then
  error "clang-apply-replacements 20 was not found: ${apply_replacements}"
  exit 1
fi

if [[ "${mode}" == "fix" && ! -f "${project_root}/.clang-format" ]]; then
  error "missing formatting configuration: ${project_root}/.clang-format"
  exit 1
fi

if [[ "${mode}" == "fix" ]]; then
  if ! git -C "${project_root}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    error "project root is not a Git working tree: ${project_root}"
    exit 1
  fi

  worktree_status="$(git -C "${project_root}" status --porcelain)"

  if [[ -n "${worktree_status}" ]]; then
    error "working tree is not clean; commit or stash changes before 'fix'"
    exit 1
  fi
fi

mkdir -p -- "${output_dir}"

# --- Analysis -----------------------------------------------------------------

run_tidy() {
  local action="$1"

  printf '[venimapping] %s\n' "${action}"
  rm -f -- "${fixes}"

  if ! "${run_clang_tidy}" \
    -quiet \
    -clang-tidy-binary "${clang_tidy}" \
    "-header-filter=${header_filter}" \
    -p "${build_dir}" \
    -j"$(nproc)" \
    -export-fixes "${fixes}" \
    >"${report}" 2>&1; then
    error "clang-tidy failed"
    error "see ${report#"${project_root}/"} for details"
    return 1
  fi

  print_summary
}

cd -- "${project_root}"

if ! run_tidy "running clang-tidy..."; then
  exit 1
fi

if [[ "${mode}" == "check" ]]; then
  exit 0
fi

if [[ ! -s "${fixes}" ]]; then
  printf '\n[venimapping] no automatic fixes to apply\n'
  exit 0
fi

# --- Automatic fixes ----------------------------------------------------------

printf '\n[venimapping] applying available automatic fixes...\n'
if ! "${apply_replacements}" \
  -format \
  -style=file \
  "${output_dir}" \
  >>"${report}" 2>&1; then
  error "automatic fix application failed"
  error "see ${report#"${project_root}/"} for details"
  exit 1
fi

printf '\n'
if ! run_tidy "rechecking the modified source..."; then
  exit 1
fi

printf '\n[venimapping] automatic fixes applied; review the changes with git diff\n'
