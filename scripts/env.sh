# ------------------------------------------------------------------------------
#  Filename: env.sh
#
#  Purpose: SENTENCE (50-80 characters).
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

case "${0}" in
  env.sh|*/env.sh)
    echo "[venimapping] ERROR: source this file; do not execute it:" >&2
    echo "[venimapping]          source ${0}" >&2
    exit 1
    ;;
esac

if [ -z "${BASH_VERSION-}" ]; then
  echo "[venimapping] ERROR: env.sh requires bash." >&2
  return 1 2>/dev/null || exit 1
fi

VENIMAPPING_UPSTREAM="${HOME}/workspace/upstream"
VENIMAPPING_ROS_SETUP="${VENIMAPPING_UPSTREAM}/ros2-jazzy/install/setup.bash"
VENIMAPPING_DRIVER_SETUP="${VENIMAPPING_UPSTREAM}/vimbax-ros2-driver/install/setup.bash"
VENIMAPPING_VIMBAX_SDK="${VENIMAPPING_UPSTREAM}/vimbax-sdk"
VENIMAPPING_CTI_DIR="${VENIMAPPING_VIMBAX_SDK}/cti"

_vm_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENIMAPPING_ROOT="$(cd -- "${_vm_script_dir}/.." && pwd)"

_vm_err() {
  printf '[venimapping] ERROR: %s\n' "$*" >&2
}

_vm_warn() {
  local line first="$1"
  shift
  printf '[venimapping] WARNING: %s\n' "${first}" >&2
  for line in "$@"; do
    printf '[venimapping]          %s\n' "${line}" >&2
  done
}

_vm_print_layout() {
  cat >&2 <<EOF_LAYOUT
[venimapping] expected upstream layout:
  ${VENIMAPPING_ROS_SETUP}
      ROS 2 Jazzy underlay
  ${VENIMAPPING_DRIVER_SETUP}
      vimbax_ros2_driver overlay
  ${VENIMAPPING_CTI_DIR}/*.cti
      Vimba X GenTL producers
EOF_LAYOUT
}

_vm_need_file() {
  [ -f "$1" ] || {
    _vm_err "missing $2: $1"
    return 1
  }
}

_vm_need_dir()  {
  [ -d "$1" ] || {
    _vm_err "missing $2: $1"
    return 1
  }
}

_vm_need_glob() {
  compgen -G "$1" >/dev/null 2>&1 || {
    _vm_err "missing $2: $1"
    return 1
  }
}

_vm_validate() {
  _vm_need_file "${VENIMAPPING_ROS_SETUP}" "Jazzy underlay" || return 1
  _vm_need_file "${VENIMAPPING_DRIVER_SETUP}" "driver overlay" || return 1
  _vm_need_dir "${VENIMAPPING_VIMBAX_SDK}" "Vimba X SDK" || return 1

  if ! _vm_need_glob "${VENIMAPPING_CTI_DIR}/*.cti" "GenTL producers"; then
    _vm_err "locate VimbaGigETL.cti under ${VENIMAPPING_VIMBAX_SDK} and update VENIMAPPING_CTI_DIR"
    return 1
  fi
}

_vm_cleanup() {
  unset -f _vm_err _vm_warn _vm_print_layout \
    _vm_need_file _vm_need_dir _vm_need_glob _vm_validate _vm_cleanup
  unset _vm_script_dir _vm_rmw _vm_overlay _vm_venv
}

if ! _vm_validate; then
  _vm_print_layout
  _vm_cleanup
  return 1
fi

if ! source "${VENIMAPPING_ROS_SETUP}"; then
  _vm_err "failed to source Jazzy underlay: ${VENIMAPPING_ROS_SETUP}"
  _vm_cleanup
  return 1
fi

if ! source "${VENIMAPPING_DRIVER_SETUP}"; then
  _vm_err "failed to source driver overlay: ${VENIMAPPING_DRIVER_SETUP}"
  _vm_cleanup
  return 1
fi

if ! command -v ros2 >/dev/null 2>&1; then
  _vm_err "ROS 2 CLI is unavailable after sourcing the underlays"
  _vm_cleanup
  return 1
fi

case ":${GENICAM_GENTL64_PATH-}:" in
  *":${VENIMAPPING_CTI_DIR}:"*) ;;
  *)
    export GENICAM_GENTL64_PATH="${VENIMAPPING_CTI_DIR}${GENICAM_GENTL64_PATH:+:${GENICAM_GENTL64_PATH}}"
    ;;
esac

if [ -n "${RMW_IMPLEMENTATION-}" ]; then
  _vm_rmw="${RMW_IMPLEMENTATION}"
elif ros2 pkg prefix rmw_cyclonedds_cpp >/dev/null 2>&1; then
  export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  _vm_rmw="rmw_cyclonedds_cpp"
else
  _vm_rmw="default"
fi

_vm_overlay="not built"
if [ -f "${VENIMAPPING_ROOT}/install/setup.bash" ]; then
  if ! source "${VENIMAPPING_ROOT}/install/setup.bash"; then
    _vm_err "failed to source project overlay: ${VENIMAPPING_ROOT}/install/setup.bash"
    _vm_cleanup
    return 1
  fi
  _vm_overlay="active"
fi

_vm_venv="none"
if [ -n "${VIRTUAL_ENV-}" ]; then
  if [ "${VIRTUAL_ENV}" = "${VENIMAPPING_ROOT}/.venv" ]; then
    _vm_venv="project"
  else
    _vm_venv="external"
    _vm_warn "another Python virtual environment is already active:" "${VIRTUAL_ENV}"
  fi
elif [ -f "${VENIMAPPING_ROOT}/.venv/bin/activate" ]; then
  if ! source "${VENIMAPPING_ROOT}/.venv/bin/activate"; then
    _vm_err "failed to activate project virtual environment"
    _vm_cleanup
    return 1
  fi
  _vm_venv="project"
fi

printf '\033[32m[venimapping] jazzy=active driver=active gentl=active rmw=%s venv=%s overlay=%s\033[0m\n' \
  "${_vm_rmw}" "${_vm_venv}" "${_vm_overlay}"

_vm_cleanup
