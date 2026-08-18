#!/usr/bin/env bash
# ------------------------------------------------------------------------------
#  Filename: ide.sh
#
#  Purpose:  Creates VS Code config and merges compilation databases for a built workspace.
#
#  Usage:    ./scripts/ide.sh
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

VENIMAPPING_WS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENIMAPPING_PACKAGES=(
  venimapping_bringup venimapping_camera
)
VENIMAPPING_UPSTREAM_PREFIXES=(
  "${HOME:-/nonexistent}/workspace/upstream/vimbax-ros2-driver/install"
  "${HOME:-/nonexistent}/workspace/upstream/ros2-jazzy/install"
)

IDE_CONFIG_NAME="Linux (venimapping)"
IDE_CPP_STANDARD="c++23"
IDE_COMPILER_PATH="/usr/bin/c++"
IDE_PYTHON_PATH="/usr/bin/python3"

IDE_ROS_ENV_KEYS=(
  PYTHONPATH LD_LIBRARY_PATH AMENT_PREFIX_PATH
  ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION
  ROS_AUTOMATIC_DISCOVERY_RANGE RMW_IMPLEMENTATION
)
IDE_ROS_ENV_PATH_KEYS=(
  PYTHONPATH LD_LIBRARY_PATH AMENT_PREFIX_PATH
)

IDE_VSCODE_DIR="${VENIMAPPING_WS}/.vscode"
IDE_COMPILE_DB="${VENIMAPPING_WS}/build/compile_commands.json"
IDE_CPP_PROPERTIES="${IDE_VSCODE_DIR}/c_cpp_properties.json"
IDE_ROS_ENV="${IDE_VSCODE_DIR}/ros.env"
IDE_SETTINGS="${IDE_VSCODE_DIR}/settings.json"

# --- Diagnostics --------------------------------------------------------------

if [[ -t 1 && -t 2 && -z "${NO_COLOR:-}" ]]; then
  C_YELLOW=$'\033[33m' C_RED=$'\033[31m' C_GREEN=$'\033[32m' C_RESET=$'\033[0m'
else
  C_YELLOW="" C_RED="" C_GREEN="" C_RESET=""
fi

info() { printf '[venimapping] %s\n' "$*"; }

warn() {
  printf '%s[venimapping] WARN: %s%s\n' "${C_YELLOW}" "$*" "${C_RESET}" >&2
}

error() {
  printf '%s[venimapping] ERROR: %s%s\n' "${C_RED}" "$*" "${C_RESET}" >&2
}

ide_rel() {
  printf '%s\n' "${1#"${VENIMAPPING_WS}"/}"
}

ide_commit() {
  if mv -f "$1" "$2"; then
    return 0
  fi
  rm -f "$1"
  warn "cannot write $(ide_rel "$2")"
  return 1
}

# --- Preconditions ------------------------------------------------------------

ide_preflight() {
  local rc=0
  if [[ ! -d "${VENIMAPPING_WS}/build" ]]; then
    error "missing ${VENIMAPPING_WS}/build"
    rc=1
  fi
  if [[ ! -f "${VENIMAPPING_WS}/install/setup.bash" ]]; then
    error "missing ${VENIMAPPING_WS}/install/setup.bash"
    rc=1
  fi
  if [[ ! -x "${IDE_COMPILER_PATH}" ]]; then
    error "missing C++ compiler ${IDE_COMPILER_PATH}"
    rc=1
  fi
  if [[ ! -x "${IDE_PYTHON_PATH}" ]]; then
    error "missing ${IDE_PYTHON_PATH}; required to write the JSON artifacts"
    rc=1
  fi
  if [[ $rc -ne 0 ]]; then
    error "this script configures an already-built workspace; build it first"
  fi
  return "$rc"
}

# --- C++: compilation database and c_cpp_properties.json ----------------------

# Merge build/<pkg>/compile_commands.json for every package into one
# workspace-level database. colcon-cmake writes its own merged file at the
# same path, but only when it decides the file is stale; this rewrite is
# unconditional and preserves VENIMAPPING_PACKAGES order, so repeated runs
# produce a byte-identical file. Warns and returns 1 when nothing could be
# merged.
ide_merge_compile_commands() {
  local tmp pkg part
  local -a parts=()
  for pkg in "${VENIMAPPING_PACKAGES[@]}"; do
    part="${VENIMAPPING_WS}/build/${pkg}/compile_commands.json"
    if [[ -f "$part" ]]; then
      parts+=("$part")
    fi
  done
  if [[ ${#parts[@]} -eq 0 ]]; then
    warn "no per-package compile_commands.json under build/;" \
      "leaving $(ide_rel "${IDE_COMPILE_DB}") alone"
    return 1
  fi
  tmp="${IDE_COMPILE_DB}.tmp"
  if ! printf '%s\n' "${parts[@]}" | "${IDE_PYTHON_PATH}" -c '
import json, sys

entries = []
for path in sys.stdin.read().splitlines():
    if not path:
        continue
    with open(path) as handle:
        data = json.load(handle)
    if isinstance(data, list):
        entries.extend(data)
with open(sys.argv[1], "w") as handle:
    json.dump(entries, handle, indent=2)
    handle.write("\n")
' "$tmp" 2>/dev/null; then
    rm -f "$tmp"
    warn "cannot merge compilation databases into $(ide_rel "${IDE_COMPILE_DB}")"
    return 1
  fi
  ide_commit "$tmp" "${IDE_COMPILE_DB}" || return 1
  info "merged ${#parts[@]} compilation database(s) into $(ide_rel "${IDE_COMPILE_DB}")"
  return 0
}

# Echo, one per line, the header search directories under PREFIX, covering
# both colcon layouts: merged (PREFIX/include) and isolated
# (PREFIX/<pkg>/include). ROS 2 Jazzy nests a package's headers one level
# deeper again -- install/rclcpp/include/rclcpp/rclcpp/rclcpp.hpp -- and it
# is the *inner* directory that the real compile line puts on -isystem, so
# each nested child is emitted alongside its parent.
ide_prefix_include_dirs() {
  local prefix=$1
  local dir nested
  if [[ ! -d "$prefix" ]]; then
    return 0
  fi
  if [[ -d "$prefix/include" ]]; then
    printf '%s\n' "$prefix/include"
    for nested in "$prefix/include"/*/; do
      if [[ -d "$nested" ]]; then
        printf '%s\n' "${nested%/}"
      fi
    done
  fi
  for dir in "$prefix"/*/include; do
    if [[ ! -d "$dir" ]]; then
      continue
    fi
    printf '%s\n' "$dir"
    for nested in "$dir"/*/; do
      if [[ -d "$nested" ]]; then
        printf '%s\n' "${nested%/}"
      fi
    done
  done
  return 0
}

# Echo the fallback includePath, one entry per line, in the same order the
# compiler sees headers: project sources first, then the project's own
# installed headers, then the driver overlay, then the Jazzy underlay.
#
# The full driver and Jazzy header indexes are intentional: packages beyond
# the current compilation database are included so standalone and generated
# headers remain resolvable and navigable in VS Code.
#
# The Vimba X SDK is deliberately absent: nothing here compiles against it
# directly, and the driver overlay vendors the VmbC headers it was built
# with, so adding the SDK would let IntelliSense resolve against a different
# version than the compiler uses.
ide_include_dirs() {
  local prefix
  if [[ -d "${VENIMAPPING_WS}/src" ]]; then
    printf '%s\n' "${VENIMAPPING_WS}/src/**"
  fi
  ide_prefix_include_dirs "${VENIMAPPING_WS}/install"
  for prefix in "${VENIMAPPING_UPSTREAM_PREFIXES[@]}"; do
    ide_prefix_include_dirs "$prefix"
  done
  return 0
}

# Overwrite .vscode/c_cpp_properties.json from the current build state.
ide_write_cpp_properties() {
  local tmp
  tmp="${IDE_CPP_PROPERTIES}.tmp"
  if ! ide_include_dirs | env \
    IDE_NAME="${IDE_CONFIG_NAME}" \
    IDE_COMPILER="${IDE_COMPILER_PATH}" \
    IDE_CPPSTD="${IDE_CPP_STANDARD}" \
    IDE_DB="${IDE_COMPILE_DB}" \
    "${IDE_PYTHON_PATH}" -c '
import json, os, sys

seen = set()
includes = []
for line in sys.stdin.read().splitlines():
    if line and line not in seen:
        seen.add(line)
        includes.append(line)
doc = {
    "configurations": [
        {
            "name": os.environ["IDE_NAME"],
            "compilerPath": os.environ["IDE_COMPILER"],
            "cppStandard": os.environ["IDE_CPPSTD"],
            "compileCommands": os.environ["IDE_DB"],
            "includePath": includes,
        }
    ],
    "version": 4,
}
with open(sys.argv[1], "w") as handle:
    json.dump(doc, handle, indent=4)
    handle.write("\n")
' "$tmp" 2>/dev/null; then
    rm -f "$tmp"
    warn "cannot generate $(ide_rel "${IDE_CPP_PROPERTIES}")"
    return 1
  fi
  ide_commit "$tmp" "${IDE_CPP_PROPERTIES}" || return 1
  info "wrote $(ide_rel "${IDE_CPP_PROPERTIES}") (compiler ${IDE_COMPILER_PATH})"
  return 0
}

# --- ROS/Python: ros.env and settings.json ------------------------------------

# Echo the ros.env variables as NAME=VALUE lines, by sourcing the built
# overlay's setup.bash. Sourcing the overlay is enough on its own: colcon
# hardcodes the parent prefixes into install/setup.sh, so the Jazzy -> driver
# -> project chain is walked for us. RMW_IMPLEMENTATION is pinned to
# CycloneDDS inside the capture when the ament index carries the package.
#
# The subshell is started with `env -i` and a minimal allowlist so that a
# PYTHONPATH or LD_LIBRARY_PATH already set in the caller's shell cannot
# leak into the snapshot. `bash -c` is non-login on purpose: a login shell
# would also source /etc/profile.d/VimbaX_GenTL_Path_64bit.sh and put SDK
# paths in the capture.
#
# Warns and returns 1 when setup.bash fails to source.
ide_capture_overlay_env() {
  local setup="${VENIMAPPING_WS}/install/setup.bash"
  local captured rc=0
  # shellcheck disable=SC2016  # $1/$@ must expand in the sanitized subshell
  captured=$(env -i \
    HOME="${HOME:-/}" \
    PATH=/usr/local/bin:/usr/bin:/bin \
    LC_ALL=C.UTF-8 \
    bash -c '
      source "$1" >/dev/null 2>&1 || exit 90
      shift
      if [ -z "${RMW_IMPLEMENTATION-}" ]; then
        ifs_save=$IFS
        IFS=:
        set -f
        for prefix in ${AMENT_PREFIX_PATH-}; do
          if [ -n "$prefix" ] &&
            [ -e "$prefix/share/ament_index/resource_index/packages/rmw_cyclonedds_cpp" ]; then
            export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
            break
          fi
        done
        set +f
        IFS=$ifs_save
      fi
      for name in "$@"; do
        printf "%s=%s\n" "$name" "${!name-}"
      done
    ' ide-capture "$setup" "${IDE_ROS_ENV_KEYS[@]}") || rc=$?
  if [[ $rc -ne 0 ]]; then
    warn "cannot source $(ide_rel "$setup") (rc=$rc); leaving the ROS environment file alone"
    return 1
  fi
  printf '%s\n' "$captured"
  return 0
}

# Echo one colon-separated path list, filtered: duplicates dropped first-wins
# and entries that no longer exist dropped entirely.
#
# The sourced order is preserved, never sorted -- it is what puts an overlay
# ahead of its underlay, so a package built in both resolves to the overlay
# copy. Symlinks are also left alone: the workspaces are built with
# --symlink-install, and resolving them would collapse the layout this is
# meant to record.
ide_filter_path_list() {
  local rest=$1
  local entry out=""
  local -A seen=()
  local -a kept=()
  while [[ -n "$rest" ]]; do
    entry=${rest%%:*}
    if [[ "$entry" == "$rest" ]]; then
      rest=""
    else
      rest=${rest#*:}
    fi
    if [[ -z "$entry" || -n "${seen[$entry]:-}" ]]; then
      continue
    fi
    seen[$entry]=1
    if [[ ! -e "$entry" ]]; then
      continue
    fi
    kept+=("$entry")
  done
  if [[ ${#kept[@]} -gt 0 ]]; then
    printf -v out '%s:' "${kept[@]}"
    out=${out%:}
  fi
  printf '%s\n' "$out"
  return 0
}

# Overwrite .vscode/ros.env from the environment the built overlay exports.
# The whole file is replaced every time; no manual content is preserved, and
# nothing varying (no timestamp) is written, so repeated runs against an
# unchanged workspace produce a byte-identical file. Warns and returns 1
# without touching any existing file when the environment cannot be captured
# or carries no usable PYTHONPATH.
ide_write_ros_env() {
  local tmp captured line key
  captured=$(ide_capture_overlay_env) || return 1
  # Parsed line by line and matched against the known key set; lines no key
  # claims are dropped.
  local -A values=()
  while IFS= read -r line; do
    key=${line%%=*}
    case " ${IDE_ROS_ENV_KEYS[*]} " in
      *" $key "*) values[$key]=${line#*=} ;;
    esac
  done <<<"$captured"
  for key in "${IDE_ROS_ENV_PATH_KEYS[@]}"; do
    values[$key]=$(ide_filter_path_list "${values[$key]:-}")
  done
  if [[ -z "${values[PYTHONPATH]:-}" ]]; then
    warn "sourcing the overlay exported no usable PYTHONPATH; leaving $(ide_rel "${IDE_ROS_ENV}") alone"
    return 1
  fi
  tmp="${IDE_ROS_ENV}.tmp"
  # `|| { ... }` instead of `if ! { ... }`: negating a brace group swallows
  # the exit status of a failed redirection, so an unwritable .vscode/ would
  # sail on to the rename below and misreport the failure.
  {
    printf '# Generated by scripts/ide.sh; rewritten on every run. Manual edits are lost.\n'
    printf '# A snapshot of what install/setup.bash exports, read by VS Code through\n'
    printf '# python.envFile. PATH is deliberately absent, so there is no ros2 CLI here.\n'
    for key in "${IDE_ROS_ENV_KEYS[@]}"; do
      if [[ -n "${values[$key]:-}" ]]; then
        printf '%s=%s\n' "$key" "${values[$key]}"
      fi
    done
  } >"$tmp" 2>/dev/null || {
    rm -f "$tmp"
    warn "cannot generate $(ide_rel "${IDE_ROS_ENV}")"
    return 1
  }
  ide_commit "$tmp" "${IDE_ROS_ENV}" || return 1
  local entries
  entries=$(awk -F: '/^PYTHONPATH=/ {print NF; exit}' "${IDE_ROS_ENV}") \
    || entries=""
  info "wrote $(ide_rel "${IDE_ROS_ENV}") (${entries:-0} PYTHONPATH entries)"
  return 0
}

# Create .vscode/settings.json with the C++ formatter keys and the two keys
# that point VS Code at the interpreter and at ros.env -- but only when the
# file does not exist. An existing settings.json is never parsed, merged, or
# rewritten: it is the user's file, and every key is static, so there is
# nothing to keep in sync between runs. The existence probe below is a plain
# text search for the key names, not a parse; it never edits the file, only
# points out when keys are missing. The C++ style policy itself lives in the
# committed .clang-format, which this script never generates or touches.
ide_write_settings() {
  local tmp key
  if [[ ! -f "${VENIMAPPING_WS}/.clang-format" ]]; then
    warn "missing .clang-format at the workspace root; VS Code C++ formatting" \
      "will error until it is committed"
  fi
  if [[ ! -f "${VENIMAPPING_WS}/.clang-tidy" ]]; then
    warn "missing .clang-tidy at the workspace root; VS Code C++ analysis" \
      "will not follow the project policy until it is committed"
  fi
  if [[ -e "${IDE_SETTINGS}" ]]; then
    local -a missing=()
    for key in C_Cpp.formatting C_Cpp.codeAnalysis.clangTidy.enabled \
      editor.defaultFormatter python.defaultInterpreterPath python.envFile; do
      if ! grep -qF -- "\"${key}\"" "${IDE_SETTINGS}" 2>/dev/null; then
        missing+=("$key")
      fi
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
      info "$(ide_rel "${IDE_SETTINGS}") already configures the C++ formatter and Python environment; left untouched"
    else
      warn "$(ide_rel "${IDE_SETTINGS}") exists; this script never edits it --"
      warn "missing keys: ${missing[*]}"
      warn "delete the file and rerun scripts/ide.sh to regenerate it"
    fi
    return 0
  fi
  tmp="${IDE_SETTINGS}.tmp"
  # shellcheck disable=SC2016  # ${workspaceFolder} is resolved by VS Code
  if ! env IDE_PY="${IDE_PYTHON_PATH}" "${IDE_PYTHON_PATH}" -c '
import json, os, sys

doc = {
    "C_Cpp.formatting": "clangFormat",
    "C_Cpp.clang_format_style": "file",
    "C_Cpp.clang_format_fallbackStyle": "none",
    "C_Cpp.codeAnalysis.clangTidy.enabled": True,
    "[cpp]": {
        "editor.defaultFormatter": "ms-vscode.cpptools",
        "editor.detectIndentation": False,
        "editor.formatOnSave": True,
        "editor.insertSpaces": True,
        "editor.rulers": [100],
        "editor.tabSize": 2,
    },
    "python.defaultInterpreterPath": os.environ["IDE_PY"],
    "python.envFile": "${workspaceFolder}/.vscode/ros.env",
}
text = json.dumps(doc, indent=4)
# json.dumps has no inline-array form; the ruler list stays on one line.
text = text.replace("[\n            100\n        ]", "[100]")
with open(sys.argv[1], "w") as handle:
    handle.write(text)
    handle.write("\n")
' "$tmp" 2>/dev/null; then
    rm -f "$tmp"
    warn "cannot generate $(ide_rel "${IDE_SETTINGS}")"
    return 1
  fi
  ide_commit "$tmp" "${IDE_SETTINGS}" || return 1
  info "wrote $(ide_rel "${IDE_SETTINGS}") (C++ format-on-save; interpreter ${IDE_PYTHON_PATH})"
  return 0
}

# --- Entry point --------------------------------------------------------------

main() {
  ide_preflight || exit 1
  local rc=0 db=ok cpp=ok rosenv=ok settings=ok summary
  ide_merge_compile_commands || { db=failed; rc=1; }
  # .vscode/ is created once for the three writers below. The compilation
  # database lives under build/ and must stay regenerable even when the
  # directory cannot be created.
  if mkdir -p "${IDE_VSCODE_DIR}"; then
    ide_write_cpp_properties || { cpp=failed; rc=1; }
    ide_write_ros_env || { rosenv=failed; rc=1; }
    ide_write_settings || { settings=failed; rc=1; }
  else
    warn "cannot create $(ide_rel "${IDE_VSCODE_DIR}")"
    cpp=failed rosenv=failed settings=failed rc=1
  fi
  printf -v summary 'compile-db=%s cpp-properties=%s ros-env=%s settings=%s' \
    "$db" "$cpp" "$rosenv" "$settings"
  if [[ $rc -eq 0 ]]; then
    printf '%s[venimapping] %s%s\n' "${C_GREEN}" "$summary" "${C_RESET}"
  else
    printf '%s[venimapping] %s%s\n' "${C_RED}" "$summary" "${C_RESET}" >&2
  fi
  exit "$rc"
}

main "$@"
