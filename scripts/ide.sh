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

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
  echo "[venimapping] ERROR: execute this file instead of sourcing it:" >&2
  echo "  ${BASH_SOURCE[0]}" >&2
  return 1
fi

set -Eeuo pipefail

# --- Configuration ------------------------------------------------------------

VENIMAPPING_WS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# Ordered: venimapping_camera first -- the only package that compiles C++, so
# compiler detection must hit its CMake cache; venimapping_bringup is
# LANGUAGES NONE and contributes no compilation database and no CXX cache
# entries.
VENIMAPPING_PACKAGES=(venimapping_camera venimapping_bringup)

# Fallback header prefixes beyond the project's own install/, in the order
# the compiler resolves them: the driver overlay, then the Jazzy underlay.
VENIMAPPING_UPSTREAM_PREFIXES=(
  "${HOME:-/nonexistent}/workspace/upstream/vimbax-ros2-driver/install"
  "${HOME:-/nonexistent}/workspace/upstream/ros2-jazzy/install"
)

# Shown in the VS Code configuration picker, so the file is visibly generated.
IDE_CONFIG_NAME="Linux (venimapping)"
IDE_GENERATED_NOTE="GENERATED FILE -- owned by scripts/ide.sh and rewritten on every run. Manual edits are lost; change the generator instead."

# venimapping_camera compiles with cxx_std_23 (target_compile_features), so
# IntelliSense must match it for headers the compilation database never
# covers -- expected.hpp needs std::expected even in the fallback path.
IDE_C_STANDARD="c17"
IDE_CPP_STANDARD="c++23"

# The variables .vscode/ros.env carries, in the order they are written.
#
# PYTHONPATH alone resolves imports but cannot run anything: without
# LD_LIBRARY_PATH rclpy fails to load librosidl_runtime_c.so, and without
# AMENT_PREFIX_PATH ament_index_python cannot find a package's share
# directory. RMW_IMPLEMENTATION pins CycloneDDS when it is installed: under
# the default FastDDS the driver crashes serializing responses from the
# lab's camera, so VS Code-launched processes must not fall back to it.
#
# PATH, CMAKE_PREFIX_PATH, PKG_CONFIG_PATH and COLCON_PREFIX_PATH are
# deliberately absent. A dotenv file does no $VAR expansion, so writing PATH
# here would not extend the user's PATH, it would replace it in every
# Run/Debug process VS Code starts.
IDE_ROS_ENV_KEYS=(PYTHONPATH LD_LIBRARY_PATH AMENT_PREFIX_PATH ROS_DISTRO
  ROS_VERSION ROS_PYTHON_VERSION ROS_AUTOMATIC_DISCOVERY_RANGE
  RMW_IMPLEMENTATION)
# The subset of the above that is a colon-separated path list.
IDE_ROS_ENV_PATH_KEYS=(PYTHONPATH LD_LIBRARY_PATH AMENT_PREFIX_PATH)

IDE_COMPILE_DB="${VENIMAPPING_WS}/build/compile_commands.json"
IDE_VSCODE_DIR="${VENIMAPPING_WS}/.vscode"
IDE_CPP_PROPERTIES="${IDE_VSCODE_DIR}/c_cpp_properties.json"
IDE_ROS_ENV="${IDE_VSCODE_DIR}/ros.env"
IDE_SETTINGS="${IDE_VSCODE_DIR}/settings.json"

# Assigned by ide_detect_compiler.
IDE_COMPILER_PATH=""
IDE_INTELLISENSE_MODE=""

# Assigned by ide_detect_python.
IDE_PYTHON_PATH=""

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

# ide_commit TMP TARGET: move a finished artifact into place. Warns, removes
# TMP, and returns 1 when the rename fails.
ide_commit() {
  if mv -f "$1" "$2"; then
    return 0
  fi
  rm -f "$1"
  warn "cannot write $2"
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
  if ! command -v python3 >/dev/null 2>&1; then
    error "python3 not found; required to write the JSON artifacts"
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
    warn "no per-package compile_commands.json under ${VENIMAPPING_WS}/build; leaving ${IDE_COMPILE_DB} alone"
    return 1
  fi
  tmp="${IDE_COMPILE_DB}.tmp"
  if ! printf '%s\n' "${parts[@]}" | python3 -c '
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
    warn "cannot merge compilation databases into ${IDE_COMPILE_DB}"
    return 1
  fi
  ide_commit "$tmp" "${IDE_COMPILE_DB}" || return 1
  info "merged ${#parts[@]} compilation database(s) into ${IDE_COMPILE_DB}"
  return 0
}

# Detect the compiler the build actually used, from the CMake caches colcon
# left under build/<pkg>/. CMake records the path in CMakeCache.txt but the
# vendor identity only in CMakeFiles/<ver>/CMakeCXXCompiler.cmake, so both
# are read. Sets IDE_COMPILER_PATH and IDE_INTELLISENSE_MODE; falls back to
# the default toolchain when no cache is readable. Always returns 0.
ide_detect_compiler() {
  local pkg cache compiler_cmake compiler_id="" arch flavor
  IDE_COMPILER_PATH=""
  for pkg in "${VENIMAPPING_PACKAGES[@]}"; do
    cache="${VENIMAPPING_WS}/build/${pkg}/CMakeCache.txt"
    if [[ ! -r "$cache" ]]; then
      continue
    fi
    IDE_COMPILER_PATH=$(sed -n 's/^CMAKE_CXX_COMPILER:FILEPATH=//p' "$cache" \
      | head -n1)
    if [[ -z "${IDE_COMPILER_PATH}" ]]; then
      continue
    fi
    for compiler_cmake in \
      "${VENIMAPPING_WS}/build/${pkg}/CMakeFiles"/*/CMakeCXXCompiler.cmake; do
      if [[ -r "$compiler_cmake" ]]; then
        compiler_id=$(sed -n 's/^set(CMAKE_CXX_COMPILER_ID "\(.*\)")$/\1/p' \
          "$compiler_cmake" | head -n1)
        if [[ -n "$compiler_id" ]]; then
          break
        fi
      fi
    done
    break
  done
  if [[ -z "${IDE_COMPILER_PATH}" ]]; then
    if ! IDE_COMPILER_PATH=$(command -v c++); then
      IDE_COMPILER_PATH="/usr/bin/c++"
    fi
    warn "cannot read a CMake cache under ${VENIMAPPING_WS}/build; assuming compiler ${IDE_COMPILER_PATH} for IntelliSense"
  fi
  case "$compiler_id" in
    *Clang*) flavor=clang ;;
    *) flavor=gcc ;;
  esac
  case "$(uname -m)" in
    aarch64 | arm64) arch=arm64 ;;
    *) arch=x64 ;;
  esac
  IDE_INTELLISENSE_MODE="linux-${flavor}-${arch}"
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

# Overwrite .vscode/c_cpp_properties.json from the current build state,
# creating .vscode/ when absent. The whole file is replaced every time; no
# manual content is preserved.
ide_write_cpp_properties() {
  local tmp
  if ! mkdir -p "${IDE_VSCODE_DIR}"; then
    warn "cannot create ${IDE_VSCODE_DIR}"
    return 1
  fi
  ide_detect_compiler
  tmp="${IDE_CPP_PROPERTIES}.tmp"
  if ! ide_include_dirs | env \
    IDE_NAME="${IDE_CONFIG_NAME}" \
    IDE_NOTE="${IDE_GENERATED_NOTE}" \
    IDE_COMPILER="${IDE_COMPILER_PATH}" \
    IDE_MODE="${IDE_INTELLISENSE_MODE}" \
    IDE_CSTD="${IDE_C_STANDARD}" \
    IDE_CPPSTD="${IDE_CPP_STANDARD}" \
    IDE_DB="${IDE_COMPILE_DB}" \
    python3 -c '
import json, os, sys

seen = set()
includes = []
for line in sys.stdin.read().splitlines():
    if line and line not in seen:
        seen.add(line)
        includes.append(line)
doc = {
    "env": {
        "generatedBy": "venimapping/scripts/ide.sh",
        "generatedNote": os.environ["IDE_NOTE"],
    },
    "configurations": [
        {
            "name": os.environ["IDE_NAME"],
            "compilerPath": os.environ["IDE_COMPILER"],
            "cStandard": os.environ["IDE_CSTD"],
            "cppStandard": os.environ["IDE_CPPSTD"],
            "intelliSenseMode": os.environ["IDE_MODE"],
            "compileCommands": os.environ["IDE_DB"],
            "includePath": includes,
            "defines": [],
        }
    ],
    "version": 4,
}
with open(sys.argv[1], "w") as handle:
    json.dump(doc, handle, indent=4)
    handle.write("\n")
' "$tmp" 2>/dev/null; then
    rm -f "$tmp"
    warn "cannot generate ${IDE_CPP_PROPERTIES}"
    return 1
  fi
  ide_commit "$tmp" "${IDE_CPP_PROPERTIES}" || return 1
  info "wrote ${IDE_CPP_PROPERTIES} (compiler ${IDE_COMPILER_PATH}, ${IDE_INTELLISENSE_MODE})"
  return 0
}

# --- Python: ros.env and settings.json ----------------------------------------

# Detect the Python interpreter the build actually used, from the CMake
# caches under build/<pkg>/ -- the same source ide_detect_compiler reads, one
# key over. Sets IDE_PYTHON_PATH; falls back to the python3 on PATH and then
# to the stock interpreter location. Always returns 0.
ide_detect_python() {
  local pkg cache
  IDE_PYTHON_PATH=""
  for pkg in "${VENIMAPPING_PACKAGES[@]}"; do
    cache="${VENIMAPPING_WS}/build/${pkg}/CMakeCache.txt"
    if [[ ! -r "$cache" ]]; then
      continue
    fi
    IDE_PYTHON_PATH=$(sed -n 's/^_Python3_EXECUTABLE:INTERNAL=//p' "$cache" \
      | head -n1)
    if [[ -n "${IDE_PYTHON_PATH}" ]]; then
      break
    fi
  done
  if [[ -z "${IDE_PYTHON_PATH}" ]]; then
    if ! IDE_PYTHON_PATH=$(command -v python3); then
      IDE_PYTHON_PATH="/usr/bin/python3"
    fi
    warn "no _Python3_EXECUTABLE in any CMake cache under ${VENIMAPPING_WS}/build; assuming interpreter ${IDE_PYTHON_PATH}"
  fi
  return 0
}

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
  # shellcheck disable=SC2016  # the inner script's $1/$@ must expand in the sanitized subshell, not here
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
          if [ -n "$prefix" ] && [ -e "$prefix/share/ament_index/resource_index/packages/rmw_cyclonedds_cpp" ]; then
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
    warn "cannot source $setup (rc=$rc); leaving the ROS environment file alone"
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

# Warn when the interpreter recorded by the build reports a different
# python3.X than the one the captured site-packages directories were built
# for -- the usual sign of an interpreter switch since the last build. The
# captured paths are the truth, so this only warns; the caller still writes.
# Always returns 0.
ide_check_python_version() {
  local pythonpath=$1
  local tag tags
  if [[ ! -x "${IDE_PYTHON_PATH}" ]]; then
    return 0
  fi
  tag=$("${IDE_PYTHON_PATH}" -c \
    'import sys; print("python3.%d" % sys.version_info[1])' 2>/dev/null) || return 0
  tags=$(printf '%s\n' "${pythonpath//:/$'\n'}" \
    | grep -o 'python3\.[0-9]\+' | sort -u) || tags=""
  if [[ -z "$tag" || -z "$tags" ]]; then
    return 0
  fi
  if ! grep -qxF -- "$tag" <<<"$tags"; then
    warn "interpreter ${IDE_PYTHON_PATH} is $tag but the captured paths are for ${tags//$'\n'/ }; writing the captured paths anyway"
  fi
  return 0
}

# Overwrite .vscode/ros.env from the environment the built overlay exports,
# creating .vscode/ when absent. The whole file is replaced every time; no
# manual content is preserved, and nothing varying (no timestamp) is
# written, so repeated runs against an unchanged workspace produce a
# byte-identical file. Warns and returns 1 without touching any existing
# file when the environment cannot be captured or carries no usable
# PYTHONPATH.
ide_write_ros_env() {
  local tmp captured line key
  if ! mkdir -p "${IDE_VSCODE_DIR}"; then
    warn "cannot create ${IDE_VSCODE_DIR}"
    return 1
  fi
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
    warn "sourcing the overlay exported no usable PYTHONPATH; leaving ${IDE_ROS_ENV} alone"
    return 1
  fi
  ide_check_python_version "${values[PYTHONPATH]}"
  tmp="${IDE_ROS_ENV}.tmp"
  # `|| { ... }` instead of `if ! { ... }`: negating a brace group swallows
  # the exit status of a failed redirection, so an unwritable .vscode/ would
  # sail on to the rename below and misreport the failure.
  {
    printf '# %s\n' "${IDE_GENERATED_NOTE}"
    printf '#\n'
    printf '# A snapshot of the environment install/setup.bash exports, read by VS Code\n'
    printf '# through python.envFile. Not a replacement for scripts/env.sh in a\n'
    printf '# terminal: PATH is deliberately absent, so there is no ros2 CLI here.\n'
    for key in "${IDE_ROS_ENV_KEYS[@]}"; do
      if [[ -n "${values[$key]:-}" ]]; then
        printf '%s=%s\n' "$key" "${values[$key]}"
      fi
    done
  } >"$tmp" 2>/dev/null || {
    rm -f "$tmp"
    warn "cannot generate ${IDE_ROS_ENV}"
    return 1
  }
  ide_commit "$tmp" "${IDE_ROS_ENV}" || return 1
  local entries
  entries=$(awk -F: '/^PYTHONPATH=/ {print NF; exit}' "${IDE_ROS_ENV}") \
    || entries=""
  info "wrote ${IDE_ROS_ENV} (${entries:-0} PYTHONPATH entries, interpreter ${IDE_PYTHON_PATH})"
  return 0
}

# Create .vscode/settings.json with the two keys that point VS Code at the
# interpreter and at ros.env -- but only when the file does not exist.
#
# An existing settings.json is never parsed, merged, or rewritten: it is the
# user's file, and both keys are static, so there is nothing to keep in sync
# between runs. The existence probe below is a plain text search for the two
# key names, not a parse; it is there only so the script stays quiet about a
# file it wrote itself.
ide_write_settings() {
  local tmp
  if ! mkdir -p "${IDE_VSCODE_DIR}"; then
    warn "cannot create ${IDE_VSCODE_DIR}"
    return 1
  fi
  if [[ -e "${IDE_SETTINGS}" ]]; then
    if grep -qF -- '"python.defaultInterpreterPath"' "${IDE_SETTINGS}" 2>/dev/null \
      && grep -qF -- '"python.envFile"' "${IDE_SETTINGS}" 2>/dev/null; then
      info "${IDE_SETTINGS} already configures the interpreter and env file; left untouched"
    else
      warn "${IDE_SETTINGS} exists; this script never edits it -- add these keys to resolve ROS 2 Python imports:"
      warn "    \"python.defaultInterpreterPath\": \"${IDE_PYTHON_PATH}\","
      warn "    \"python.envFile\": \"\${workspaceFolder}/.vscode/ros.env\""
    fi
    return 0
  fi
  tmp="${IDE_SETTINGS}.tmp"
  # shellcheck disable=SC2016  # ${workspaceFolder} is a VS Code substitution, resolved by the editor
  if ! env IDE_PY="${IDE_PYTHON_PATH}" python3 -c '
import json, os, sys

doc = {
    "python.defaultInterpreterPath": os.environ["IDE_PY"],
    "python.envFile": "${workspaceFolder}/.vscode/ros.env",
}
with open(sys.argv[1], "w") as handle:
    json.dump(doc, handle, indent=4)
    handle.write("\n")
' "$tmp" 2>/dev/null; then
    rm -f "$tmp"
    warn "cannot generate ${IDE_SETTINGS}"
    return 1
  fi
  ide_commit "$tmp" "${IDE_SETTINGS}" || return 1
  info "wrote ${IDE_SETTINGS} (interpreter ${IDE_PYTHON_PATH}); reload VS Code to pick it up"
  return 0
}

# --- Entry point --------------------------------------------------------------

main() {
  ide_preflight || exit 1
  local rc=0 db=ok cpp=ok rosenv=ok settings=ok summary
  ide_merge_compile_commands || { db=failed; rc=1; }
  ide_write_cpp_properties || { cpp=failed; rc=1; }
  # Detected once here: both remaining writers need the interpreter, and a
  # workspace with no readable CMake cache should warn about it once. The
  # || true suppresses errexit inside the helper, exactly as the || guards
  # do for the writers around it.
  ide_detect_python || true
  ide_write_ros_env || { rosenv=failed; rc=1; }
  ide_write_settings || { settings=failed; rc=1; }
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
