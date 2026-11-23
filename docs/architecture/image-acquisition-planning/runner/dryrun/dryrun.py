# ------------------------------------------------------------------------------
#  Filename: dryrun.py
#
#  Purpose:  Runs the planning runner against a throwaway repository, remote,
#            and driver checkout with stub tools, and checks each failure path.
#
#  Usage:    python3 dryrun.py <empty scratch directory>
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# --- Configuration ------------------------------------------------------------

DRYRUN_DIR = Path(__file__).resolve().parent
RUNNER_DIR = DRYRUN_DIR.parent
PLANNING_REL = "docs/architecture/image-acquisition-planning"
V1_REL = "docs/architecture/image-acquisition-design-v1.md"
V2_REL = "docs/architecture/image-acquisition-design-v2.md"
BRANCH = "plans/dryrun"
REAL_GIT = shutil.which("git")
CRASH_TASK = "fix-codex-r1"
PUSH_FAIL_TASK = "recheck-claude-r1"

sys.dont_write_bytecode = True
sys.path.insert(0, str(RUNNER_DIR))
import run as runner  # noqa: E402

GIT_WRAPPER = f"""#!/bin/bash
real={REAL_GIT}
state="$PLANRUN_FAKE_STATE"
if [ "$1" = push ] && [ ! -f "$state/push-failed" ] && \\
   "$real" log -1 --format=%B | \\
     grep -qx "Planning-Task: $PLANRUN_PUSH_FAIL_TASK"; then
  touch "$state/push-failed"
  exec "$real" push "$state/no-such-remote.git" HEAD:refs/heads/x
fi
if [ "$1" = push ] && [ ! -f "$state/final-push-failed" ] && \\
   "$real" log -1 --format=%B | grep -qx "Planning-Event: run-complete"; then
  touch "$state/final-push-failed"
  exec "$real" push "$state/no-such-remote.git" HEAD:refs/heads/x
fi
"$real" "$@"
rc=$?
if [ "$1" = commit ] && [ $rc -eq 0 ] && [ ! -f "$state/crashed" ] && \\
   "$real" log -1 --format=%B | \\
     grep -qx "Planning-Task: $PLANRUN_CRASH_TASK"; then
  touch "$state/crashed"
  kill -9 $PPID
fi
exit $rc
"""

FEATURES = [{"name": "ExposureTime", "type": "float"}]


def scenario() -> dict:
    disputes = [
        {"id": "dispute-position-claude-d1", "template": "dispute-position",
         "tool": "claude", "params": {"issue": "d1"},
         "blocks": ["register-final"]},
        {"id": "dispute-position-codex-d1", "template": "dispute-position",
         "tool": "codex", "params": {"issue": "d1"},
         "blocks": ["register-final"]},
        {"id": "dispute-judge-claude-d1", "template": "dispute-judge",
         "tool": "claude", "params": {"issue": "d1"},
         "deps": ["dispute-position-claude-d1", "dispute-position-codex-d1"],
         "blocks": ["register-final"]},
        {"id": "dispute-judge-codex-d1", "template": "dispute-judge",
         "tool": "codex", "params": {"issue": "d1"},
         "deps": ["dispute-position-claude-d1", "dispute-position-codex-d1"],
         "blocks": ["register-final"]},
    ]
    round_one = [
        {"id": "fix-codex-r1", "template": "fix", "tool": "codex",
         "params": {"round": "1", "issues": "i1", "sections": "data-plane"},
         "blocks": ["prose"]},
        {"id": "recheck-claude-r1", "template": "recheck", "tool": "claude",
         "params": {"round": "1", "issues": "i1", "sections": "data-plane"},
         "deps": ["fix-codex-r1"], "blocks": ["prose"]},
        {"id": "camera-c2", "template": "camera-check", "tool": "claude",
         "params": {"check": "c2"},
         "camera": {"question": "dry run question two",
                    "features": FEATURES},
         "blocks": ["prose"]},
        {"id": "integrate-2", "template": "integrate", "tool": "claude",
         "params": {"round": "2"},
         "deps": ["recheck-claude-r1", "camera-c2"], "blocks": ["prose"]},
    ]
    return {
        "fail_restore_calls": [2],
        "tasks": {
            "trace-codex": {"attempts": ["transient-codex", "transient-codex",
                                         "ok"]},
            "reconcile": {"emit": {"tasks": [
                {"id": "camera-c1", "template": "camera-check",
                 "tool": "codex", "params": {"check": "c1"},
                 "camera": {"question": "dry run question one",
                            "features": FEATURES},
                 "blocks": ["positions-claude", "positions-codex"]}]}},
            "register": {"emit": {"tasks": disputes}},
            "dispute-judge-claude-d1": {"attempts": ["unrecognized", "ok"]},
            "camera-c1": {"attempts": ["stream:8"]},
            "camera-c2": {"attempts": ["ok", "decoy", "ok"]},
            "draft-codex": {"attempts": ["quota-tryagain:5", "ok"]},
            "review-codex": {"attempts": ["transient-codex"] * 4 + ["ok"]},
            "integrate-1": {"emit": {"progress": {"closed": 2},
                                     "tasks": round_one}},
            "integrate-2": {"emit": {"progress": {"closed": 1},
                                     "tasks": []}},
            "prose": {"attempts": ["quota-epoch:3", "ok"]},
            "meaning-check": {"attempts": ["quota-noreset", "ok"]},
        },
    }


# --- Setup --------------------------------------------------------------------


def git(*args: str, cwd: Path) -> str:
    return subprocess.run([REAL_GIT, *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


def setup(root: Path) -> dict:
    remote = root / "remote.git"
    work = root / "work"
    driver = root / "driver"
    state = root / "fake-state"
    run_dir = root / "run"
    bin_dir = root / "bin"
    for path in (work, driver, state, bin_dir):
        path.mkdir(parents=True)

    git("init", "--quiet", "--bare", str(remote), cwd=root)
    git("init", "--quiet", "-b", BRANCH, cwd=work)
    git("config", "user.name", "Dry Run", cwd=work)
    git("config", "user.email", "dryrun@localhost", cwd=work)
    shutil.copytree(RUNNER_DIR.parent, work / PLANNING_REL,
                    ignore=shutil.ignore_patterns("__pycache__", "RUN.md"))
    (work / V1_REL).write_text("# v1 stand-in\n")
    git("add", ".", cwd=work)
    git("commit", "--quiet", "-m", "dry run base", cwd=work)
    git("remote", "add", "origin", str(remote), cwd=work)
    git("push", "--quiet", "-u", "origin", BRANCH, cwd=work)

    git("init", "--quiet", cwd=driver)
    (driver / "driver.cpp").write_text("// stand-in\n")
    git("add", ".", cwd=driver)
    git("-c", "user.name=d", "-c", "user.email=d@d", "commit", "--quiet",
        "-m", "driver", cwd=driver)

    with open(work / V1_REL, "a") as handle:
        handle.write("Unrelated edit by Logan.\n")
    (work / "notes-unrelated.md").write_text("Unrelated untracked notes.\n")

    wrapper = bin_dir / "git"
    wrapper.write_text(GIT_WRAPPER)
    wrapper.chmod(0o755)
    env_script = root / "camera-env.sh"
    env_script.write_text("true\n")
    scenario_file = root / "scenario.json"
    scenario_file.write_text(json.dumps(scenario(), indent=2))

    agent = ["python3", str(DRYRUN_DIR / "fake_agent.py")]
    settings = {
        "run_dir": str(run_dir), "remote": "origin", "branch": BRANCH,
        "read_roots": [str(driver)], "driver_source": str(driver),
        "claude": {"command": [*agent, "claude"], "model": None,
                   "timeout_s": 60},
        "codex": {"command": [*agent, "codex"], "timeout_s": 60},
        "transient_backoff_s": [0.2, 0.4, 0.8],
        "quota_backoff_s": [1, 2, 4],
        "quota_margin_s": 0,
        "max_sleep_chunk_s": 1,
        "max_integrate_rounds": 8,
        "camera": {
            "env_script": str(env_script), "namespace": "/vimbax_camera",
            "launch": ["python3", str(DRYRUN_DIR / "vimbax_camera_node")],
            "guard": ["python3", str(DRYRUN_DIR / "fake_guard.py")],
            "driver_process": "vimbax_camera_node", "ready_timeout_s": 5,
            "task_timeout_s": 60, "max_stream_s": 3,
            "stream_poll_s": 0.25, "stream_stop_margin_s": 0.5,
        },
    }
    settings_file = root / "settings.json"
    settings_file.write_text(json.dumps(settings, indent=2))
    env = dict(os.environ)
    env.update(PATH=f"{bin_dir}:{env['PATH']}",
               PLANRUN_FAKE_SCENARIO=str(scenario_file),
               PLANRUN_FAKE_STATE=str(state),
               PLANRUN_FAKE_RUN_DIR=str(run_dir),
               PLANRUN_CRASH_TASK=CRASH_TASK,
               PLANRUN_PUSH_FAIL_TASK=PUSH_FAIL_TASK)
    return {"work": work, "remote": remote, "run_dir": run_dir,
            "state": state, "settings": settings_file, "env": env,
            "driver": driver}


# --- Checks -------------------------------------------------------------------


class Checks:
    def __init__(self) -> None:
        self.results: list[tuple[bool, str, str]] = []

    def check(self, ok: bool, name: str, detail: str = "") -> None:
        self.results.append((bool(ok), name, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}"
              + (f"  [{detail}]" if detail else ""), flush=True)


def load_state(ctx: dict) -> dict:
    return json.loads((ctx["run_dir"] / "state.json").read_text())


def outcomes(state: dict, task: str) -> list:
    return [a["outcome"] for a in state["tasks"][task]["attempts"]]


def head_message(ctx: dict, ref: str = "HEAD") -> str:
    return git("log", "-1", "--format=%B", ref, cwd=ctx["work"])


def remote_head(ctx: dict) -> str:
    return git("rev-parse", BRANCH, cwd=ctx["remote"]).strip()


def local_head(ctx: dict) -> str:
    return git("rev-parse", "HEAD", cwd=ctx["work"]).strip()


def commits_for(ctx: dict, task: str) -> list[str]:
    return git("log", "--format=%H", f"--grep=^Planning-Task: {task}$",
               cwd=ctx["work"]).split()


def committed_file(ctx: dict, rel: str, ref: str = "HEAD") -> str:
    return git("show", f"{ref}:{rel}", cwd=ctx["work"])


def run_once(ctx: dict, label: str) -> int:
    print(f"\n=== {label} ===", flush=True)
    result = subprocess.run(
        ["python3", str(ctx["work"] / PLANNING_REL / "runner" / "run.py"),
         "--settings", str(ctx["settings"])],
        cwd=ctx["work"], env=ctx["env"], capture_output=True, text=True)
    log = ctx["run_dir"].parent / f"{label.split()[0]}.log"
    log.write_text(result.stdout + result.stderr)
    tail = (result.stdout + result.stderr).strip().splitlines()[-1:]
    print(f"exit {result.returncode}; last line: {tail}", flush=True)
    return result.returncode


def classifier_checks(c: Checks) -> None:
    base = time.time()
    samples = {
        "claude epoch": ("Claude AI usage limit reached|1795421110",
                         "quota", 1795421110.0),
        "claude reset clock": (
            "You've hit your session limit · resets 3am (America/Chicago)",
            "quota", "future"),
        "codex try again": (
            "You've hit your usage limit. ... or try again at "
            "Nov 23rd, 2026 3:45 AM.", "quota", "future-or-now"),
        "codex usage_limit_reached": (
            "error: usage_limit_reached", "quota", None),
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
        c.check(ok, f"classifier: {name} -> {expected}",
                f"got {kind}, reset {runner.stamp(parsed)}")


# --- Scenario -----------------------------------------------------------------


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    if root.exists() and any(root.iterdir()):
        sys.exit(f"{root} must be empty")
    root.mkdir(parents=True, exist_ok=True)
    ctx = setup(root)
    c = Checks()
    classifier_checks(c)

    code = run_once(ctx, "run1 (until the unrecognized error)")
    state = load_state(ctx)
    c.check(code == 2 and state["status"] == "stopped",
            "unrecognized error stops the run", f"exit {code}")
    c.check(outcomes(state, "dispute-judge-claude-d1") == ["error"],
            "unrecognized error is not retried",
            str(outcomes(state, "dispute-judge-claude-d1")))
    errors = [e for e in state["errors"] if e["kind"] == "task"]
    c.check(errors and "dry run unrecognized failure" in errors[-1]["detail"],
            "error details are saved in state.json")
    attempt_dir = Path(state["tasks"]["dispute-judge-claude-d1"]["attempts"][-1]
                       ["dir"])
    c.check((attempt_dir / "stdout.log").read_text().strip() != "",
            "the failed attempt keeps its logs", str(attempt_dir))
    c.check("Stop reason" in committed_file(ctx, f"{PLANNING_REL}/RUN.md")
            and remote_head(ctx) == local_head(ctx),
            "the stop record is committed and pushed")
    c.check(outcomes(state, "trace-codex") ==
            ["transient", "transient", "ok"],
            "transient errors retry and then succeed",
            str(outcomes(state, "trace-codex")))
    t_attempts = state["tasks"]["trace-codex"]["attempts"]
    c.check(t_attempts[1]["started"] - t_attempts[0]["ended"] >= 0.2 and
            t_attempts[2]["started"] - t_attempts[1]["ended"] >= 0.4,
            "transient retries wait for the backoff")
    for task in ("trace-codex", "positions-codex", "dispute-position-codex-d1"):
        text = committed_file(
            ctx, runner.fill("{P}/codex/" + {
                "trace-codex": "trace.md",
                "positions-codex": "positions.md",
                "dispute-position-codex-d1": "disputes/d1-position.md",
            }[task], {"P": PLANNING_REL}))
        c.check('Peer outputs visible: []' in text,
                f"{task} could not see the Claude output of its blind group")
    blind = [state["tasks"][t]["commit"] for t in ("trace-claude",
                                                   "trace-codex")]
    starts = [state["tasks"][t]["attempts"][-1]["start_commit"]
              for t in ("trace-claude", "trace-codex")]
    c.check(starts[0] == starts[1] and all(blind),
            "both traces started from the same checkpoint", starts[0][:10])
    cleanup = json.loads((Path(state["tasks"]["camera-c1"]["attempts"][-1]
                               ["dir"]) / "camera-cleanup.json").read_text())
    c.check(cleanup["stream_stopped"] and cleanup["features_restored"] is True
            and cleanup["driver_pids_left"] == [],
            "camera check c1 cleanup is verified", json.dumps(cleanup))
    c.check(not runner.pids_named("vimbax_camera_node"),
            "no stub driver is left after c1")
    c.check("c1" in committed_file(ctx, f"{PLANNING_REL}/camera-log.md"),
            "the runner records c1 in camera-log.md")
    started_log = (ctx["state"] / "stream-started.log").read_text()
    started = float(started_log.split()[0])
    stops = [float(x) for x in
             (ctx["state"] / "stream-stops.log").read_text().split()]
    lasted = stops[0] - started
    c1 = state["tasks"]["camera-c1"]["attempts"][-1]
    c.check(1.5 <= lasted <= 3.0,
            "the runner stops a stream before the 3 s stream limit",
            f"stream lasted {lasted:.2f} s, the agent kept it on for 8 s")
    c.check((ctx["state"] / "stream-on-at-end").read_text() == "False"
            and c1.get("stream", {}).get("limit_stops") == 1,
            "the stream was already off when the agent finished")

    code = run_once(ctx, "run2 (until transient retries run out)")
    state = load_state(ctx)
    c.check(state["tasks"]["dispute-judge-claude-d1"]["status"] == "done"
            and outcomes(state, "dispute-judge-claude-d1") == ["error", "ok"],
            "after a restart the failed task runs again and succeeds")
    c.check(code == 2 and outcomes(state, "review-codex") ==
            ["transient"] * 4,
            "transient retries stop after three retries",
            str(outcomes(state, "review-codex")))
    c.check(any(e["kind"] == "transient-exhausted" for e in state["errors"]),
            "the exhausted retries are recorded as an error")
    quota = state["tasks"]["draft-codex"]["attempts"]
    other = state["tasks"]["draft-claude"]["attempts"][-1]
    c.check(quota[0]["outcome"] == "quota" and quota[1]["outcome"] == "ok",
            "a recognized quota error pauses and resumes the task")
    c.check(quota[1]["started"] >= quota[0]["resume_at"],
            "the task resumes at the reported reset time",
            f"reset {runner.stamp(quota[0]['resume_at'])}, resumed "
            f"{runner.stamp(quota[1]['started'])}")
    c.check(quota[0]["ended"] <= other["started"] <= quota[1]["started"],
            "Claude continues its own task while Codex is paused")
    c.check(state["tasks"]["draft-codex"]["tool"] == "codex",
            "the paused task stays with the same tool")
    pause_commits = git("log", "--format=%H %s", cwd=ctx["work"]).splitlines()
    pause = [line.split()[0] for line in pause_commits
             if "record the codex quota pause" in line]
    pause_md = committed_file(ctx, f"{PLANNING_REL}/RUN.md", pause[0]) \
        if pause else ""
    c.check("paused until" in pause_md
            and "Unfinished: draft-codex" in pause_md,
            "the pause record names the paused task and the reset time")

    code = run_once(ctx, "run3 (crash after a local commit)")
    state = load_state(ctx)
    crash_commits = commits_for(ctx, CRASH_TASK)
    c.check(code == -9 and state["tasks"][CRASH_TASK]["status"] == "importing"
            and len(crash_commits) == 1,
            "the crash leaves a local commit and a stale state",
            f"exit {code}, status {state['tasks'][CRASH_TASK]['status']}")

    code = run_once(ctx, "run4 (recovery, push failure, camera cleanup)")
    state = load_state(ctx)
    c.check(state["tasks"][CRASH_TASK]["status"] == "done"
            and state["tasks"][CRASH_TASK]["commit"] == crash_commits[0]
            and commits_for(ctx, CRASH_TASK) == crash_commits,
            "recovery adopts the existing commit without a second commit")
    push_errors = [e for e in state["errors"] if e["kind"] == "push"]
    failed_commit = commits_for(ctx, PUSH_FAIL_TASK)
    c.check(push_errors and failed_commit,
            "a failed push is recorded as an error",
            push_errors[0]["detail"][:90] if push_errors else "")
    c.check(state["tasks"][PUSH_FAIL_TASK]["status"] == "done",
            "the run continues after the failed push")
    c.check(code == 2 and state["camera"] is not None
            and state["camera"].get("dirty"),
            "an unverified camera cleanup stops the run", f"exit {code}")
    c.check(not runner.pids_named("vimbax_camera_node"),
            "the stub driver is shut down even when restore fails")

    code = run_once(ctx, "run5 (a driver the runner did not start)")
    state = load_state(ctx)
    decoy = int((ctx["state"] / "decoy-started").read_text())
    alive = Path(f"/proc/{decoy}").exists()
    c.check(code == 2 and state["camera"] and state["camera"].get("dirty")
            and any("did not start" in e["detail"] for e in state["errors"]),
            "a driver that the runner did not start stops the run",
            f"exit {code}")
    c.check(alive and runner.pids_named("vimbax_camera_node") == [decoy],
            "the runner stops only its own driver and leaves the other alone",
            f"decoy {decoy} alive: {alive}")
    os.kill(decoy, 15)
    time.sleep(0.5)

    code = run_once(ctx, "run6 (completion with a failed final push)")
    state = load_state(ctx)
    final = state.get("final_commit", "")
    status_text = (ctx["run_dir"] / "final-status.txt").read_text()
    c.check(code == 3 and state["status"] == "complete"
            and state["final_push"] == "failed",
            "a failed final push exits with code 3", f"exit {code}")
    c.check(final == local_head(ctx) and remote_head(ctx) != final
            and "complete locally" in status_text,
            "the report says the design is complete locally",
            status_text.splitlines()[0][:100])
    retry = next(line.strip() for line in status_text.splitlines()
                 if line.strip().startswith("git -C "))
    subprocess.run(retry, shell=True, check=True, capture_output=True)
    c.check(remote_head(ctx) == final,
            "the printed retry command pushes the final commit", retry[:90])
    before = local_head(ctx)
    code = run_once(ctx, "run7 (rerun after completion)")
    state = load_state(ctx)
    c.check(code == 0 and local_head(ctx) == before
            and state["final_push"] == "verified",
            "a rerun after completion only checks the push and adds no commit",
            f"exit {code}")
    c.check(outcomes(state, "camera-c2")[-1] == "ok"
            and state["camera"] is None,
            "camera cleanup is verified before the hardware task retries")
    guard_log = (ctx["state"] / "guard.log").read_text().split()
    c.check(guard_log.count("restore") == 6,
            "restore ran for each camera attempt and each recovery",
            f"{guard_log.count('restore')} restore calls")
    c.check(outcomes(state, "prose") == ["quota", "ok"]
            and state["tasks"]["prose"]["attempts"][1]["started"]
            >= state["tasks"]["prose"]["attempts"][0]["resume_at"],
            "a Claude quota pause waits when nothing else is ready")
    c.check(outcomes(state, "meaning-check") == ["quota", "ok"],
            "a quota error without a reset time uses the backoff")
    c.check(remote_head(ctx) == local_head(ctx)
            and failed_commit[0] in git("rev-list", BRANCH, cwd=ctx["remote"]),
            "the commit from the failed push reaches the remote later")
    status = git("status", "--porcelain", cwd=ctx["work"])
    c.check(f" M {V1_REL}" in status and "?? notes-unrelated.md" in status,
            "unrelated edits stay in the worktree", status.strip())
    c.check(git("log", "--format=%H", "--", "notes-unrelated.md",
                cwd=ctx["work"]).strip() == ""
            and "Unrelated edit" not in committed_file(ctx, V1_REL),
            "unrelated edits are never committed")
    base = git("rev-list", "--max-parents=0", "HEAD", cwd=ctx["work"]).strip()
    touched = set(git("log", "--format=", "--name-only", f"{base}..HEAD",
                      cwd=ctx["work"]).split())
    outside = sorted(path for path in touched
                     if not path.startswith(PLANNING_REL + "/")
                     and path != V2_REL)
    c.check(touched and not outside,
            "runner commits touch only planning paths and v2",
            f"{len(touched)} paths, outside: {outside}")
    trailers = git("log", "--format=%(trailers:key=Planning-Task,valueonly)",
                   cwd=ctx["work"]).split()
    c.check(len(trailers) == len(set(trailers)),
            "each task has exactly one checkpoint commit",
            f"{len(trailers)} task commits")
    c.check(all(t["status"] == "done" for t in state["tasks"].values()),
            "all tasks are done", f"{len(state['tasks'])} tasks")

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
