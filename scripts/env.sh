# ------------------------------------------------------------------------------
#  Filename: env.sh
#
#  Purpose:  Sources ROS 2, the Vimba X driver, and project overlays.
#
#  Usage:    source scripts/env.sh
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

# --- Guards -------------------------------------------------------------------

if [ -z "${BASH_VERSION:-}" ]; then
  echo "[venimapping] ERROR: env.sh must be sourced from Bash." >&2
  return 1 2>/dev/null || exit 1
fi

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "[venimapping] ERROR: source this file instead of executing it:" >&2
  echo "  source ${BASH_SOURCE[0]}" >&2
  exit 1
fi

# --- Configuration ------------------------------------------------------------

_venimapping_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
_venimapping_upstream="${HOME}/workspace/upstream"
_venimapping_ros_setup="${_venimapping_upstream}/ros2-jazzy/install/setup.bash"
_venimapping_driver_setup="${_venimapping_upstream}/vimbax-ros2-driver/install/setup.bash"
_venimapping_vimbax_sdk="${_venimapping_upstream}/vimbax-sdk"
_venimapping_cti_dir="${_venimapping_vimbax_sdk}/cti"

# --- Diagnostics --------------------------------------------------------------

_vm_err() {
  printf '[venimapping] ERROR: %s\n' "$*" >&2
}

_vm_print_layout() {
  cat >&2 <<EOF
[venimapping] expected upstream layout:
  ROS 2 Jazzy underlay:
    ${_venimapping_ros_setup}
  vimbax_ros2_driver overlay:
    ${_venimapping_driver_setup}
  Vimba X GenTL producers:
    ${_venimapping_cti_dir}/*.cti
EOF
}

# --- Preconditions ------------------------------------------------------------

_vm_need_file() {
  if [ ! -f "$1" ]; then
    _vm_err "missing $2: $1"
    return 1
  fi
}

_vm_need_dir() {
  if [ ! -d "$1" ]; then
    _vm_err "missing $2: $1"
    return 1
  fi
}

_vm_need_glob() {
  if ! compgen -G "$1" >/dev/null 2>&1; then
    _vm_err "missing $2: $1"
    return 1
  fi
}

_vm_need_gentl_path() {
  if [[ ":${GENICAM_GENTL64_PATH:-}:" != *":$1:"* ]]; then
    _vm_err "missing $2: $1"
    return 1
  fi
}

_vm_validate() {
  _vm_need_file "${_venimapping_ros_setup}" "Jazzy underlay" || return 1
  _vm_need_file "${_venimapping_driver_setup}" "driver overlay" || return 1
  _vm_need_dir "${_venimapping_vimbax_sdk}" "Vimba X SDK" || return 1
  _vm_need_glob "${_venimapping_cti_dir}/*.cti" "GenTL producers" || return 1
  _vm_need_gentl_path "${_venimapping_cti_dir}" "GenTL path registration" || return 1
}

_vm_cleanup() {
  unset -f \
    _vm_err _vm_print_layout _vm_need_file \
    _vm_need_dir _vm_need_glob _vm_need_gentl_path \
    _vm_validate _vm_cleanup

  unset -v \
    _venimapping_root _venimapping_upstream _venimapping_ros_setup \
    _venimapping_driver_setup _venimapping_vimbax_sdk _venimapping_cti_dir \
    _vm_rmw _vm_overlay _vm_venv
}

# --- Environment setup --------------------------------------------------------

if ! _vm_validate; then
  _vm_print_layout
  _vm_cleanup
  return 1
fi

if ! source "${_venimapping_ros_setup}"; then
  _vm_err "failed to source Jazzy underlay: ${_venimapping_ros_setup}"
  _vm_cleanup
  return 1
fi

if ! source "${_venimapping_driver_setup}"; then
  _vm_err "failed to source driver overlay: ${_venimapping_driver_setup}"
  _vm_cleanup
  return 1
fi

if ! command -v ros2 >/dev/null 2>&1; then
  _vm_err "ROS 2 CLI is unavailable after sourcing the underlay and overlay"
  _vm_cleanup
  return 1
fi

if [[ -n "${RMW_IMPLEMENTATION:-}" ]]; then
  _vm_rmw="${RMW_IMPLEMENTATION}"
elif ros2 pkg prefix rmw_cyclonedds_cpp &>/dev/null; then
  export RMW_IMPLEMENTATION="rmw_cyclonedds_cpp"
  _vm_rmw="${RMW_IMPLEMENTATION}"
else
  _vm_rmw="default"
fi

if [[ ! -f "${_venimapping_root}/install/setup.bash" ]]; then
  _vm_overlay="not built"
elif source "${_venimapping_root}/install/setup.bash"; then
  _vm_overlay="active"
else
  _vm_err "failed to source project overlay: ${_venimapping_root}/install/setup.bash"
  _vm_cleanup
  return 1
fi

if [[ "${VIRTUAL_ENV:-}" == "${_venimapping_root}/.venv" ]]; then
  _vm_venv="project"
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
  _vm_venv="external"
elif [[ ! -f "${_venimapping_root}/.venv/bin/activate" ]]; then
  _vm_venv="none"
elif source "${_venimapping_root}/.venv/bin/activate"; then
  _vm_venv="project"
else
  _vm_err "failed to activate project virtual environment"
  _vm_cleanup
  return 1
fi

# --- Summary ------------------------------------------------------------------

printf '\033[32m[venimapping] jazzy=active driver=active gentl=active rmw=%s venv=%s overlay=%s\033[0m\n' \
  "${_vm_rmw}" "${_vm_venv}" "${_vm_overlay}"

_vm_cleanup
