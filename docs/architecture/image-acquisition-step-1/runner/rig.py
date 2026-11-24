# ------------------------------------------------------------------------------
#  Filename: rig.py
#
#  Purpose:  Does all camera work for the step 1 runner: driver launches with
#            log capture, the init waits, feature reads and writes through the
#            ros2 CLI, the settings file save, the bring-up part A check, the
#            CLI form of part B, and the snapshot and restore of the camera.
#
#  Usage:    import rig
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import ast
import json
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

from common import excerpt, group_pids, kill_group

# --- Configuration ------------------------------------------------------------

INIT_LINE = "Initialization done!"
LOAD_LINE = "Loading settings from file"
NO_FILE = "/nonexistent.xml"
TOLERANCE = 0.001

PARAM_RE = re.compile(r"(?:value is|values are):[ \t]*(.*)")

SERVICE_TYPES = {
    "float": ("FeatureFloatGet", "FeatureFloatSet"),
    "int": ("FeatureIntGet", "FeatureIntSet"),
    "enum": ("FeatureEnumGet", "FeatureEnumSet"),
    "bool": ("FeatureBoolGet", "FeatureBoolSet"),
}

# Each feature that step 1 or its checks write. The runner refuses a write to
# any other feature, so it cannot change IP settings, firmware, or user sets.
FEATURES = {
    "PixelFormat": "enum",
    "Width": "int",
    "Height": "int",
    "TriggerSelector": "enum",
    "TriggerMode": "enum",
    "ExposureTime": "float",
    "AcquisitionFrameRateEnable": "bool",
    "AcquisitionFrameRate": "float",
}

# The phase 1 profile from v2 section 10, "Acquisition profile file". Each row
# is the camera feature, the profile key, and the value.
PROFILE = [
    ("PixelFormat", "pixel_format", "Mono8"),
    ("Width", "width", 1296),
    ("Height", "height", 1032),
    ("TriggerMode", "trigger_mode", "Off"),
    ("AcquisitionFrameRateEnable", "acquisition_frame_rate_enable", True),
    ("AcquisitionFrameRate", "acquisition_frame_rate", 30.0),
    ("ExposureTime", "exposure_time", 4999.455),
]

# The values that bring-up part A writes before the controlled reopen.
PART_A = [("ExposureTime", 10000.0), ("AcquisitionFrameRate", 20.0)]

ERROR_RE = re.compile(
    r"error=vimbax_camera_msgs\.msg\.Error\(code=(-?\d+), "
    r"text=('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\)")
VALUE_RE = re.compile(
    r"[(,]\s*value=('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|[^,()]+)")


class CameraError(Exception):
    """A camera or driver step failed in a way that a file change cannot fix."""


class CheckFailed(Exception):
    """A check with a fixed pass rule failed."""

    def __init__(self, check: str, detail: str, repairable: bool) -> None:
        super().__init__(f"{check}: {detail}")
        self.check = check
        self.detail = detail
        self.repairable = repairable


# --- Commands -----------------------------------------------------------------


class Shell:
    """Runs commands in the ROS environment and writes a transcript."""

    def __init__(self, env: dict[str, str], cwd: Path, transcript: Path) -> None:
        self.env = env
        self.cwd = cwd
        self.transcript = transcript
        cwd.mkdir(parents=True, exist_ok=True)

    def note(self, text: str) -> None:
        with open(self.transcript, "a", encoding="utf-8") as log:
            log.write(text.rstrip("\n") + "\n\n")

    def run(self, argv: list[str], timeout: float,
            cwd: Path | None = None) -> tuple[int, str, float]:
        start = time.monotonic()
        process = subprocess.Popen(
            argv, cwd=cwd or self.cwd, env=self.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            start_new_session=True)
        try:
            output, _ = process.communicate(timeout=timeout)
            code = process.returncode
        except subprocess.TimeoutExpired:
            kill_group(process.pid, 2)
            output, _ = process.communicate()
            output += "\n[the runner killed the command at its time limit]"
            code = 124
        elapsed = time.monotonic() - start
        self.note(f"$ {shlex.join(argv)}\n{output.rstrip()}\n"
                  f"[exit {code}, {elapsed:.2f} s]")
        return code, output, elapsed


class Cli:
    """Calls the driver services through `ros2 service call`."""

    def __init__(self, shell: Shell, namespace: str, timeout_s: float,
                 on_write: Callable[[], None]) -> None:
        self.shell = shell
        self.namespace = namespace.rstrip("/")
        self.timeout_s = timeout_s
        self.on_write = on_write
        self.status_forbidden = ""

    def call(self, service: str, srv_type: str, request: dict | None) -> str:
        argv = ["timeout", str(int(self.timeout_s)), "ros2", "service", "call",
                f"{self.namespace}/{service}",
                f"vimbax_camera_msgs/srv/{srv_type}"]
        if request is not None:
            argv.append(json.dumps(request))
        code, output, _ = self.shell.run(argv, self.timeout_s + 15)
        if code != 0 or "response:" not in output:
            raise CameraError(f"{service} call ended with exit {code}: "
                              f"{excerpt(output, 300)}")
        response = output.split("response:", 1)[1].strip()
        match = ERROR_RE.search(response)
        if match is None:
            raise CameraError(f"{service} reply has no error field: "
                              f"{excerpt(response, 300)}")
        if int(match.group(1)) != 0:
            raise CameraError(f"{service} returned error {match.group(1)} "
                              f"{match.group(2)}")
        return ERROR_RE.sub("error=_", response)

    def get(self, name: str):
        kind = FEATURES[name]
        reply = self.call(f"features/{kind}_get", SERVICE_TYPES[kind][0],
                          {"feature_name": name})
        return parse_value(kind, reply)

    def float_increment(self, name: str) -> float | None:
        """Returns the write increment of a float feature, or None."""
        reply = self.call("features/float_info_get", "FeatureFloatInfoGet",
                          {"feature_name": name})
        available = re.search(r"\binc_available=(True|False)", reply)
        inc = re.search(r"\binc=([-+0-9.eE]+)", reply)
        if available is None or inc is None:
            raise CameraError(f"float info reply has no increment: "
                              f"{excerpt(reply, 300)}")
        value = float(inc.group(1))
        return value if available.group(1) == "True" and value > 0 else None

    def set(self, name: str, value) -> None:
        if name not in FEATURES:
            raise CameraError(f"the runner refuses a write to {name}")
        kind = FEATURES[name]
        self.on_write()
        self.call(f"features/{kind}_set", SERVICE_TYPES[kind][1],
                  {"feature_name": name, "value": value})

    def streaming(self) -> bool:
        if self.status_forbidden:
            raise CameraError(f"a status call is not allowed now: "
                              f"{self.status_forbidden}")
        reply = self.call("status", "Status", None)
        match = re.search(r"streaming=(True|False)", reply)
        if match is None:
            raise CameraError(f"status reply has no streaming field: "
                              f"{excerpt(reply, 300)}")
        return match.group(1) == "True"

    def stream_stop(self) -> None:
        self.call("stream_stop", "StreamStartStop", None)

    def save(self, path: Path, allowed_roots: list[Path]) -> None:
        path = path.resolve()
        if path.suffix != ".xml":
            raise CameraError(f"the runner refuses a settings save to {path}: "
                              f"the name must end in .xml")
        if not any(path.is_relative_to(root.resolve())
                   for root in allowed_roots):
            raise CameraError(f"the runner refuses a settings save to {path}: "
                              f"it is outside {allowed_roots}")
        self.on_write()
        self.call("settings/save", "SettingsLoadSave", {"filename": str(path)})


def parse_value(kind: str, reply: str):
    match = VALUE_RE.search(reply)
    if match is None:
        raise CameraError(f"reply has no value field: {excerpt(reply, 300)}")
    raw = match.group(1).strip()
    try:
        if kind == "float":
            return float(raw)
        if kind == "int":
            return int(raw)
        if kind == "bool":
            return {"True": True, "False": False}[raw]
        return str(ast.literal_eval(raw))
    except (ValueError, KeyError, SyntaxError) as error:
        raise CameraError(f"cannot read a {kind} from {raw!r}: {error}")


def same(name: str, left, right) -> bool:
    if FEATURES.get(name) == "float":
        return abs(float(left) - float(right)) <= TOLERANCE
    return left == right


def took(cli: Cli, name: str, written, read) -> tuple[bool, str]:
    """Decides if the camera took a written value.

    v2 asks for a readback within 0.001. The camera rounds a float write to
    its own increment, for example ExposureTime 10000.0 to 10004.707. So a
    float readback also passes when it is within one increment of the
    written value. The report lists each such rounding.
    """
    if same(name, read, written):
        return True, "exact"
    if FEATURES.get(name) != "float":
        return False, f"wrote {written}, read {read}"
    inc = cli.float_increment(name)
    if inc is not None and abs(float(read) - float(written)) <= inc * 1.0001:
        return True, (f"rounded: wrote {written}, the camera holds {read}, "
                      f"increment {inc}")
    return False, f"wrote {written}, read {read}, increment {inc}"


# --- Driver launches ----------------------------------------------------------


class Driver:
    """Starts each driver in its own process group and stops it again."""

    def __init__(self, shell: Shell, settings: dict, bare_params: Path,
                 on_launch: Callable[[int], None],
                 on_stop: Callable[[int], None]) -> None:
        self.shell = shell
        self.settings = settings
        self.bare_params = bare_params
        self.on_launch = on_launch
        self.on_stop = on_stop
        self.processes: dict[int, subprocess.Popen] = {}
        self.init_waits: dict[str, dict] = {}

    def launch(self, name: str, args: list[str] | None = None,
               bare: bool = False) -> int:
        """Starts a driver whose console output goes through tee to name.log."""
        if bare:
            command = ["ros2", "run", "vimbax_camera", "vimbax_camera_node",
                       "--ros-args", "-r",
                       f"__ns:={self.settings['namespace']}",
                       "-r", "__node:=vimbax_camera",
                       "--params-file", str(self.bare_params)]
        else:
            command = ["ros2", "launch", "venimapping_bringup",
                       "camera.launch.py", *(args or [])]
        line = f"{shlex.join(command)} 2>&1 | tee {shlex.quote(name + '.log')}"
        self.shell.note(f"$ {line}  (started in the background)")
        process = subprocess.Popen(
            ["bash", "-c", line], cwd=self.shell.cwd, env=self.shell.env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        self.processes[process.pid] = process
        self.on_launch(process.pid)
        return process.pid

    def init_wait(self, name: str) -> int:
        """Runs the init wait of v2 section 10 on name.log. Returns its status."""
        limit = self.settings["init_wait_s"]
        argv = ["timeout", str(limit), "sh", "-c",
                'until grep -qF "Initialization done!" "$1"; '
                'do sleep 0.5; done', "sh", f"{name}.log"]
        code, _, elapsed = self.shell.run(argv, limit + 15)
        self.init_waits[name] = {"status": code, "seconds": round(elapsed, 2),
                                 "limit_s": limit}
        return code

    def stop(self, pgid: int) -> None:
        kill_group(pgid, self.settings["stop_grace_s"])
        process = self.processes.pop(pgid, None)
        if process is not None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        left = group_pids(pgid)
        self.shell.note(f"# stopped driver group {pgid}; processes left: {left}")
        if left:
            raise CameraError(f"driver group {pgid} did not stop: {left}")
        self.on_stop(pgid)
        self.shell.run(["ros2", "daemon", "stop"], 30)

    def stop_all(self) -> None:
        for pgid in list(self.processes):
            self.stop(pgid)


def write_bare_params(path: Path, settings: dict) -> None:
    """Writes the parameter file for a driver that loads no settings file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Written by the step 1 runner for a driver without settings_file.\n"
        "/**/vimbax_camera:\n"
        "  ros__parameters:\n"
        f"    camera_id: \"{settings['camera_id']}\"\n"
        "    autostream: 0\n"
        "    buffer_count: 7\n")


# --- Snapshot and restore -----------------------------------------------------


def snapshot(cli: Cli) -> dict:
    """Reads each feature in FEATURES. TriggerMode is read under FrameStart."""
    values = {}
    for name in ("TriggerSelector", "PixelFormat", "Width", "Height"):
        values[name] = cli.get(name)
    if values["TriggerSelector"] != "FrameStart":
        cli.set("TriggerSelector", "FrameStart")
    values["TriggerMode"] = cli.get("TriggerMode")
    if values["TriggerSelector"] != "FrameStart":
        cli.set("TriggerSelector", values["TriggerSelector"])
    for name in ("ExposureTime", "AcquisitionFrameRateEnable",
                 "AcquisitionFrameRate"):
        values[name] = cli.get(name)
    if cli.streaming():
        raise CameraError("the camera was streaming at the snapshot")
    return values


def restore(cli: Cli, baseline: dict) -> dict:
    """Writes back each baseline value that differs, in a safe order."""
    changed = []

    def put(name: str, value) -> None:
        if not same(name, cli.get(name), value):
            cli.set(name, value)
            changed.append(name)

    if cli.streaming():
        cli.stream_stop()
        if cli.streaming():
            raise CameraError("the driver still reports streaming after stop")
    for name in ("PixelFormat", "Width", "Height"):
        put(name, baseline[name])
    cli.set("TriggerSelector", "FrameStart")
    put("TriggerMode", baseline["TriggerMode"])
    put("ExposureTime", baseline["ExposureTime"])
    if baseline["AcquisitionFrameRateEnable"]:
        put("AcquisitionFrameRateEnable", True)
        put("AcquisitionFrameRate", baseline["AcquisitionFrameRate"])
    else:
        # The rate is read only and derived while the enable is false.
        put("AcquisitionFrameRateEnable", False)

    mismatched = []
    cli.set("TriggerSelector", "FrameStart")
    for name in FEATURES:
        if name == "TriggerSelector":
            continue
        if name == "AcquisitionFrameRate" and not baseline[
                "AcquisitionFrameRateEnable"]:
            continue
        current = cli.get(name)
        if not same(name, current, baseline[name]):
            mismatched.append({"name": name, "expected": baseline[name],
                               "actual": current})
    cli.set("TriggerSelector", baseline["TriggerSelector"])
    current = cli.get("TriggerSelector")
    if current != baseline["TriggerSelector"]:
        mismatched.append({"name": "TriggerSelector",
                           "expected": baseline["TriggerSelector"],
                           "actual": current})
    if mismatched:
        raise CameraError(f"features differ after the restore: {mismatched}")
    return {"restored": changed, "verified": list(FEATURES)}


# --- Rig sessions -------------------------------------------------------------


class Rig:
    """One camera stage. It collects check results and the init waits."""

    def __init__(self, cli: Cli, driver: Driver, log_dir: Path,
                 ensure_baseline: Callable[[], None], worktree: Path,
                 settings: dict) -> None:
        self.cli = cli
        self.driver = driver
        self.log_dir = log_dir
        self.ensure_baseline = ensure_baseline
        self.worktree = worktree
        self.settings = settings
        self.checks: list[dict] = []
        self.facts: dict = {}

    def record(self, check: str, passed: bool | None, detail: str) -> None:
        self.checks.append({"id": check, "passed": passed, "detail": detail})
        self.cli.shell.note(f"# check {check}: "
                            f"{'PASS' if passed else 'FAIL'} {detail}")

    def fail(self, check: str, detail: str, repairable: bool) -> None:
        self.record(check, False, detail)
        raise CheckFailed(check, detail, repairable)

    def log_text(self, name: str) -> str:
        path = self.log_dir / f"{name}.log"
        return path.read_text(errors="replace") if path.exists() else ""

    def wait_for_init(self, check: str, name: str) -> None:
        code = self.driver.init_wait(name)
        wait = self.driver.init_waits[name]
        if code != 0:
            self.fail(check, f"the init wait on {name}.log ended with status "
                             f"{code} after {wait['seconds']} s", False)
        self.record(check, True, f"init wait on {name}.log ended with status "
                                 f"0 after {wait['seconds']} s")

    def grep_load(self, *names: str) -> tuple[int, str]:
        argv = ["grep", "-F", LOAD_LINE, *[f"{n}.log" for n in names]]
        code, output, _ = self.cli.shell.run(argv, 30)
        return code, output.strip()

    def result(self) -> dict:
        return {"checks": self.checks, "init_waits": self.driver.init_waits,
                "facts": self.facts}


def make_settings(rig: Rig, save_path: Path, allowed_roots: list[Path],
                  keep: Path) -> None:
    """Makes camera_settings.xml with steps 1 to 7 in v2 section 10.

    The runner does step 8, the copy into the package, after its scan of the
    file. A copy for the logs goes to keep.
    """
    cli = rig.cli
    pgid = rig.driver.launch("driver_settings", bare=True)
    rig.wait_for_init("S0", "driver_settings")
    if LOAD_LINE in rig.log_text("driver_settings"):
        rig.fail("S0", "the driver without settings_file tried a load", False)
    rig.ensure_baseline()
    if cli.streaming():
        cli.stream_stop()
        if cli.streaming():
            rig.fail("S0", "the driver still reports streaming", False)
    rig.record("S0", True, "the driver without settings_file is up and "
                           "the stream is stopped")

    cli.set("PixelFormat", "Mono8")
    cli.set("Width", 1296)
    cli.set("Height", 1032)
    rig.record("S1", True, "wrote PixelFormat Mono8, Width 1296, Height 1032")
    cli.status_forbidden = "v2 section 10 forbids status between steps 2 and 6"
    cli.set("TriggerSelector", "FrameStart")
    cli.set("TriggerMode", "Off")
    rig.record("S2", True, "wrote TriggerSelector FrameStart, then "
                           "TriggerMode Off")
    cli.set("AcquisitionFrameRateEnable", True)
    rig.record("S3", True, "wrote AcquisitionFrameRateEnable true")
    cli.set("AcquisitionFrameRate", 30.0)
    rig.record("S4", True, "wrote AcquisitionFrameRate 30.0")
    cli.set("ExposureTime", 4999.455)
    rig.record("S5", True, "wrote ExposureTime 4999.455")

    readback = {}
    for name, _, value in PROFILE:
        readback[name] = cli.get(name)
    rig.facts["readback_before_save"] = readback
    wrong = {n: readback[n] for n, _, v in PROFILE if not same(n, readback[n], v)}
    if wrong:
        rig.fail("S6", f"the camera did not take the profile values: {wrong}",
                 False)
    rig.record("S6", True, f"no status call between steps 2 and 7; the "
                           f"readback matches the profile: {readback}")

    cli.save(save_path, allowed_roots)
    cli.status_forbidden = ""
    if not save_path.is_file() or save_path.stat().st_size == 0:
        rig.fail("S7", f"settings/save left no file at {save_path}", False)
    rig.record("S7", True, f"settings/save wrote {save_path} "
                           f"({save_path.stat().st_size} bytes)")
    rig.driver.stop(pgid)
    keep.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(save_path, keep)


def rig_check(rig: Rig, profile_file: Path, install_prefix: Path) -> None:
    """Runs part A steps 1 to 16 and exit checks 4 to 10 of step 1."""
    cli = rig.cli
    driver = rig.driver

    pgid = driver.launch("driver_control", [f"settings_file:={NO_FILE}"])
    rig.record("A1", True, f"launched with settings_file:={NO_FILE}")
    rig.wait_for_init("A2", "driver_control")
    rig.ensure_baseline()
    code, output = rig.grep_load("driver_control")
    rig.record("A3", code == 0 and bool(output), output or f"grep exit {code}")
    if code != 0 or not output:
        rig.fail("A4", "the capture does not show the failed-load line", True)
    rig.record("A4", True, "the control log has the failed-load line")
    lines = rig.log_text("driver_control").splitlines()
    load_at = next(i for i, line in enumerate(lines) if LOAD_LINE in line)
    init_at = next(i for i, line in enumerate(lines) if INIT_LINE in line)
    rig.facts["control_order"] = {"load_line": load_at + 1,
                                  "init_line": init_at + 1,
                                  "in_order": load_at < init_at}
    driver.stop(pgid)
    rig.record("A5", True, "stopped the control driver")

    pgid = driver.launch("driver_a")
    rig.record("A6", True, "launched with the default arguments")
    rig.wait_for_init("A7", "driver_a")
    # A failed load in driver_a means that the launch file is at fault.
    loaded = LOAD_LINE not in rig.log_text("driver_a")
    try:
        if cli.streaming():
            rig.fail("A8", "the stream runs before the part A writes", False)
        for index, (name, value) in enumerate(PART_A):
            cli.set(name, value)
            rig.record(f"A{8 + index}", True, f"wrote {name} {value}")
        values = {name: cli.get(name) for name, _ in PART_A}
    except CameraError as error:
        rig.fail("A8", f"{error}; driver_a loaded the settings file: {loaded}",
                 not loaded)
    rig.facts["part_a_readback"] = values
    rig.record("A10", True, f"read back {values}")
    profile = {name: value for name, _, value in PROFILE}
    wrong, notes = {}, {}
    for name, value in PART_A:
        try:
            ok, note = took(cli, name, value, values[name])
        except CameraError as error:
            ok, note = False, str(error)
        if ok and same(name, values[name], profile[name]):
            ok, note = False, f"{note}; equal to the profile value"
        notes[name] = note
        if not ok:
            wrong[name] = values[name]
    rig.facts["part_a_rounding"] = {n: t for n, t in notes.items()
                                    if t != "exact"}
    if wrong:
        rig.fail("A11", f"the camera did not take the part A values: "
                        f"{wrong}; {notes}", not loaded)
    rig.record("A11", True,
               "the readback is within 0.001 of each value" if not
               rig.facts["part_a_rounding"] else
               f"each value taken; v2 step 11 asks for 0.001, and the camera "
               f"rounded: {rig.facts['part_a_rounding']}")
    driver.stop(pgid)
    rig.record("A12", True, "stopped driver_a")

    pgid = driver.launch("driver_b")
    rig.record("A13", True, "launched again with the default arguments")
    rig.wait_for_init("A14", "driver_b")
    code, output = rig.grep_load("driver_a", "driver_b")
    rig.record("A15", code == 1 and not output,
               output or f"grep exit {code}, no line")
    if code != 1 or output:
        rig.fail("A16", f"grep printed a failed-load line or failed: "
                        f"exit {code}: {output}", code == 0)
    rig.record("A16", True, "neither driver_a.log nor driver_b.log has the "
                            "failed-load line")

    failures = exit_checks(rig, profile_file, install_prefix)
    driver.stop(pgid)
    if failures:
        first = failures[0]
        raise CheckFailed(first["id"], first["detail"],
                          all(f["repairable"] for f in failures))
    p11_check(rig)
    host_check(rig)


def exit_checks(rig: Rig, profile_file: Path, install_prefix: Path) -> list:
    """Runs exit checks 4 to 10 on driver_b. Returns the failures."""
    cli = rig.cli
    shell = cli.shell
    namespace = rig.settings["namespace"]
    node = f"{namespace}/vimbax_camera"
    failures = []

    def check(check_id: str, passed: bool, detail: str,
              repairable: bool) -> None:
        rig.record(check_id, passed, detail)
        if not passed:
            failures.append({"id": check_id, "detail": detail,
                             "repairable": repairable})

    def graph(argv: list[str], rule: Callable[[str], bool]) -> str:
        deadline = time.monotonic() + rig.settings["graph_retry_s"]
        while True:
            code, output, _ = shell.run(argv, 60)
            if (code == 0 and rule(output)) or time.monotonic() > deadline:
                return output if code == 0 else f"exit {code}: {output}"
            time.sleep(1.0)

    def param(name: str) -> str:
        # ros2 param get prints "<Type> value is: <v>" for a scalar and
        # "<Type> values are: [<v>, ...]" for an array.
        output = graph(["ros2", "param", "get", node, name],
                       lambda out: PARAM_RE.search(out) is not None)
        match = PARAM_RE.search(output)
        return match.group(1).strip() if match else output.strip()

    value = param("use_ros_time")
    check("E4", value == "True", f"use_ros_time is {value}", True)

    value = param("settings_file")
    expected = install_prefix / "share/venimapping_bringup/config/" \
                                "camera_settings.xml"
    exists = Path(value).is_file()
    if value == str(expected) and exists:
        detail = f"settings_file is {value}, the installed path; the file exists"
    else:
        detail = (f"settings_file is {value}; expected {expected}; file "
                  f"exists: {exists}")
    check("E5", value == str(expected) and exists, detail, True)

    value = param("image_raw.enable_pub_plugins")
    try:
        plugins = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        plugins = value
    check("E6", plugins == ["image_transport/raw"],
          f"image_raw.enable_pub_plugins is {value}", True)

    topic = f"{namespace}/image_raw"
    output = graph(["ros2", "topic", "info", topic],
                   lambda out: "Publisher count: 1" in out)
    count = re.search(r"Publisher count: (\d+)", output)
    check("E7", bool(count) and count.group(1) == "1",
          f"Publisher count: {count.group(1) if count else '?'}", True)

    extra = []
    for _ in range(2):
        code, output, _ = shell.run(["ros2", "topic", "list"], 60)
        extra += [t for t in output.split() if t.startswith(topic + "/")]
        time.sleep(1.0)
    check("E8", code == 0 and not extra,
          f"topics under {topic}/: {sorted(set(extra)) or 'none'}", True)

    check_profile(rig, profile_file, check)

    argv = ["timeout", str(rig.settings["probe_timeout_s"]), "ros2", "run",
            "venimapping_camera", "camera_gateway_probe", "--ros-args",
            "-p", "enable_writes:=false", "-p", "exercise_stream:=false"]
    code, output, _ = shell.run(argv, rig.settings["probe_timeout_s"] + 15)
    (rig.log_dir / "gateway_probe.log").write_text(output)
    summary = [line for line in output.splitlines() if "probe complete" in line]
    check("E10", code == 0 and any("all checks passed" in s for s in summary),
          f"exit {code}; {summary[-1].strip() if summary else 'no summary'}",
          False)
    return failures


def check_profile(rig: Rig, profile_file: Path, check: Callable) -> None:
    """Exit check 9: CLI reads of the seven profile values."""
    import yaml

    try:
        loaded = yaml.safe_load(profile_file.read_text())
        profile = loaded["/**"]["ros__parameters"]["profile"]
        file_values = {name: profile[key] for name, key, _ in PROFILE}
    except (OSError, KeyError, TypeError, yaml.YAMLError) as error:
        check("E9", False, f"cannot read {profile_file.name}: {error}", True)
        return
    wrong_file = {n: file_values[n] for n, _, v in PROFILE
                  if not same(n, file_values[n], v)}
    if wrong_file:
        check("E9", False, f"{profile_file.name} differs from v2: {wrong_file}",
              True)
        return
    try:
        rig.cli.set("TriggerSelector", "FrameStart")
        camera = {name: rig.cli.get(name) for name, _, _ in PROFILE}
    except CameraError as error:
        check("E9", False, str(error), False)
        return
    rig.facts["profile_readback"] = camera
    wrong = {n: camera[n] for n, _, _ in PROFILE
             if not same(n, camera[n], file_values[n])}
    check("E9", not wrong, f"camera {camera}; differs: {wrong or 'none'}",
          False)


def p11_check(rig: Rig) -> None:
    """Tests P11: do written values survive a driver restart without a file."""
    cli = rig.cli
    result = {"holds": None, "detail": ""}
    rig.facts["p11"] = result
    try:
        pgid = rig.driver.launch("p11_write", [f"settings_file:={NO_FILE}"])
        if rig.driver.init_wait("p11_write") != 0:
            raise CameraError("the init wait on p11_write.log failed")
        if not cli.get("AcquisitionFrameRateEnable"):
            cli.set("AcquisitionFrameRateEnable", True)
        for name, value in PART_A:
            cli.set(name, value)
        written = {name: cli.get(name) for name, _ in PART_A}
        taken = [took(cli, n, v, written[n])[0] for n, v in PART_A]
        rig.driver.stop(pgid)
        if not all(taken):
            raise CameraError(f"the camera did not take {written}")
        pgid = rig.driver.launch("p11_read", [f"settings_file:={NO_FILE}"])
        if rig.driver.init_wait("p11_read") != 0:
            raise CameraError("the init wait on p11_read.log failed")
        after = {name: cli.get(name) for name, _ in PART_A}
        after["AcquisitionFrameRateEnable"] = cli.get(
            "AcquisitionFrameRateEnable")
        rig.driver.stop(pgid)
        # Compare with the values that the camera held, after its rounding.
        holds = (all(same(n, after[n], written[n]) for n, _ in PART_A)
                 and after["AcquisitionFrameRateEnable"] is True)
        result.update(holds=holds, written=written, after_restart=after,
                      detail="the values survived the restart" if holds else
                      "the camera did not keep the values across the restart")
    except CameraError as error:
        result["detail"] = f"inconclusive: {error}"
        rig.driver.stop_all()
    rig.record("P11", result["holds"], result["detail"])


def host_check(rig: Rig) -> None:
    code, output, _ = rig.cli.shell.run(
        ["sysctl", "net.core.rmem_max", "net.core.rmem_default"], 30)
    values = dict(re.findall(r"(net\.core\.\S+)\s*=\s*(\d+)", output))
    low = {k: v for k, v in values.items() if int(v) < 8388608}
    rig.facts["host"] = {"values": values, "below_8388608": low}
    rig.record("H1", True if code == 0 else None,
               f"{values}; below 8388608: {low or 'none'}")
