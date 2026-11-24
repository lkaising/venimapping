# ------------------------------------------------------------------------------
#  Filename: dryrun.py
#
#  Purpose:  Runs the step 1 runner against a throwaway repository, remote,
#            and driver checkout, with fake agents, a fake colcon, and a fake
#            ros2 CLI that serves a fake camera and driver. Checks the success
#            path and each failure path that it can simulate.
#
#  Usage:    python3 dryrun.py <empty scratch directory> [scenario ...]
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


# The power-on ExposureTime of the fake camera, on the grid of the real one.
ON_EXPOSURE = 5012.627
# The fake camera rounds the part A write of 10000.0 to this value.
PART_A_EXPOSURE = 10004.815

# --- Configuration ------------------------------------------------------------

DRYRUN_DIR = Path(__file__).resolve().parent
RUNNER_DIR = DRYRUN_DIR.parent
HARNESS_DIR = RUNNER_DIR.parent
SOURCE_ROOT = HARNESS_DIR.parent.parent.parent
HARNESS = "docs/architecture/image-acquisition-step-1"
OUT = f"{HARNESS}/output"
PKG = "src/venimapping_bringup"
XML = f"{PKG}/config/camera_settings.xml"
V2 = "docs/architecture/image-acquisition-design-v2.md"
BRANCH = "feat/dryrun-step1"
REAL_GIT = shutil.which("git")
ALLOWED = {f"{PKG}/config/camera.yaml", f"{PKG}/config/acquisition_profile.yaml",
           f"{PKG}/launch/camera.launch.py", f"{PKG}/CMakeLists.txt",
           f"{PKG}/package.xml", f"{PKG}/test/test_camera_config.py", XML}

sys.dont_write_bytecode = True
sys.path.insert(0, str(RUNNER_DIR))
import run as runner  # noqa: E402
from common import pids_named  # noqa: E402

GIT_WRAPPER = f"""#!/bin/bash
real={REAL_GIT}
state="$STEP1_FAKE_STATE"
if [ "$1" = push ] && [ -n "$STEP1_PUSH_FAIL_STAGE" ] && \\
   [ ! -f "$state/push-failed" ] && "$real" log -1 --format=%B | \\
     grep -qx "Step1-Stage: $STEP1_PUSH_FAIL_STAGE"; then
  touch "$state/push-failed"
  exec "$real" push "$state/no-such-remote.git" HEAD:refs/heads/x
fi
if [ "$1" = push ] && [ -n "$STEP1_FINAL_PUSH_FAIL" ] && \\
   [ ! -f "$state/final-push-failed" ] && \\
   "$real" log -1 --format=%B | grep -qx "Step1-Event: run-complete"; then
  touch "$state/final-push-failed"
  exec "$real" push "$state/no-such-remote.git" HEAD:refs/heads/x
fi
"$real" "$@"
rc=$?
if [ "$1" = commit ] && [ $rc -eq 0 ] && [ -n "$STEP1_CRASH_STAGE" ] && \\
   [ ! -f "$state/crashed" ] && "$real" log -1 --format=%B | \\
     grep -qx "Step1-Stage: $STEP1_CRASH_STAGE"; then
  touch "$state/crashed"
  kill -9 $PPID
fi
exit $rc
"""

TOOL_WRAPPER = '#!/bin/sh\nexec python3 "{script}" "$@"\n'


# --- Setup --------------------------------------------------------------------


def git(*args: str, cwd: Path) -> str:
    return subprocess.run([REAL_GIT, *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


def setup(root: Path, scenario: dict, accounts: bool = True,
          faults: dict | None = None) -> dict:
    # Each scenario uses the exposure grid of the real camera by default.
    scenario.setdefault("camera", {}).setdefault("exposure_grid", True)
    remote, work, driver = root / "remote.git", root / "work", root / "driver"
    state, run_dir, bin_dir = root / "fake-state", root / "run", root / "bin"
    for path in (work, driver, state, bin_dir):
        path.mkdir(parents=True)

    git("init", "--quiet", "--bare", str(remote), cwd=root)
    git("init", "--quiet", "-b", BRANCH, cwd=work)
    git("config", "user.name", "Dry Run", cwd=work)
    git("config", "user.email", "dryrun@localhost", cwd=work)
    for name in ("runner", "prompts"):
        shutil.copytree(HARNESS_DIR / name, work / HARNESS / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(SOURCE_ROOT / PKG, work / PKG,
                    ignore=shutil.ignore_patterns("__pycache__", "test",
                                                  "acquisition_profile.yaml",
                                                  "camera_settings.xml"))
    (work / V2).parent.mkdir(parents=True, exist_ok=True)
    (work / V2).write_text("# v2 stand-in\n")
    (work / ".gitignore").write_text("build/\ninstall/\nlog/\n")
    git("add", ".", cwd=work)
    git("commit", "--quiet", "-m", "dry run base", cwd=work)
    git("remote", "add", "origin", str(remote), cwd=work)
    git("push", "--quiet", "-u", "origin", BRANCH, cwd=work)

    git("init", "--quiet", cwd=driver)
    (driver / "driver.cpp").write_text("// stand-in\n")
    git("add", ".", cwd=driver)
    git("-c", "user.name=d", "-c", "user.email=d@d", "commit", "--quiet",
        "-m", "driver", cwd=driver)

    (bin_dir / "git").write_text(GIT_WRAPPER)
    (bin_dir / "ros2").write_text(
        TOOL_WRAPPER.format(script=DRYRUN_DIR / "fake_ros2.py"))
    for tool in ("git", "ros2"):
        (bin_dir / tool).chmod(0o755)
    env_script = root / "camera-env.sh"
    env_script.write_text("true\n")
    scenario_file = root / "scenario.json"
    scenario_file.write_text(json.dumps(scenario, indent=2))

    agent = ["python3", str(DRYRUN_DIR / "fake_agent.py")]
    settings = {
        "run_dir": str(run_dir), "remote": "origin", "branch": BRANCH,
        "env_script": str(env_script),
        "read_roots": [str(driver)], "driver_source": str(driver),
        "claude": {"command": [*agent, "claude"], "model": None,
                   "timeout_s": 60},
        "codex": {"command": [*agent, "codex"], "timeout_s": 60},
        "build": {"colcon": ["python3", str(DRYRUN_DIR / "fake_colcon.py")],
                  "timeout_s": 60},
        "transient_backoff_s": [0.2, 0.4, 0.8],
        "quota_backoff_s": [1, 2, 4],
        "quota_margin_s": 0,
        "max_sleep_chunk_s": 0.5,
        "max_build_repairs": 2,
        "max_rig_repairs": 1,
        "camera": {
            "namespace": "/vimbax_camera", "camera_id": "0GPF3",
            "driver_process": "vimbax_camera_node", "init_wait_s": 3,
            "service_timeout_s": 3, "graph_retry_s": 1, "stop_grace_s": 2,
            "probe_timeout_s": 5, "xml_denied_policy": "stop",
            "xml_denied_patterns": json.loads(
                (RUNNER_DIR / "settings.json").read_text())["camera"]
            ["xml_denied_patterns"],
        },
    }
    settings["camera"].update(scenario.get("camera_settings", {}))
    if accounts:
        work_dir = root / "claude-work"
        work_dir.mkdir()
        settings["claude"]["accounts"] = [
            {"name": "personal", "config_dir": None},
            {"name": "work", "config_dir": str(work_dir)}]
    settings_file = root / "settings.json"
    settings_file.write_text(json.dumps(settings, indent=2))
    env = dict(os.environ)
    for key in ("STEP1_CRASH_STAGE", "STEP1_PUSH_FAIL_STAGE",
                "STEP1_FINAL_PUSH_FAIL"):
        env.pop(key, None)
    env.update(PATH=f"{bin_dir}:{env['PATH']}",
               STEP1_FAKE_SCENARIO=str(scenario_file),
               STEP1_FAKE_STATE=str(state),
               STEP1_FAKE_INSTALL=str(work / "install"),
               CLAUDE_CONFIG_DIR=str(root / "stray-config"))
    env.update(faults or {})
    return {"work": work, "remote": remote, "run_dir": run_dir,
            "state": state, "settings": settings_file, "env": env,
            "root": root, "scenario": scenario_file}


def set_camera(ctx: dict, **values) -> None:
    data = json.loads(ctx["scenario"].read_text())
    data.setdefault("camera", {}).update(values)
    ctx["scenario"].write_text(json.dumps(data, indent=2))


# --- Helpers ------------------------------------------------------------------


class Checks:
    def __init__(self) -> None:
        self.results: list[tuple[bool, str, str]] = []

    def check(self, ok, name: str, detail: str = "") -> None:
        self.results.append((bool(ok), name, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}"
              + (f"  [{detail}]" if detail else ""), flush=True)


def runner_command(ctx: dict) -> list[str]:
    return ["python3", str(ctx["work"] / HARNESS / "runner" / "run.py"),
            "--settings", str(ctx["settings"])]


def run_once(ctx: dict, label: str) -> int:
    print(f"\n=== {ctx['root'].name}: {label} ===", flush=True)
    result = subprocess.run(runner_command(ctx), cwd=ctx["work"],
                            env=ctx["env"], capture_output=True, text=True)
    log = ctx["root"] / f"{label.split()[0]}.log"
    log.write_text(result.stdout + result.stderr)
    tail = (result.stdout + result.stderr).strip().splitlines()[-1:]
    print(f"exit {result.returncode}; last line: {tail}", flush=True)
    return result.returncode


def interrupt(ctx: dict, label: str, marker: str, sig: int) -> tuple[int, str]:
    """Starts the runner, waits for a marker file, and sends a signal."""
    print(f"\n=== {ctx['root'].name}: {label} ===", flush=True)
    log = open(ctx["root"] / f"{label.split()[0]}.log", "w")
    process = subprocess.Popen(runner_command(ctx), cwd=ctx["work"],
                               env=ctx["env"], stdout=log,
                               stderr=subprocess.STDOUT)
    path = ctx["state"] / marker
    deadline = time.time() + 60
    while not path.exists() and time.time() < deadline:
        time.sleep(0.1)
    content = path.read_text() if path.exists() else ""
    process.send_signal(sig)
    code = process.wait(timeout=60)
    print(f"exit {code} after {signal.Signals(sig).name}", flush=True)
    return code, content


def state_of(ctx: dict) -> dict:
    return json.loads((ctx["run_dir"] / "state.json").read_text())


def outcomes(state: dict, stage: str) -> list:
    return [a["outcome"] for a in state["stages"][stage]["attempts"]]


def remote_head(ctx: dict) -> str:
    return git("rev-parse", BRANCH, cwd=ctx["remote"]).strip()


def local_head(ctx: dict) -> str:
    return git("rev-parse", "HEAD", cwd=ctx["work"]).strip()


def committed(ctx: dict, rel: str, ref: str = "HEAD") -> str:
    result = subprocess.run([REAL_GIT, "show", f"{ref}:{rel}"], cwd=ctx["work"],
                            capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def touched_paths(ctx: dict) -> set[str]:
    base = git("rev-list", "--max-parents=0", "HEAD", cwd=ctx["work"]).strip()
    return set(git("log", "--format=", "--name-only", f"{base}..HEAD",
                   cwd=ctx["work"]).split())


def outside_paths(ctx: dict) -> list[str]:
    return sorted(p for p in touched_paths(ctx)
                  if p not in ALLOWED and not p.startswith(OUT + "/"))


def one_commit_per_attempt(ctx: dict) -> bool:
    lines = git("log", "--format=%(trailers:key=Step1-Stage,valueonly)"
                "%(trailers:key=Step1-Attempt,valueonly)", cwd=ctx["work"])
    pairs = [" ".join(chunk.split()) for chunk in lines.split("\n\n")
             if chunk.strip()]
    return len(pairs) == len(set(pairs))


def camera_features(ctx: dict) -> dict:
    return json.loads((ctx["state"] / "camera.json").read_text())["features"]


def camera_view(ctx: dict) -> dict:
    """Returns the values that the fake camera reports for each feature."""
    raw = camera_features(ctx)
    # ExposureMode and ExposureAuto are only read, so the baseline omits them.
    view = {k: v for k, v in raw.items()
            if "@" not in k and k not in ("ExposureMode", "ExposureAuto")}
    view["TriggerMode"] = raw["TriggerMode@FrameStart"]
    if not raw["AcquisitionFrameRateEnable"]:
        view["AcquisitionFrameRate"] = min(69.71556091308594,
                                           1e6 / raw["ExposureTime"])
    return view


def lines_of(ctx: dict, name: str) -> list[str]:
    path = ctx["state"] / name
    return path.read_text().splitlines() if path.exists() else []


def common_end_checks(c: Checks, ctx: dict, name: str) -> None:
    outside = outside_paths(ctx)
    c.check(not outside, f"{name}: commits touch only step 1 and output paths",
            f"outside: {outside}")
    c.check(one_commit_per_attempt(ctx),
            f"{name}: each stage attempt has at most one checkpoint commit")
    c.check(not pids_named("vimbax_camera_node"),
            f"{name}: no driver process is left")
    c.check(not lines_of(ctx, "violations.log"),
            f"{name}: no status call between the TriggerMode write and the "
            f"save", "; ".join(lines_of(ctx, "violations.log"))[:200])
    status = git("status", "--porcelain", cwd=ctx["work"]).strip()
    c.check(status == "", f"{name}: the worktree is clean", status[:200])


def classifier_checks(c: Checks) -> None:
    base = time.time()
    samples = {
        "claude epoch": (f"Claude AI usage limit reached|{int(base) + 3600}",
                         "quota", float(int(base) + 3600)),
        "claude reset clock": (
            "You've hit your session limit · resets 3am (America/Chicago)",
            "quota", "future"),
        "codex try again": (
            "You've hit your usage limit. ... or try again at "
            "Nov 23rd, 2026 3:45 AM.", "quota", "future-or-now"),
        "codex usage_limit_reached": ("error: usage_limit_reached", "quota",
                                      None),
        "claude overload": ("API Error: 529 overloaded_error", "transient",
                            None),
        "codex disconnect": ("stream disconnected before completion",
                             "transient", None),
        "unknown": ("API Error: 400 invalid_request_error", "error", None),
    }
    for name, (text, expected, reset) in samples.items():
        stdout = json.dumps({"type": "result", "subtype": "success",
                             "is_error": True, "result": text})
        kind, _ = runner.classify("claude", 1, stdout, "", False, 60)
        parsed = runner.parse_reset(text, base)
        ok = kind == expected
        if reset == "future":
            ok = ok and parsed is not None and parsed > base
        elif reset == "future-or-now":
            ok = ok and parsed is not None and parsed >= base
        elif isinstance(reset, float):
            ok = ok and parsed == reset
        c.check(ok, f"classifier: {name} -> {expected}", f"got {kind}")


def parser_checks(c: Checks) -> None:
    import rig
    reply = ("vimbax_camera_msgs.srv.FeatureBoolGet_Response(value=True, "
             "error=vimbax_camera_msgs.msg.Error(code=0, text=''))")
    c.check(rig.parse_value("bool", rig.ERROR_RE.sub("error=_", reply)) is True,
            "parser: a bool reply with the value first")
    reply = ("vimbax_camera_msgs.srv.FeatureEnumGet_Response(error=vimbax_"
             "camera_msgs.msg.Error(code=0, text='a, value=x'), "
             "value='Mono8')")
    c.check(rig.parse_value("enum", rig.ERROR_RE.sub("error=_", reply))
            == "Mono8", "parser: an error text with a comma and 'value='")
    c.check(rig.ERROR_RE.search(
        "error=vimbax_camera_msgs.msg.Error(code=-6, text='x')").group(1)
        == "-6", "parser: a negative error code")


# --- Main scenario ------------------------------------------------------------


def main_scenario(root: Path, c: Checks) -> None:
    scenario = {"stages": {
        "implement": {"attempts": ["sleep:60", "transient", "ok"],
                      "bugs": ["use_ros_time", "plugins"]},
        "repair-1": {"attempts": ["quota-epoch:2", "quota-epoch:4", "ok"],
                     "bugs": ["plugins"]},
        "review": {"attempts": ["quota-noreset", "ok"]},
    }, "camera": {"pause_after_part_a": 5}}
    ctx = setup(root, scenario, faults={
        "STEP1_CRASH_STAGE": "review", "STEP1_PUSH_FAIL_STAGE": "settings",
        "STEP1_FINAL_PUSH_FAIL": "1"})
    name = "main"

    code, orphan = interrupt(ctx, "run0 (Ctrl-C while implement runs)",
                             "implement.sleeping", signal.SIGINT)
    state = state_of(ctx)
    orphan = int(orphan)
    c.check(code != 0 and state["stages"]["implement"]["status"] == "running"
            and Path(f"/proc/{orphan}").exists(),
            "main: Ctrl-C stops the runner and leaves its agent behind",
            f"exit {code}, agent {orphan}")

    code = run_once(ctx, "run1 (to the crash after the review commit)")
    state = state_of(ctx)
    c.check(not Path(f"/proc/{orphan}").exists()
            and outcomes(state, "implement") == ["interrupted", "transient",
                                                 "ok"],
            "main: the restart stops the old agent and runs the stage again",
            str(outcomes(state, "implement")))
    attempts = state["stages"]["implement"]["attempts"]
    c.check(attempts[2]["started"] - attempts[1]["ended"] >= 0.2,
            "main: a transient retry waits for the backoff")
    order = state["order"]
    c.check(order[:4] == ["implement", "build-1", "repair-1", "build-3"]
            and state["stages"]["build-1"]["result"]["passed"] is False,
            "main: a failed test adds a repair stage and a new build",
            " ".join(order))
    build_log = committed(
        ctx, f"{OUT}/colcon/build-1-a1/commands.log")
    c.check("camera.yaml has no use_ros_time" in build_log,
            "main: the failing build log is committed")
    repair = state["stages"]["repair-1"]["attempts"]
    c.check([a["outcome"] for a in repair] == ["quota", "quota", "ok"]
            and [a["account"] for a in repair] == ["work", "personal", "work"]
            and repair[0]["resume_at"] <= repair[2]["started"]
            < repair[1]["resume_at"],
            "main: with both accounts paused the stage waits for the "
            "earliest reset",
            " ".join(a["account"] for a in repair))
    dirs = [line.split()[4] for line in lines_of(ctx, "agents.log")
            if line.split()[1] == "claude"]
    c.check(all(d == "-" or d.endswith("claude-work") for d in dirs)
            and "stray-config" not in " ".join(dirs),
            "main: each Claude launch gets the config folder of its account")
    c.check(outcomes(state, "review") == ["quota", "ok"]
            and state["stages"]["review"]["tool"] == "codex",
            "main: a Codex quota error without a reset time backs off")
    c.check(code == -9 and state["stages"]["review"]["status"] == "importing",
            "main: the crash leaves a local commit and a stale state",
            f"exit {code}")
    c.check(any(e["kind"] == "push" for e in state["errors"]),
            "main: a failed push is recorded as an error")
    xml = committed(ctx, XML)
    c.check("<Feature Name=\"AcquisitionFrameRate\">30.0</Feature>" in xml
            and "ExposureTime\">4999.455" in xml,
            "main: the settings file from the camera is committed",
            xml[:80].replace("\n", " "))
    calls = [line.split(" ", 1)[1] for line in lines_of(ctx, "calls.log")]
    writes = [c_ for c_ in calls if "_set" in c_.split()[0]]
    c.check(any("settings/save" in c_ and "/run/attempts/settings/" in c_
                for c_ in calls),
            "main: settings/save writes only inside the run folder")
    c.check(all(json.loads(w.split(" ", 1)[1])["feature_name"]
                in runner.rig.FEATURES for w in writes),
            "main: each feature write is on the allow-list",
            f"{len(writes)} writes")
    prompt = (ctx["state"] / "implement.prompt.md").read_text()
    c.check("Do not start a camera driver" in prompt
            and "Files that you may change" in prompt,
            "main: the agent prompt holds the camera rules and the file list")

    code, _ = interrupt(ctx, "run2 (SIGKILL during part A)",
                        "part-a-written", signal.SIGKILL)
    state = state_of(ctx)
    c.check(state["stages"]["review"]["status"] == "done"
            and len([l for l in git("log", "--format=%B", cwd=ctx["work"])
                     .splitlines() if l == "Step1-Stage: review"]) == 1,
            "main: recovery adopts the review commit without a second commit")
    left = pids_named("vimbax_camera_node")
    c.check(code == -9 and state["camera"] is not None and left
            and camera_features(ctx)["ExposureTime"] == PART_A_EXPOSURE,
            "main: the kill leaves a driver and the part A values",
            f"drivers {left}")

    code = run_once(ctx, "run3 (recovery, rig repair, final push fails)")
    state = state_of(ctx)
    cleanup = sorted((ctx["run_dir"] / "attempts" / "rig-1" / "1").glob(
        "cleanup-*/camera-cleanup.json"))
    report = json.loads(cleanup[0].read_text()) if cleanup else {}
    c.check(report.get("restore", {}).get("restored")
            and "ExposureTime" in report["restore"]["restored"],
            "main: the restart restores the camera from the baseline",
            json.dumps(report.get("restore"))[:160])
    c.check(outcomes(state, "rig-1") == ["interrupted", "ok"]
            and state["stages"]["rig-1"]["result"]["failed_check"] == "E6",
            "main: the rerun of rig-1 fails exit check 6 on the plugin filter")
    c.check("repair-2" in state["order"] and "rig-2" in state["order"]
            and state["stages"]["rig-2"]["result"]["passed"],
            "main: a repairable rig failure adds a repair, a build, and a rig "
            "check")
    results = json.loads(committed(ctx, f"{OUT}/rig/rig-1-a2/results.json")
                         or "{}")
    c.check(results.get("passed") is False,
            "main: the failed rig attempt logs are committed")
    rig_dir = f"{OUT}/rig/rig-2-a1"
    control = committed(ctx, f"{rig_dir}/driver_control.log")
    driver_b = committed(ctx, f"{rig_dir}/driver_b.log")
    c.check("Loading settings from file /nonexistent.xml" in control
            and "Initialization done!" in driver_b
            and "Loading settings" not in driver_b,
            "main: the part A logs are committed with the expected lines")
    text = committed(ctx, f"{OUT}/report.md")
    exit_rows = [line for line in text.splitlines()
                 if line.startswith("| ") and line.split("|")[1].strip()
                 in [str(i) for i in range(1, 11)]
                 and "PASS" in line]
    c.check("| Part A step 11 |" in text and str(PART_A_EXPOSURE) in text
            and "Contradicted" in text,
            "main: the report lists the part A rounding as a contradiction")
    c.check(len(exit_rows) >= 10 and "| P11 |" in text and "Holds" in text,
            "main: the report shows each exit check item as PASS and P11",
            f"{len(exit_rows)} PASS rows")
    baseline = json.loads((ctx["run_dir"] / "camera-baseline.json")
                          .read_text())
    view = camera_view(ctx)
    c.check(view == baseline and view["ExposureTime"] == ON_EXPOSURE
            and view["AcquisitionFrameRateEnable"] is False,
            "main: the camera ends the run with the baseline values",
            json.dumps(view))
    status = (ctx["run_dir"] / "final-status.txt").read_text()
    c.check(code == 3 and state["final_push"] == "failed"
            and "complete locally" in status,
            "main: a failed final push exits with code 3", f"exit {code}")
    retry = next(line.strip() for line in status.splitlines()
                 if line.strip().startswith("git -C "))
    subprocess.run(retry, shell=True, check=True, capture_output=True,
                   env=ctx["env"])
    final = state["final_commit"]
    c.check(remote_head(ctx) == final,
            "main: the printed retry command pushes the final commit")
    before = local_head(ctx)
    code = run_once(ctx, "run4 (rerun after completion)")
    state = state_of(ctx)
    c.check(code == 0 and local_head(ctx) == before
            and state["final_push"] == "verified",
            "main: a rerun after completion only checks the push",
            f"exit {code}")
    c.check("Status: complete" in committed(ctx, f"{OUT}/RUN.md"),
            "main: RUN.md records the complete run")
    common_end_checks(c, ctx, name)


# --- Failure scenarios --------------------------------------------------------


def forbidden_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"stages": {"implement": {
        "attempts": ["forbidden", "ok"]}}}, accounts=False)
    code = run_once(ctx, "run1 (a task writes forbidden paths)")
    state = state_of(ctx)
    run_md = committed(ctx, f"{OUT}/RUN.md")
    c.check(code == 2 and state["stages"]["implement"]["status"] == "failed"
            and "unexpected output src/venimapping_camera/CMakeLists.txt"
            in run_md and f"unexpected output {XML}" in run_md,
            "forbidden: a write outside the allowed paths stops the run",
            f"exit {code}")
    c.check(not committed(ctx, f"{PKG}/config/acquisition_profile.yaml")
            and not (ctx["work"] / "src/venimapping_camera").exists(),
            "forbidden: nothing from the stopped stage is imported")
    c.check("accounts" not in json.dumps(state["stages"]["implement"]
                                         ["attempts"]),
            "forbidden: without accounts the attempts carry no account")
    code = run_once(ctx, "run2 (resume after the stop)")
    state = state_of(ctx)
    c.check(code == 0 and state["status"] == "complete"
            and outcomes(state, "implement") == ["error", "ok"],
            "forbidden: the resume runs the stage again and completes",
            f"exit {code}")
    common_end_checks(c, ctx, "forbidden")


def init_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"camera": {"init_never": True}}, accounts=False)
    code = run_once(ctx, "run1 (the driver never prints the init line)")
    state = state_of(ctx)
    run_md = committed(ctx, f"{OUT}/RUN.md")
    c.check(code == 2 and "status 124" in run_md
            and "powered and on the network" in run_md,
            "init: an init wait at its limit stops the run with a clear reason",
            f"exit {code}")
    log = committed(ctx, f"{OUT}/settings/settings-a1/driver_settings.log")
    c.check("Initializing camera" in log and "Initialization done" not in log,
            "init: the driver log of the failed wait is committed")
    c.check(not pids_named("vimbax_camera_node") and state["camera"] is None,
            "init: the runner stops the driver and closes the camera stage")
    c.check(not (ctx["state"] / "camera.json").exists()
            or camera_features(ctx)["ExposureTime"] == ON_EXPOSURE,
            "init: the camera is unchanged")
    set_camera(ctx, init_never=False)
    code = run_once(ctx, "run2 (resume with a working driver)")
    state = state_of(ctx)
    c.check(code == 0 and outcomes(state, "settings") == ["ok", "ok"]
            and state["stages"]["settings"]["result"]["passed"],
            "init: the resume runs the settings stage again and completes",
            f"exit {code}")
    common_end_checks(c, ctx, "init")


def rigfail_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"camera": {"reject_part_a": True}}, accounts=False)
    code = run_once(ctx, "run1 (the camera does not take the part A values)")
    state = state_of(ctx)
    c.check(code == 2 and state["stages"]["rig-1"]["status"] == "failed"
            and "repair-1" not in state["order"]
            and "did not take" in state["stop_reason"],
            "rigfail: a failed part A step 11 stops the run with no repair",
            state.get("stop_reason", "")[:120])
    c.check(camera_features(ctx)["ExposureTime"] == ON_EXPOSURE
            and not pids_named("vimbax_camera_node"),
            "rigfail: the camera is restored and no driver is left")
    decoy = subprocess.Popen(
        ["python3", str(DRYRUN_DIR / "vimbax_camera_node")],
        env={**ctx["env"], "STEP1_DECOY": "1"}, start_new_session=True)
    time.sleep(0.5)
    set_camera(ctx, reject_part_a=False)
    code = run_once(ctx, "run2 (a driver that the runner did not start)")
    state = state_of(ctx)
    c.check(code == 2 and decoy.poll() is None
            and "already running" in state["stop_reason"],
            "rigfail: a foreign driver stops the camera stage and stays alive",
            f"exit {code}")
    decoy.terminate()
    decoy.wait()
    code = run_once(ctx, "run3 (resume without the foreign driver)")
    state = state_of(ctx)
    c.check(code == 0 and state["stages"]["rig-1"]["result"]["passed"],
            "rigfail: the resume runs the rig check again and completes",
            f"exit {code}")
    common_end_checks(c, ctx, "rigfail")


def p11_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"camera": {"p11_resets": True}}, accounts=False)
    code = run_once(ctx, "run1 (the camera resets on each driver start)")
    state = state_of(ctx)
    text = committed(ctx, f"{OUT}/report.md")
    p11 = state["stages"]["rig-1"]["result"]["facts"]["p11"]
    c.check(code == 0 and p11["holds"] is False
            and "| P11 |" in text and "Contradicted" in text
            and "P11 is contradicted" in text,
            "p11: a contradicted P11 is recorded and the run completes",
            p11["detail"])
    common_end_checks(c, ctx, "p11")


def restore_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"camera": {"fail_set_once": [["ExposureTime", ON_EXPOSURE]]}},
                accounts=False)
    code = run_once(ctx, "run1 (the restore write fails once)")
    state = state_of(ctx)
    c.check(code == 2 and state["camera"] and state["camera"].get("dirty")
            and "cleanup could not be verified" in state["stop_reason"],
            "restore: an unverified restore stops the run", f"exit {code}")
    c.check(not pids_named("vimbax_camera_node"),
            "restore: the driver is stopped even when the restore fails")
    code = run_once(ctx, "run2 (resume retries the cleanup first)")
    state = state_of(ctx)
    c.check(code == 0 and camera_features(ctx)["ExposureTime"] == ON_EXPOSURE
            and outcomes(state, "settings") == ["error", "ok"],
            "restore: the resume restores the camera and completes",
            f"exit {code}")
    common_end_checks(c, ctx, "restore")


def decoy_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"stages": {"fix": {"attempts": ["decoy", "ok"]}}},
                accounts=False)
    code = run_once(ctx, "run1 (an agent starts a driver)")
    state = state_of(ctx)
    decoy = int((ctx["state"] / "decoy.pid").read_text())
    c.check(code == 2 and Path(f"/proc/{decoy}").exists()
            and "camera driver is running after the agent task"
            in state["stop_reason"],
            "decoy: a driver after an agent task stops the run", f"exit {code}")
    os.kill(decoy, signal.SIGTERM)
    time.sleep(0.5)
    code = run_once(ctx, "run2 (resume)")
    c.check(code == 0, "decoy: the resume completes", f"exit {code}")
    common_end_checks(c, ctx, "decoy")


def xml_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"camera": {"xml_denied": True}}, accounts=False)
    code = run_once(ctx, "run1 (the saved file holds an IP feature)")
    state = state_of(ctx)
    c.check(code == 2 and "GevPersistentIPAddress" in state["stop_reason"],
            "xml: a denied feature in the saved file stops the run",
            state.get("stop_reason", "")[:120])
    c.check(not committed(ctx, XML) and "GevPersistentIPAddress" in committed(
        ctx, f"{OUT}/settings/settings-a1/camera_settings.saved.xml"),
        "xml: the file is kept in the logs and not put in the package")
    c.check("xml_denied_policy" in state.get("stop_action", "")
            and "strip" in state.get("stop_action", ""),
            "xml: the stop says how to choose the policy",
            state.get("stop_action", "")[:120])
    calls = [line for line in lines_of(ctx, "launches.log")]
    c.check(not any("camera_settings.xml" in line for line in calls),
            "xml: no driver loaded the file")
    common_end_checks(c, ctx, "xml")


def strip_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"camera": {"xml_denied": True},
                       "camera_settings": {"xml_denied_policy": "strip"}},
                accounts=False)
    code = run_once(ctx, "run1 (strip the IP feature from the package copy)")
    c.check(code == 0, "strip: the run completes", f"exit {code}")
    installed = committed(ctx, XML)
    c.check(bool(installed) and "GevPersistentIPAddress" not in installed
            and "ExposureTime" in installed,
            "strip: the package copy has the profile and no IP feature")
    c.check("GevPersistentIPAddress" in committed(
        ctx, f"{OUT}/settings/settings-a1/camera_settings.saved.xml"),
        "strip: the saved file in the logs is unchanged")
    report_text = committed(ctx, f"{OUT}/report.md")
    c.check("Policy `strip`" in report_text
            and "GevPersistentIPAddress" in report_text,
            "strip: the report names the policy and the removed feature")
    common_end_checks(c, ctx, "strip")


def keep_scenario(root: Path, c: Checks) -> None:
    real = json.loads((RUNNER_DIR / "settings.json").read_text())["camera"]
    ctx = setup(root, {"camera": {"xml_denied": True},
                       "camera_settings": {
                           "xml_denied_policy": "keep",
                           "xml_keep_features": real["xml_keep_features"],
                           "xml_keep_selectors": real["xml_keep_selectors"]}},
                accounts=False)
    code = run_once(ctx, "run1 (keep only the listed features)")
    c.check(code == 0, "keep: the run completes", f"exit {code}")
    installed = committed(ctx, XML)
    c.check(bool(installed) and "ExposureTime" in installed
            and "ExposureAuto" in installed
            and "GevPersistentIPAddress" not in installed
            and "DeviceLinkThroughputLimit" not in installed
            and "DeviceModelName" not in installed,
            "keep: the package copy has the listed features and no other")
    saved = committed(ctx, f"{OUT}/settings/settings-a1/"
                           f"camera_settings.saved.xml")
    c.check("GevPersistentIPAddress" in saved
            and "DeviceLinkThroughputLimit" in saved,
            "keep: the saved file in the logs is unchanged")
    report_text = committed(ctx, f"{OUT}/report.md")
    c.check("Policy `keep`" in report_text
            and "| 9b |" in report_text
            and "`ExposureAuto`" in report_text,
            "keep: the report names the policy and the kept features")
    rig = json.loads(committed(ctx, f"{OUT}/rig/rig-1-a1/results.json")
                     or "{}")
    found = {x["id"]: x for x in rig.get("checks", [])}
    c.check(found.get("E9b", {}).get("passed")
            and "ExposureAuto" in found["E9b"]["detail"],
            "keep: exit check 9b reads the kept features back",
            found.get("E9b", {}).get("detail", "no E9b")[:120])
    common_end_checks(c, ctx, "keep")


def exhaust_scenario(root: Path, c: Checks) -> None:
    ctx = setup(root, {"stages": {
        "implement": {"bugs": ["plugins"]},
        "repair-1": {"attempts": ["nochange"]}}}, accounts=False)
    code = run_once(ctx, "run1 (the repair changes no file)")
    state = state_of(ctx)
    c.check(code == 2 and "changed no file" in state["stop_reason"]
            and state["stages"]["repair-1"]["status"] == "done",
            "exhaust: a repair with no change stops the run", f"exit {code}")
    code = run_once(ctx, "run2 (resume reruns the checks)")
    state = state_of(ctx)
    c.check(code == 2 and state["stages"]["rig-2"]["status"] == "failed"
            and "repair rounds are used" in state["stop_reason"],
            "exhaust: a second rig failure stops when the repairs are used",
            state.get("stop_reason", "")[:120])
    common_end_checks(c, ctx, "exhaust")


SCENARIOS = {
    "main": main_scenario, "forbidden": forbidden_scenario,
    "init": init_scenario, "rigfail": rigfail_scenario, "p11": p11_scenario,
    "restore": restore_scenario, "decoy": decoy_scenario, "xml": xml_scenario,
    "strip": strip_scenario, "keep": keep_scenario,
    "exhaust": exhaust_scenario,
}


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    if root.exists() and any(root.iterdir()):
        sys.exit(f"{root} must be empty")
    root.mkdir(parents=True, exist_ok=True)
    chosen = sys.argv[2:] or list(SCENARIOS)
    c = Checks()
    classifier_checks(c)
    parser_checks(c)
    for name in chosen:
        if pids_named("vimbax_camera_node"):
            sys.exit("a vimbax_camera_node process runs; the dry run will not "
                     "start")
        SCENARIOS[name](root / name, c)

    failed = [r for r in c.results if not r[0]]
    summary = root / "dryrun-report.md"
    summary.write_text("\n".join(
        f"- {'PASS' if ok else 'FAIL'} {name}" + (f" ({d})" if d else "")
        for ok, name, d in c.results) + "\n")
    print(f"\n{len(c.results) - len(failed)}/{len(c.results)} checks passed. "
          f"Report: {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
