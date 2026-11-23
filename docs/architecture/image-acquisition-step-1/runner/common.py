# ------------------------------------------------------------------------------
#  Filename: common.py
#
#  Purpose:  Small helpers that the step 1 runner, the rig checks, and the
#            preflight share: time stamps, atomic writes, process groups, and
#            the ROS environment.
#
#  Usage:    import common
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import datetime
import os
import signal
import subprocess
import time
from pathlib import Path

# --- Configuration ------------------------------------------------------------

# Prefix variables that a sourced overlay sets. The runner removes them before
# it sources env.sh, so an overlay from another checkout cannot shadow this one.
OVERLAY_VARIABLES = (
    "AMENT_PREFIX_PATH", "CMAKE_PREFIX_PATH", "COLCON_PREFIX_PATH",
    "PYTHONPATH", "LD_LIBRARY_PATH", "ROS_PACKAGE_PATH",
)


class Stop(Exception):
    """Ends the run with a recorded error that needs a person to look at."""

    def __init__(self, reason: str, action: str = "") -> None:
        super().__init__(reason)
        self.action = action


# --- Time and files -----------------------------------------------------------


def now() -> float:
    return time.time()


def stamp(t: float | None) -> str:
    if not t:
        return "-"
    moment = datetime.datetime.fromtimestamp(t).astimezone()
    return moment.isoformat(timespec="seconds")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def excerpt(text: str, limit: int = 1500) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[-limit:]


# --- Processes ----------------------------------------------------------------


def boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""


def group_pids(pgid: int) -> list[int]:
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
        except OSError:
            continue
        fields = stat.rsplit(")", 1)[1].split()
        if fields[0] != "Z" and int(fields[2]) == pgid:
            found.append(int(entry.name))
    return found


def pids_named(name: str) -> list[int]:
    """Returns the live processes whose program or script has this name."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
            state = (entry / "stat").read_text().rsplit(")", 1)[1].split()[0]
        except OSError:
            continue
        if state == "Z":
            continue
        if any(os.path.basename(a.decode(errors="replace")) == name
               for a in argv[:2]):
            found.append(int(entry.name))
    return found


def kill_group(pgid: int, grace_s: float) -> None:
    """Sends SIGINT, then SIGTERM, then SIGKILL until the group is empty."""
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        deadline = now() + grace_s
        while now() < deadline:
            if not group_pids(pgid):
                return
            time.sleep(0.2)


# --- ROS environment ----------------------------------------------------------


def ros_env(env_script: Path) -> dict[str, str]:
    """Sources env.sh in a clean Bash and returns the resulting environment."""
    base = {k: v for k, v in os.environ.items()
            if k not in OVERLAY_VARIABLES}
    base["PATH"] = ":".join(
        part for part in os.environ.get("PATH", "").split(":")
        if "/install/" not in part and not part.endswith("/install"))
    result = subprocess.run(
        ["bash", "-c", 'set +u; source "$1" >/dev/null 2>&1 && env -0', "_",
         str(env_script)],
        capture_output=True, stdin=subprocess.DEVNULL, env=base)
    if result.returncode != 0:
        raise Stop(f"could not source {env_script}",
                   f"Run `source {env_script}` in a terminal and fix the "
                   f"error that it prints. Then run the resume command.")
    pairs = [item.split(b"=", 1) for item in result.stdout.split(b"\0")
             if b"=" in item]
    return {k.decode(): v.decode() for k, v in pairs}
