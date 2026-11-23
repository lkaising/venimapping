# ------------------------------------------------------------------------------
#  Filename: run.py
#
#  Purpose:  Implements and verifies step 1 of the v2 image acquisition design
#            with no person present. It runs the Claude and Codex tasks and
#            the deterministic build, test, and camera stages one at a time,
#            checkpoints each result on the step 1 branch, and pauses or
#            stops on failures.
#
#  Usage:    python3 docs/architecture/image-acquisition-step-1/runner/run.py
#            The same command resumes a stopped or interrupted run.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import argparse
import datetime
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.dont_write_bytecode = True

import checks  # noqa: E402
import report  # noqa: E402
import rig  # noqa: E402
from common import (Stop, atomic_write, boot_id, excerpt, group_pids,  # noqa
                    kill_group, now, pids_named, ros_env, stamp)

# --- Configuration ------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = RUNNER_DIR.parent / "prompts"
SETTINGS_FILE = RUNNER_DIR / "settings.json"

HARNESS = "docs/architecture/image-acquisition-step-1"
OUT = f"{HARNESS}/output"
V2 = "docs/architecture/image-acquisition-design-v2.md"
PKG = "src/venimapping_bringup"
XML = f"{PKG}/config/camera_settings.xml"
PROFILE_FILE = f"{PKG}/config/acquisition_profile.yaml"
STEP1_TEXT = [
    f"{PKG}/config/camera.yaml",
    f"{PKG}/config/acquisition_profile.yaml",
    f"{PKG}/launch/camera.launch.py",
    f"{PKG}/CMakeLists.txt",
    f"{PKG}/package.xml",
    f"{PKG}/test/test_camera_config.py",
]
NEW_FILES = [f"{PKG}/config/acquisition_profile.yaml",
             f"{PKG}/test/test_camera_config.py"]
CHANGED_FILES = [f"{PKG}/config/camera.yaml", f"{PKG}/launch/camera.launch.py",
                 f"{PKG}/CMakeLists.txt", f"{PKG}/package.xml"]

# Each stage kind. Agent kinds write only their listed paths.
KINDS = {
    "implement": {
        "tool": "claude", "prompt": "implement.md", "writes": STEP1_TEXT,
        "outputs": [f"{OUT}/implement-notes.md"],
        "commit": "feat(bringup): add the step 1 bring-up parameters and files"},
    "repair": {
        "tool": "claude", "prompt": "repair.md", "writes": STEP1_TEXT,
        "outputs": [f"{OUT}/repairs/{{id}}.md"],
        "commit": "fix(bringup): repair the failed {failed} check ({id})"},
    "review": {
        "tool": "codex", "prompt": "review.md", "writes": [],
        "outputs": [f"{OUT}/review.md", f"{OUT}/review.json"],
        "commit": "docs(step1): record the Codex review of step 1"},
    "fix": {
        "tool": "claude", "prompt": "fix.md", "writes": STEP1_TEXT,
        "outputs": [f"{OUT}/fixes.md"],
        "commit": "fix(bringup): apply the step 1 review fixes"},
    "build": {"tool": "harness",
              "commit": "test(step1): record the bring-up build and test "
                        "({id})"},
    "settings": {"tool": "harness", "camera": True,
                 "commit": "feat(bringup): add the camera settings file made "
                           "on the rig"},
    "rig": {"tool": "harness", "camera": True,
            "commit": "test(step1): record the step 1 rig check ({id})"},
    "report": {"tool": "harness",
               "commit": "docs(step1): record the step 1 report"},
}
# Log folders under the output folder. The project .gitignore ignores each
# folder named build, install, or log, so no log folder uses those names.
LOG_FOLDERS = {"build": "colcon", "settings": "settings", "rig": "rig"}
PIPELINE = ["implement", "build", "settings", "review", "fix", "build", "rig",
            "report"]

EXIT_COMPLETE = 0
EXIT_STOPPED = 2
EXIT_COMPLETE_LOCAL = 3
SEVERITIES = ("blocking", "major", "minor")

QUOTA_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"usage limit",
        r"hit your (?:\w+ ){0,3}limit",
        r"spend limit",
        r"usage_limit_reached",
        r"UsageLimitReached",
        r"limit reached\|\d{10}",
        r"out of (?:extra )?usage",
    )
]

TRANSIENT_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"overloaded",
        r"\b(?:500|502|503|504|529)\b",
        r"rate_limit_error",
        r"ECONNRESET|ECONNREFUSED|ETIMEDOUT|EAI_AGAIN|ENOTFOUND|EPIPE",
        r"connection (?:reset|refused|closed|error|timed out)",
        r"network (?:error|is unreachable)",
        r"temporar(?:y|ily) (?:failure|unavailable)",
        r"stream disconnected",
        r"socket hang up",
        r"fetch failed",
        r"service unavailable",
        r"request timed out",
    )
]

MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()


def fill(pattern: str, values: dict[str, str]) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)),
                  pattern)


# --- Error classification -----------------------------------------------------


def parse_reset(text: str, reference: float) -> float | None:
    """Returns the reset time a quota message reports, or None."""
    found = _parse_reset(text, reference)
    if found is None or found > reference + 8 * 86400:
        return None
    return max(found, reference)


def _parse_reset(text: str, reference: float) -> float | None:
    match = re.search(r"\|(\d{10})\b", text)
    if match:
        return float(match.group(1))

    match = re.search(r"resets?_?at\"?\s*[:=]\s*\"?(\d{10})", text)
    if match:
        return float(match.group(1))

    match = re.search(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?"
        r"(?:Z|[+-]\d{2}:?\d{2})?", text)
    if match:
        try:
            moment = datetime.datetime.fromisoformat(
                match.group(0).replace("Z", "+00:00"))
        except ValueError:
            moment = None
        if moment is not None:
            if moment.tzinfo is None:
                moment = moment.astimezone()
            return moment.timestamp()

    match = re.search(
        r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)"
        r"(?:\s*\(([^)]+)\))?", text, re.IGNORECASE)
    if match:
        hour = int(match.group(1)) % 12
        if match.group(3).lower() == "pm":
            hour += 12
        minute = int(match.group(2) or 0)
        return _next_clock(reference, hour, minute, match.group(4))

    match = re.search(r"try again at\s+([^\n]+)", text, re.IGNORECASE)
    if match:
        return _parse_try_again(match.group(1), reference)
    return None


def _zone(name: str | None) -> datetime.tzinfo | None:
    if not name:
        return datetime.datetime.now().astimezone().tzinfo
    try:
        return ZoneInfo(name.strip())
    except Exception:
        return None


def _next_clock(reference: float, hour: int, minute: int,
                zone_name: str | None) -> float | None:
    zone = _zone(zone_name)
    if zone is None:
        return None
    base = datetime.datetime.fromtimestamp(reference, zone)
    target = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target.timestamp() <= reference:
        target += datetime.timedelta(days=1)
    return target.timestamp()


def _parse_try_again(raw: str, reference: float) -> float | None:
    raw = raw.strip().rstrip(".").strip()
    raw = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", r"\1", raw)

    match = re.match(
        r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4}),?\s+(?:at\s+)?"
        r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])?", raw)
    if match and match.group(1).lower() in MONTHS:
        hour = int(match.group(4))
        if match.group(6):
            hour = hour % 12 + (12 if match.group(6).lower() == "pm" else 0)
        moment = datetime.datetime(
            int(match.group(3)), MONTHS.index(match.group(1).lower()) + 1,
            int(match.group(2)), hour, int(match.group(5))).astimezone()
        return moment.timestamp()

    match = re.match(r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])?", raw)
    if match:
        hour = int(match.group(1))
        if match.group(3):
            hour = hour % 12 + (12 if match.group(3).lower() == "pm" else 0)
        return _next_clock(reference, hour, int(match.group(2)), None)
    return None


def classify(tool: str, returncode: int | None, stdout: str, stderr: str,
             timed_out: bool, timeout_s: int) -> tuple[str, str]:
    """Returns (class, detail). Class is ok, quota, transient, or error."""
    if timed_out:
        return "error", f"no result after {timeout_s} s; the runner killed it"

    if tool == "claude":
        failed, detail = _claude_failure(returncode, stdout)
    else:
        failed, detail = _codex_failure(returncode, stdout)
    if not failed:
        return "ok", ""

    text = "\n".join(part for part in (detail, stderr) if part.strip())
    if not text.strip():
        text = f"exit code {returncode} with no error text"
    if any(p.search(text) for p in QUOTA_PATTERNS):
        return "quota", text
    if any(p.search(text) for p in TRANSIENT_PATTERNS):
        return "transient", text
    return "error", text


def _claude_failure(returncode: int | None, stdout: str) -> tuple[bool, str]:
    result = None
    for line in reversed(stdout.strip().splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("type") == "result":
            result = candidate
            break
    if result is None:
        return True, stdout
    text = str(result.get("result", ""))
    if result.get("is_error") or result.get("subtype") != "success":
        return True, f"{result.get('subtype', '')}: {text}"
    return returncode != 0, text


def _codex_failure(returncode: int | None, stdout: str) -> tuple[bool, str]:
    messages = []
    completed = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "error":
            messages.append(str(event.get("message", "")))
        elif kind == "turn.failed":
            messages.append(str((event.get("error") or {}).get("message", "")))
        elif kind == "turn.completed":
            completed = True
    if messages or returncode != 0 or not completed:
        return True, "\n".join(messages)
    return False, ""


# --- Runner -------------------------------------------------------------------


class Runner:
    def __init__(self, settings_path: Path, stop_before: str = "") -> None:
        self.settings = json.loads(settings_path.read_text())
        self.stop_before = stop_before
        self.worktree = Path(self.git(
            "rev-parse", "--show-toplevel", cwd=RUNNER_DIR).strip())
        branch = self.git("rev-parse", "--abbrev-ref", "HEAD").strip()
        if branch != self.settings["branch"]:
            sys.exit(f"the worktree is on {branch}, not on "
                     f"{self.settings['branch']}; the runner will not commit")
        self.run_dir = Path(self.settings["run_dir"])
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "state.json"
        self.env_cache: dict[str, str] | None = None
        self.camera_lock = None
        self.lock = open(self.run_dir / "runner.lock", "w")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit("another runner holds " + str(self.run_dir))
        self.state = self.load_state()
        self.sync_claude_pause()

    # --- State ----------------------------------------------------------------

    def load_state(self) -> dict:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text())
        else:
            state = {
                "status": "running", "stages": {}, "order": [], "errors": [],
                "events": [], "camera": None, "baseline": None,
                "base_commit": self.head(), "last_checkpoint": None,
                "repairs": {"build": 0, "rig": 0},
                "push": {"pending": False, "failures": 0, "last_error": ""},
                "tools": {t: {"paused_until": 0, "quota_hits": 0, "reason": ""}
                          for t in ("claude", "codex", "harness")},
                "accounts": {}, "account_next": 0,
            }
            for kind in PIPELINE:
                self.add_stage(state, kind, {}, len(state["order"]))
        for account in self.accounts():
            state["accounts"].setdefault(
                account["name"],
                {"paused_until": 0, "quota_hits": 0, "reason": ""})
        return state

    def accounts(self) -> list[dict]:
        return self.settings["claude"].get("accounts") or []

    def sync_claude_pause(self) -> None:
        accounts = self.accounts()
        if accounts:
            self.state["tools"]["claude"].update(
                paused_until=min(self.state["accounts"][a["name"]]
                                 ["paused_until"] for a in accounts),
                reason="every Claude account is paused")

    def add_stage(self, state: dict, kind: str, params: dict,
                  position: int) -> str:
        count = sum(1 for s in state["stages"].values() if s["kind"] == kind)
        stage_id = f"{kind}-{count + 1}" if kind in (
            "build", "rig", "repair") else kind
        state["stages"][stage_id] = {
            "id": stage_id, "kind": kind, "tool": KINDS[kind]["tool"],
            "params": params, "status": "pending", "attempts": [],
            "commit": None, "not_before": 0, "transient_failures": 0,
            "result": None,
        }
        state["order"].insert(position, stage_id)
        return stage_id

    def save(self) -> None:
        atomic_write(self.state_path, json.dumps(self.state, indent=2))

    def event(self, text: str) -> None:
        self.state["events"].append(f"{stamp(now())} {text}")
        self.state["events"] = self.state["events"][-200:]
        with open(self.run_dir / "events.log", "a", encoding="utf-8") as log:
            log.write(f"{stamp(now())} {text}\n")
        print(f"[runner] {text}", flush=True)

    def record_error(self, kind: str, stage: str | None,
                     attempt: int | None, detail: str) -> None:
        self.state["errors"].append({
            "time": stamp(now()), "kind": kind, "stage": stage,
            "attempt": attempt, "detail": excerpt(detail)})
        self.event(f"error ({kind}) {stage or ''}: {excerpt(detail, 200)}")

    # --- Git ------------------------------------------------------------------

    def git(self, *args: str, cwd: Path | None = None,
            check: bool = True) -> str:
        env = dict(os.environ)
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
        env["GIT_TERMINAL_PROMPT"] = "0"
        result = subprocess.run(
            ["git", *args], cwd=cwd or self.worktree, env=env,
            capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if check and result.returncode != 0:
            raise Stop(f"git {' '.join(args)} failed: "
                       f"{excerpt(result.stderr + result.stdout)}")
        return result.stdout if check else result.stdout + result.stderr

    def head(self, cwd: Path | None = None) -> str:
        return self.git("rev-parse", "HEAD", cwd=cwd).strip()

    def guard_snapshot(self) -> dict:
        driver = Path(self.settings["driver_source"])
        return {
            "worktree_head": self.head(),
            "worktree_status": self.git("status", "--porcelain=v1", "-uall"),
            "driver_head": self.head(driver),
            "driver_status": self.git("status", "--porcelain=v1", cwd=driver),
        }

    def find_commit(self, stage_id: str, attempt: int) -> str | None:
        found = self.git(
            "log", "-n", "1", "--format=%H", "--all-match",
            f"--grep=^Step1-Stage: {stage_id}$",
            f"--grep=^Step1-Attempt: {attempt}$").strip()
        return found or None

    def push(self) -> None:
        push = self.state["push"]
        if not push["pending"]:
            return
        output = self.git("push", "--quiet", self.settings["remote"],
                          f"HEAD:refs/heads/{self.settings['branch']}",
                          check=False)
        local = self.head()
        if self.remote_head() == local:
            if push["failures"]:
                self.event(f"push recovered at {local[:10]}")
            push.update(pending=False, failures=0, last_error="")
        else:
            push["failures"] += 1
            push["last_error"] = excerpt(output, 600)
            self.record_error("push", None, None,
                              f"push of {local[:10]} failed; the commit is "
                              f"kept locally and the push is retried at the "
                              f"next checkpoint: {push['last_error']}")
        self.save()

    def remote_head(self) -> str:
        listing = self.git("ls-remote", self.settings["remote"],
                           f"refs/heads/{self.settings['branch']}",
                           check=False)
        return listing.split("\t")[0].strip()

    def checkpoint_run_md(self, subject: str,
                          event: str = "run-record") -> None:
        run_md = f"{OUT}/RUN.md"
        atomic_write(self.worktree / run_md, self.render_run_md())
        self.git("add", "--", run_md)
        unchanged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", run_md],
            cwd=self.worktree).returncode == 0
        if unchanged:
            return
        self.git("commit", "--quiet", "-m",
                 subject + f"\n\nStep1-Event: {event}", "--", run_md)
        self.state["push"]["pending"] = True
        self.save()
        self.push()

    # --- Scheduling -----------------------------------------------------------

    def stages(self) -> list[dict]:
        return [self.state["stages"][i] for i in self.state["order"]]

    def current(self) -> dict | None:
        """Returns the first stage that is not done. The pipeline is linear."""
        return next((s for s in self.stages()
                     if s["status"] not in ("done", "skipped")), None)

    def wake_time(self, stage: dict) -> float:
        return max(stage["not_before"],
                   self.state["tools"][stage["tool"]]["paused_until"])

    def wait_until(self, moment: float) -> None:
        self.state["status"] = "waiting"
        self.save()
        self.write_run_md()
        chunk = self.settings["max_sleep_chunk_s"]
        self.event(f"waiting until {stamp(moment)}")
        while now() < moment:
            time.sleep(max(0.0, min(chunk, moment - now())))
        self.state["status"] = "running"
        self.save()

    # --- Main loop ------------------------------------------------------------

    def run(self) -> int:
        try:
            self.recover()
            self.state["status"] = "running"
            self.save()
            self.push()
            while True:
                stage = self.current()
                if stage is None:
                    return self.finalize()
                if stage["kind"] == self.stop_before:
                    raise Stop(f"the runner stopped before {stage['id']}, as "
                               f"--stop-before asked",
                               "Run the command without --stop-before to "
                               "continue.")
                if stage["status"] != "pending":
                    raise Stop(f"stage {stage['id']} has status "
                               f"{stage['status']}; check state.json")
                wake = self.wake_time(stage)
                if wake > now():
                    self.wait_until(wake)
                    continue
                self.execute(stage)
        except Stop as stop:
            return self.stop(str(stop), stop.action)

    def finalize(self) -> int:
        left = pids_named(self.settings["camera"]["driver_process"])
        if left:
            return self.stop(f"a camera driver is running at the end of the "
                             f"run: {left}",
                             "Find out who started it and stop it. Then run "
                             "the resume command.")
        if not self.state.get("final_commit"):
            self.state["status"] = "complete"
            self.event("all stages done")
            self.save()
            self.checkpoint_run_md("docs(step1): record the completed step 1 "
                                   "run", event="run-complete")
            self.state["final_commit"] = self.head()
            self.save()
        else:
            self.state["push"]["pending"] = True
            self.push()
        final = self.state["final_commit"]
        branch = self.settings["branch"]
        remote = self.settings["remote"]
        if self.remote_head() == final:
            self.state["final_push"] = "verified"
            message = (f"Step 1 is complete. {remote}/{branch} has the final "
                       f"commit {final[:11]}. Read {OUT}/report.md.")
            code = EXIT_COMPLETE
        else:
            self.state["final_push"] = "failed"
            message = (
                f"Step 1 is complete locally, but {remote}/{branch} does not "
                f"have the final commit {final[:11]}. Retry the push with "
                f"this command:\n\n"
                f"    git -C {self.worktree} push {remote} "
                f"{final}:refs/heads/{branch}\n\n"
                f"Running the runner again also retries only the push.")
            code = EXIT_COMPLETE_LOCAL
        self.save()
        atomic_write(self.run_dir / "final-status.txt", message + "\n")
        print(f"[runner] {message}", flush=True)
        return code

    def stop(self, reason: str, action: str = "") -> int:
        self.state["status"] = "stopped"
        self.state["stop_reason"] = excerpt(reason)
        self.state["stop_action"] = action
        self.event(f"stopped: {excerpt(reason, 300)}")
        self.save()
        try:
            self.checkpoint_run_md("docs(step1): record the run stop")
        except Stop as again:
            self.write_run_md()
            print(f"[runner] could not commit the stop record: {again}",
                  file=sys.stderr)
        atomic_write(self.run_dir / "final-status.txt",
                     f"The run stopped: {reason}\n\n{action}\n")
        return EXIT_STOPPED

    # --- Recovery -------------------------------------------------------------

    def recover(self) -> None:
        if self.state["status"] == "stopped":
            self.event("restarting after a stop")
        self.state.pop("stop_action", None)
        for stage in self.stages():
            if stage["status"] == "running":
                self.recover_running(stage)
            elif stage["status"] == "failed":
                stage["status"] = "pending"
                stage["transient_failures"] = 0
        if self.state["camera"] is not None:
            self.event("verifying the camera cleanup left by an earlier "
                       "attempt")
            self.camera_teardown()
        self.save()
        for stage in self.stages():
            if stage["status"] == "importing":
                self.recover_importing(stage)

    def recover_running(self, stage: dict) -> None:
        attempt = stage["attempts"][-1]
        pid = attempt.get("pid")
        if pid and attempt.get("boot_id") == boot_id() and group_pids(pid):
            kill_group(pid, 5)
        shutil.rmtree(Path(attempt["dir"]) / "out", ignore_errors=True)
        attempt["outcome"] = "interrupted"
        attempt["ended"] = now()
        stage["status"] = "pending"
        self.event(f"{stage['id']} attempt {attempt['n']} was interrupted; "
                   f"its output was discarded")

    def recover_importing(self, stage: dict) -> None:
        attempt = stage["attempts"][-1]
        found = self.find_commit(stage["id"], attempt["n"])
        if found:
            self.event(f"{stage['id']} was committed as {found[:10]} before "
                       f"the state update; marking it done")
            self.finish_import(stage, found)
            return
        self.event(f"{stage['id']} import was cut short; restoring its paths "
                   f"and importing again")
        for rel in attempt["imported"]:
            tracked = subprocess.run(
                ["git", "cat-file", "-e", f"HEAD:{rel}"],
                cwd=self.worktree, capture_output=True).returncode == 0
            if tracked:
                self.git("checkout", "HEAD", "--", rel)
            else:
                (self.worktree / rel).unlink(missing_ok=True)
        self.import_stage(stage)

    # --- Stage execution ------------------------------------------------------

    def execute(self, stage: dict) -> None:
        number = len(stage["attempts"]) + 1
        attempt_dir = self.run_dir / "attempts" / stage["id"] / str(number)
        out_dir = attempt_dir / "out"
        if attempt_dir.exists():
            shutil.rmtree(attempt_dir)
        out_dir.mkdir(parents=True)
        attempt = {"n": number, "dir": str(attempt_dir), "started": now(),
                   "ended": None, "pid": None, "outcome": None, "detail": "",
                   "start_commit": self.head()}
        stage["attempts"].append(attempt)
        if stage["tool"] == "claude" and self.accounts():
            attempt["account"] = self.pick_account()
        stage["status"] = "running"
        self.save()
        on = f" on {attempt['account']}" if attempt.get("account") else ""
        self.event(f"start {stage['id']} ({stage['tool']}) attempt "
                   f"{number}{on}")

        before = self.guard_snapshot()
        kind = KINDS[stage["kind"]]
        try:
            if stage["tool"] != "harness":
                outcome, detail = self.run_agent(stage, attempt, attempt_dir,
                                                 out_dir)
            elif kind.get("camera"):
                outcome, detail = self.run_camera(stage, attempt, attempt_dir,
                                                  out_dir)
            else:
                outcome, detail = self.run_local(stage, attempt, out_dir)
        except Stop:
            stage["status"] = "failed"
            attempt["outcome"] = "error"
            attempt["ended"] = now()
            self.save()
            raise

        attempt["ended"] = now()
        attempt["pid"] = None
        if outcome == "ok":
            problems = self.validate(stage, attempt, out_dir, before)
            if problems:
                outcome, detail = "error", "output check failed: " + "; ".join(
                    problems)
        attempt["outcome"] = outcome
        attempt["detail"] = excerpt(detail)

        if outcome == "ok":
            self.succeed(stage, attempt)
        elif outcome == "transient":
            self.retry_transient(stage, attempt, detail)
        elif outcome == "quota":
            self.pause_on_quota(stage, attempt, detail)
        else:
            stage["status"] = "failed"
            self.record_error("stage", stage["id"], number, detail)
            self.save()
            raise Stop(f"{stage['id']} attempt {number} failed: "
                       f"{excerpt(detail, 600)}",
                       f"Read the logs in {attempt_dir}. Fix the cause, then "
                       f"run the resume command. The stage runs again.")

    # --- Agent stages ---------------------------------------------------------

    def stage_values(self, stage: dict) -> dict[str, str]:
        values = {"O": OUT, "H": HARNESS, "V2": V2, "id": stage["id"],
                  "base": self.state["base_commit"],
                  "worktree": str(self.worktree)}
        values.update(stage["params"])
        return values

    def outputs(self, stage: dict) -> list[str]:
        return [fill(p, self.stage_values(stage))
                for p in KINDS[stage["kind"]].get("outputs", [])]

    def run_agent(self, stage: dict, attempt: dict, attempt_dir: Path,
                  out_dir: Path) -> tuple[str, str]:
        for rel in KINDS[stage["kind"]]["writes"]:
            source = self.worktree / rel
            if source.is_file():
                (out_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, out_dir / rel)
        prompt = self.render_prompt(stage, out_dir)
        atomic_write(attempt_dir / "prompt.md", prompt)
        result = self.invoke(stage, attempt, prompt, attempt_dir, out_dir)
        attempt["agent_pids_left"] = group_pids(attempt["pid"])
        if attempt["agent_pids_left"]:
            kill_group(attempt["pid"], 5)
        return result

    def invoke(self, stage: dict, attempt: dict, prompt: str,
               attempt_dir: Path, out_dir: Path) -> tuple[str, str]:
        tool = stage["tool"]
        config = self.settings[tool]
        env = dict(os.environ)
        env["STEP1_STAGE"] = stage["id"]
        if attempt.get("account"):
            env.pop("CLAUDE_CONFIG_DIR", None)
            config_dir = next(a["config_dir"] for a in self.accounts()
                              if a["name"] == attempt["account"])
            if config_dir:
                env["CLAUDE_CONFIG_DIR"] = os.path.expanduser(config_dir)
        if tool == "claude":
            command = [*config["command"], "-p", "--output-format", "json",
                       "--permission-mode", "acceptEdits",
                       "--permission-prompts", "none",
                       "--no-session-persistence",
                       "--disallowedTools", "WebFetch", "WebSearch",
                       "--allowedTools", *self.claude_tools(out_dir)]
            if config.get("model"):
                command += ["--model", config["model"]]
        else:
            command = [*config["command"], "exec", "--json",
                       "--sandbox", "workspace-write",
                       "--skip-git-repo-check", "--ephemeral",
                       "--color", "never", "-C", str(out_dir),
                       "-o", str(attempt_dir / "last-message.md"), "-"]

        with open(attempt_dir / "stdout.log", "w") as stdout, \
                open(attempt_dir / "stderr.log", "w") as stderr:
            process = subprocess.Popen(
                command, cwd=out_dir, env=env, stdin=subprocess.PIPE,
                stdout=stdout, stderr=stderr, text=True,
                start_new_session=True)
            attempt["pid"] = process.pid
            attempt["boot_id"] = boot_id()
            self.save()
            try:
                process.stdin.write(prompt)
                process.stdin.close()
            except BrokenPipeError:
                pass
            timed_out = False
            try:
                process.wait(timeout=config["timeout_s"])
            except subprocess.TimeoutExpired:
                kill_group(process.pid, 5)
                process.wait()
                timed_out = True
        return classify(tool, process.returncode,
                        (attempt_dir / "stdout.log").read_text(),
                        (attempt_dir / "stderr.log").read_text(),
                        timed_out, config["timeout_s"])

    def claude_tools(self, out_dir: Path) -> list[str]:
        tools = ["Glob", "Grep", "TodoWrite",
                 f"Edit(/{out_dir}/**)", f"Write(/{out_dir}/**)"]
        tools += [f"Read(/{root}/**)" for root in
                  [str(self.worktree), *self.settings["read_roots"],
                   str(out_dir)]]
        for verb in ("log", "show", "diff", "grep", "ls-files", "blame"):
            tools.append(f"Bash(git -C {self.worktree} {verb}:*)")
            tools.append(f"Bash(git -C {self.settings['driver_source']} "
                         f"{verb}:*)")
        return tools

    def pick_account(self) -> str:
        accounts = self.accounts()
        start = self.state["account_next"] % len(accounts)
        order = accounts[start:] + accounts[:start]
        at = now()
        chosen = next((a for a in order if self.state["accounts"][a["name"]]
                       ["paused_until"] <= at), order[0])
        self.state["account_next"] = (accounts.index(chosen) + 1) % len(
            accounts)
        return chosen["name"]

    # --- Harness stages -------------------------------------------------------

    def env(self) -> dict[str, str]:
        if self.env_cache is None:
            self.env_cache = ros_env(
                self.worktree / self.settings["env_script"])
            defaults = self.worktree / ".devcontainer/colcon-defaults.yaml"
            if defaults.is_file():
                self.env_cache.setdefault("COLCON_DEFAULTS_FILE",
                                          str(defaults))
        return self.env_cache

    def log_dir(self, stage: dict, attempt: dict, out_dir: Path) -> Path:
        rel = (f"{OUT}/{LOG_FOLDERS[stage['kind']]}/{stage['id']}"
               f"-a{attempt['n']}")
        attempt["log_dir"] = rel
        return out_dir / rel

    def run_local(self, stage: dict, attempt: dict,
                  out_dir: Path) -> tuple[str, str]:
        if stage["kind"] == "report":
            text = report.render(self.state, self.settings, OUT, XML)
            atomic_write(out_dir / OUT / "report.md", text)
            attempt["result"] = {"passed": True}
            return "ok", ""
        log_dir = self.log_dir(stage, attempt, out_dir)
        shell = rig.Shell(self.env(), log_dir, log_dir / "commands.log")
        result = checks.build_and_test(
            shell, self.settings["build"]["colcon"], self.worktree,
            self.settings["build"]["timeout_s"])
        self.env_cache = None
        result["log_dir"] = attempt["log_dir"]
        attempt["result"] = result
        self.event(f"{stage['id']} {'passed' if result['passed'] else 'failed'}"
                   f": {result['checks'][-1]['detail']}")
        return "ok", ""

    # --- Camera stages --------------------------------------------------------

    def run_camera(self, stage: dict, attempt: dict, attempt_dir: Path,
                   out_dir: Path) -> tuple[str, str]:
        settings = self.settings["camera"]
        log_dir = self.log_dir(stage, attempt, out_dir)
        env = self.env()
        shell = rig.Shell(env, log_dir, log_dir / "commands.log")
        if stage["kind"] == "rig":
            prefix = self.install_prefix(shell)
        self.camera_begin(stage, attempt_dir, log_dir)
        cli = rig.Cli(shell, settings["namespace"],
                      settings["service_timeout_s"], self.mark_write)
        driver = rig.Driver(shell, settings, self.bare_params(),
                            self.camera_launched, self.camera_stopped)
        session = rig.Rig(cli, driver, log_dir,
                          lambda: self.ensure_baseline(cli), self.worktree,
                          settings)
        result: dict = {"passed": False, "repairable": False}
        try:
            try:
                if stage["kind"] == "settings":
                    save_path = attempt_dir / "camera_settings.xml"
                    rig.make_settings(
                        session, save_path,
                        [self.run_dir, self.worktree / PKG / "config"],
                        log_dir / "camera_settings.saved.xml")
                    result.update(self.scan_settings(save_path, out_dir,
                                                     session))
                else:
                    rig.rig_check(session, self.worktree / PROFILE_FILE,
                                  prefix)
                    result.update(passed=True, detail="each check passed")
            except rig.CheckFailed as failed:
                result.update(passed=False, repairable=failed.repairable,
                              detail=str(failed), failed_check=failed.check)
            except rig.CameraError as error:
                session.record("camera", False, str(error))
                result.update(passed=False, repairable=False,
                              detail=f"camera error: {error}")
        finally:
            cleanup = self.camera_teardown()
            if cleanup is not None and cleanup.exists():
                shutil.copytree(cleanup, log_dir / cleanup.name)
        result.update(session.result())
        result["log_dir"] = attempt["log_dir"]
        atomic_write(log_dir / "results.json", json.dumps(result, indent=2))
        attempt["result"] = result
        self.event(f"{stage['id']} {'passed' if result['passed'] else 'failed'}"
                   f": {excerpt(result.get('detail', ''), 300)}")
        return "ok", ""

    def install_prefix(self, shell: rig.Shell) -> Path:
        expected = self.worktree / "install" / checks.PACKAGE
        code, output, _ = shell.run(
            ["ros2", "pkg", "prefix", checks.PACKAGE], 60)
        found = output.strip().splitlines()[-1] if output.strip() else ""
        if code != 0 or Path(found) != expected:
            raise Stop(f"ros2 pkg prefix {checks.PACKAGE} gives {found!r}, "
                       f"not {expected}",
                       "Make sure that the build of this worktree exists and "
                       "that no other overlay comes first. Then resume.")
        return expected

    def scan_settings(self, save_path: Path, out_dir: Path,
                      session: rig.Rig) -> dict:
        settings = self.settings["camera"]
        scan = checks.scan_settings(save_path, settings["xml_denied_patterns"])
        result = {"scan": scan, "detail": scan["detail"]}
        missing = scan.get("missing")
        if missing is None or missing:
            result.update(passed=False, repairable=False,
                          detail=f"the saved file does not hold the profile "
                                 f"values: {scan['detail']}")
        elif scan["denied"] and settings["xml_denied_policy"] == "stop":
            result.update(passed=False, repairable=False,
                          detail=f"the saved file holds features that the "
                                 f"driver would write on each open: "
                                 f"{scan['denied']}")
        else:
            result["passed"] = True
            target = out_dir / XML
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(save_path, target)
        session.record("S8", result["passed"],
                       f"copied the file to {XML}" if result["passed"] else
                       f"did not copy the file to {XML}: {result['detail']}")
        return result

    def bare_params(self) -> Path:
        path = self.run_dir / "bare-params.yaml"
        rig.write_bare_params(path, self.settings["camera"])
        return path

    def mark_write(self) -> None:
        camera = self.state["camera"]
        if camera is not None and not camera.get("wrote"):
            camera["wrote"] = True
            self.save()

    def camera_launched(self, pgid: int) -> None:
        self.state["camera"]["pgids"].append(pgid)
        self.save()

    def camera_stopped(self, pgid: int) -> None:
        if pgid in self.state["camera"]["pgids"]:
            self.state["camera"]["pgids"].remove(pgid)
        self.save()

    def ensure_baseline(self, cli: rig.Cli) -> None:
        if self.state["baseline"] is not None:
            return
        values = rig.snapshot(cli)
        self.state["baseline"] = values
        atomic_write(self.run_dir / "camera-baseline.json",
                     json.dumps(values, indent=2))
        self.event(f"saved the camera baseline: {values}")
        self.save()

    def camera_begin(self, stage: dict, attempt_dir: Path,
                     log_dir: Path) -> None:
        settings = self.settings["camera"]
        self.camera_lock = open(self.run_dir / "camera.lock", "w")
        try:
            fcntl.flock(self.camera_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Stop("another process holds the camera lock",
                       "Make sure that no other runner uses the camera.")
        foreign = pids_named(settings["driver_process"])
        if foreign:
            raise Stop(f"a camera driver is already running: {foreign}. The "
                       f"runner will not take the camera from it.",
                       "Stop that driver, then run the resume command.")
        self.state["camera"] = {
            "stage": stage["id"], "attempt_dir": str(attempt_dir),
            "pgids": [], "boot_id": boot_id(), "wrote": False,
            "teardowns": 0}
        self.save()

    def camera_teardown(self) -> Path | None:
        """Stops each driver, restores the baseline, and verifies both."""
        camera = self.state["camera"]
        if camera is None:
            return None
        settings = self.settings["camera"]
        camera["teardowns"] = camera.get("teardowns", 0) + 1
        folder = Path(camera["attempt_dir"]) / f"cleanup-{camera['teardowns']}"
        shell = rig.Shell(self.env(), folder, folder / "commands.log")
        report_data: dict = {"stream_stopped": None, "restore": None,
                             "driver_pids_left": None}
        failures = []
        same_boot = camera.get("boot_id") == boot_id()
        for pgid in list(camera["pgids"]):
            if same_boot and group_pids(pgid):
                kill_group(pgid, settings["stop_grace_s"])
            if not same_boot or not group_pids(pgid):
                camera["pgids"].remove(pgid)
        if camera["pgids"]:
            failures.append(f"processes from the runner's driver launches "
                            f"are still running: {camera['pgids']}")
        foreign = pids_named(settings["driver_process"])
        if foreign:
            failures.append(f"a camera driver that the runner did not start "
                            f"is running, and the runner left it alone: "
                            f"{foreign}")
        if not failures and camera.get("wrote") and self.state["baseline"]:
            failures += self.restore_camera(shell, report_data)
        elif not failures:
            report_data["restore"] = "the stage wrote no feature"
        left = pids_named(settings["driver_process"])
        report_data["driver_pids_left"] = left
        if left and not failures:
            failures.append(f"a driver process is still running: {left}")
        shell.run(["ros2", "daemon", "stop"], 30)
        atomic_write(folder / "camera-cleanup.json",
                     json.dumps({**report_data, "errors": failures}, indent=2))
        if failures:
            camera["dirty"] = True
            detail = " | ".join(failures)
            self.record_error("camera-cleanup", camera["stage"], None, detail)
            self.save()
            raise Stop(f"the camera cleanup could not be verified: {detail}",
                       f"The camera may hold changed values. The baseline is "
                       f"in {self.run_dir / 'camera-baseline.json'}. Fix the "
                       f"cause, then run the resume command. The runner "
                       f"tries the cleanup again first. Logs: {folder}")
        self.state["camera"] = None
        if self.camera_lock is not None:
            fcntl.flock(self.camera_lock, fcntl.LOCK_UN)
            self.camera_lock.close()
            self.camera_lock = None
        self.event("camera cleanup verified")
        self.save()
        return folder

    def restore_camera(self, shell: rig.Shell, report_data: dict) -> list:
        settings = self.settings["camera"]
        cli = rig.Cli(shell, settings["namespace"],
                      settings["service_timeout_s"], lambda: None)
        pgids: list[int] = []
        driver = rig.Driver(shell, settings, self.bare_params(),
                            lambda pgid: (pgids.append(pgid),
                                          self.camera_launched(pgid)),
                            self.camera_stopped)
        failures = []
        try:
            driver.launch("driver_restore", bare=True)
            if driver.init_wait("driver_restore") != 0:
                raise rig.CameraError("the init wait on driver_restore.log "
                                      "failed")
            report_data["restore"] = rig.restore(cli, self.state["baseline"])
            report_data["stream_stopped"] = True
        except rig.CameraError as error:
            failures.append(f"could not restore and verify the camera "
                            f"features: {error}")
        try:
            driver.stop_all()
        except rig.CameraError as error:
            failures.append(str(error))
        return failures

    # --- Validation -----------------------------------------------------------

    def validate(self, stage: dict, attempt: dict, out_dir: Path,
                 before: dict) -> list[str]:
        problems = []
        kind = KINDS[stage["kind"]]
        written = sorted(str(p.relative_to(out_dir))
                         for p in out_dir.rglob("*")
                         if p.is_file() or p.is_symlink())
        if stage["tool"] == "harness":
            allowed = None
        else:
            allowed = set(kind["writes"]) | set(self.outputs(stage))
        for rel in written:
            if (out_dir / rel).is_symlink():
                problems.append(f"symlink output {rel}")
            elif allowed is not None and rel not in allowed:
                problems.append(f"unexpected output {rel}")
            elif allowed is None and not (rel.startswith(OUT + "/")
                                          or rel == XML):
                problems.append(f"unexpected harness output {rel}")
        after = self.guard_snapshot()
        for key, label in (("worktree_head", "worktree HEAD"),
                           ("worktree_status", "worktree files"),
                           ("driver_head", "driver HEAD"),
                           ("driver_status", "driver files")):
            if before[key] != after[key]:
                problems.append(f"{label} changed during the stage")
        if stage["tool"] == "harness":
            return problems
        drivers = pids_named(self.settings["camera"]["driver_process"])
        if drivers:
            problems.append(f"a camera driver is running after the agent "
                            f"task, and the runner left it alone: {drivers}")
        for rel in self.outputs(stage):
            path = out_dir / rel
            if not path.is_file() or path.stat().st_size == 0:
                problems.append(f"missing or empty required output {rel}")
        for rel in kind["writes"]:
            if (self.worktree / rel).is_file() and not (out_dir / rel).is_file():
                problems.append(f"deleted {rel}")
        changed = self.changed_files(stage, out_dir)
        attempt["changed"] = changed
        if stage["kind"] == "implement":
            problems += [f"missing new file {rel}" for rel in NEW_FILES
                         if not (out_dir / rel).is_file()]
            problems += [f"{rel} was not changed" for rel in CHANGED_FILES
                         if rel not in changed]
        if stage["kind"] == "review" and not problems:
            problems += self.check_review(out_dir, attempt)
        if stage["kind"] == "fix" and not problems:
            text = (out_dir / f"{OUT}/fixes.md").read_text()
            ids = [f["id"] for f in self.review_findings()]
            problems += [f"fixes.md has no entry for {i}" for i in ids
                         if not re.search(rf"\b{re.escape(i)}\b", text)]
        return problems

    def changed_files(self, stage: dict, out_dir: Path) -> list[str]:
        changed = []
        for rel in KINDS[stage["kind"]]["writes"]:
            new = out_dir / rel
            old = self.worktree / rel
            if new.is_file() and (not old.is_file()
                                  or new.read_bytes() != old.read_bytes()):
                changed.append(rel)
        return changed

    def check_review(self, out_dir: Path, attempt: dict) -> list[str]:
        try:
            data = json.loads((out_dir / f"{OUT}/review.json").read_text())
            findings = data["findings"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            return [f"review.json is not valid: {error}"]
        problems = []
        if not isinstance(findings, list):
            return ["review.json findings is not a list"]
        ids = set()
        for finding in findings:
            if not isinstance(finding, dict) or not finding.get("id") or \
                    str(finding.get("severity", "")).lower() not in SEVERITIES:
                problems.append(f"bad finding {finding}")
            elif finding["id"] in ids:
                problems.append(f"duplicate finding id {finding['id']}")
            else:
                ids.add(finding["id"])
        attempt["result"] = {"passed": True, "findings": findings}
        return problems

    def review_findings(self) -> list[dict]:
        review = self.state["stages"].get("review") or {}
        return ((review.get("result") or {}).get("findings")) or []

    # --- Success, retry, and pause --------------------------------------------

    def pause_record(self, stage: dict, attempt: dict) -> dict:
        if attempt.get("account"):
            return self.state["accounts"][attempt["account"]]
        return self.state["tools"][stage["tool"]]

    def succeed(self, stage: dict, attempt: dict) -> None:
        if stage["tool"] != "harness":
            record = self.pause_record(stage, attempt)
            record.update(quota_hits=0, paused_until=0, reason="")
            self.sync_claude_pause()
        stage["transient_failures"] = 0
        self.import_stage(stage)

    def retry_transient(self, stage: dict, attempt: dict, detail: str) -> None:
        shutil.rmtree(Path(attempt["dir"]) / "out", ignore_errors=True)
        stage["transient_failures"] += 1
        backoff = self.settings["transient_backoff_s"]
        if stage["transient_failures"] > len(backoff):
            stage["status"] = "failed"
            self.record_error("transient-exhausted", stage["id"], attempt["n"],
                              detail)
            self.save()
            raise Stop(f"{stage['id']} kept failing with transient errors "
                       f"after {len(backoff)} retries: {excerpt(detail, 300)}",
                       "Check the network and the tool status. Then run the "
                       "resume command.")
        delay = backoff[stage["transient_failures"] - 1]
        stage["status"] = "pending"
        stage["not_before"] = now() + delay
        self.event(f"{stage['id']} transient failure "
                   f"{stage['transient_failures']}/{len(backoff)}; retry in "
                   f"{delay} s")
        self.save()

    def pause_on_quota(self, stage: dict, attempt: dict, detail: str) -> None:
        shutil.rmtree(Path(attempt["dir"]) / "out", ignore_errors=True)
        tool = stage["tool"]
        record = self.pause_record(stage, attempt)
        record["quota_hits"] += 1
        reset = parse_reset(detail, now())
        if reset is not None:
            until = reset + self.settings["quota_margin_s"]
            how = f"reported reset {stamp(reset)}"
        else:
            steps = self.settings["quota_backoff_s"]
            until = now() + steps[min(record["quota_hits"], len(steps)) - 1]
            how = "no reset time reported; backing off"
        record["paused_until"] = until
        record["reason"] = f"quota on {stage['id']}: {how}"
        self.sync_claude_pause()
        label = tool
        if attempt.get("account"):
            label = f"{tool} ({attempt['account']})"
            until = self.state["tools"][tool]["paused_until"]
        stage["status"] = "pending"
        stage["not_before"] = until
        attempt["resume_at"] = record["paused_until"]
        self.event(f"{label} paused on quota until "
                   f"{stamp(record['paused_until'])} ({how}); "
                   f"{stage['id']} resumes with {tool}")
        self.save()
        self.checkpoint_run_md(f"docs(step1): record the {label} quota pause")

    # --- Import and checkpoint ------------------------------------------------

    def import_stage(self, stage: dict) -> None:
        attempt = stage["attempts"][-1]
        out_dir = Path(attempt["dir"]) / "out"
        files = sorted(str(p.relative_to(out_dir)) for p in out_dir.rglob("*")
                       if p.is_file())
        if stage["tool"] != "harness":
            writes = set(KINDS[stage["kind"]]["writes"])
            files = [rel for rel in files
                     if rel not in writes or rel in attempt.get("changed", [])]
        run_md = f"{OUT}/RUN.md"
        imported = files + [run_md]
        attempt["imported"] = imported
        stage["status"] = "importing"
        self.save()

        for rel in files:
            target = self.worktree / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(out_dir / rel, target)

        projected = json.loads(json.dumps(self.state))
        projected["stages"][stage["id"]]["status"] = "done"
        projected["stages"][stage["id"]]["result"] = attempt.get("result")
        projected["last_checkpoint"] = {"stage": stage["id"],
                                        "commit": "this commit"}
        atomic_write(self.worktree / run_md, self.render_run_md(projected))

        result = attempt.get("result") or {}
        subject = fill(KINDS[stage["kind"]]["commit"], self.stage_values(stage))
        if result.get("passed") is False:
            subject = (f"test(step1): record the failed {stage['id']} stage, "
                       f"attempt {attempt['n']}")
        trailers = {"Step1-Stage": stage["id"],
                    "Step1-Attempt": str(attempt["n"]),
                    "Step1-Tool": stage["tool"]}
        if attempt.get("account"):
            trailers["Step1-Account"] = attempt["account"]
        message = subject + "\n\n" + "\n".join(
            f"{k}: {v}" for k, v in trailers.items())
        self.git("add", "--", *imported)
        self.git("commit", "--quiet", "-m", message, "--", *imported)
        self.finish_import(stage, self.head())

    def finish_import(self, stage: dict, commit: str) -> None:
        attempt = stage["attempts"][-1]
        stage["status"] = "done"
        stage["commit"] = commit
        stage["result"] = attempt.get("result")
        self.state["last_checkpoint"] = {"stage": stage["id"],
                                         "commit": commit}
        self.state["push"]["pending"] = True
        self.event(f"checkpoint {commit[:10]} for {stage['id']}")
        self.save()
        self.push()
        self.continue_after(stage)

    def continue_after(self, stage: dict) -> None:
        """Adds repair stages after a failed check, or stops the run."""
        kind = stage["kind"]
        result = stage["result"] or {}
        position = self.state["order"].index(stage["id"]) + 1
        attempt = stage["attempts"][-1]
        logs = (f"{OUT}/{LOG_FOLDERS.get(kind, kind)}/{stage['id']}"
                f"-a{attempt['n']}")
        if kind in ("build", "rig") and not result.get("passed"):
            limit = self.settings[f"max_{kind}_repairs"]
            used = self.state["repairs"][kind]
            if not result.get("repairable") or used >= limit:
                stage["status"] = "failed"
                why = ("a file change cannot fix it" if not
                       result.get("repairable") else
                       f"the {limit} repair rounds are used")
                self.save()
                raise Stop(f"{stage['id']} failed and {why}: "
                           f"{excerpt(result.get('detail', ''), 500)}",
                           self.failure_action(stage, result, logs))
            self.state["repairs"][kind] += 1
            params = {"failed": stage["id"], "logs": logs,
                      "detail": excerpt(result.get("detail", ""), 500)}
            new = [("repair", params), ("build", {})]
            if kind == "rig":
                new.append(("rig", {}))
            for offset, (new_kind, new_params) in enumerate(new):
                added = self.add_stage(self.state, new_kind, new_params,
                                       position + offset)
                self.event(f"{stage['id']} failed; added {added}")
            self.save()
        elif kind == "settings" and not result.get("passed"):
            stage["status"] = "failed"
            self.save()
            raise Stop(f"{stage['id']} failed: "
                       f"{excerpt(result.get('detail', ''), 500)}",
                       self.failure_action(stage, result, logs))
        elif kind == "review" and not self.review_findings():
            fix = self.state["stages"]["fix"]
            if fix["status"] == "pending":
                fix["status"] = "skipped"
                self.event("the review has no findings; skipping fix")
                self.save()
        elif kind == "repair" and not attempt.get("changed"):
            notes = fill(KINDS["repair"]["outputs"][0],
                         self.stage_values(stage))
            raise Stop(f"{stage['id']} changed no file for the failed "
                       f"{stage['params']['failed']} check",
                       f"Read {notes}. Fix the cause, then run the resume "
                       f"command. The checks run again.")

    def failure_action(self, stage: dict, result: dict, logs: str) -> str:
        detail = result.get("detail", "")
        hints = [
            ("init wait", "Make sure that the camera is powered and on the "
                          "network, and that no other program holds it. If "
                          "the driver starts slower than the 60 s limit, "
                          "decide on a new limit."),
            ("did not take", "The camera did not keep a written value. Check "
                             "the feature access modes with the Vimba X "
                             "Viewer."),
            ("denied features", "Review the saved file. Decide if the driver "
                                "may write these features on each open. Then "
                                "change xml_denied_policy or the pattern list "
                                "in settings.json."),
        ]
        hint = next((text for key, text in hints if key in detail),
                    "Read the results and the logs. Fix the cause.")
        return (f"{hint} The logs are in {logs}/ in the worktree. Then run "
                f"the resume command. The stage runs again.")

    # --- Prompts and RUN.md ---------------------------------------------------

    def render_prompt(self, stage: dict, out_dir: Path) -> str:
        kind = KINDS[stage["kind"]]
        lines = [
            f"# Task {stage['id']}",
            "",
            f"- Tool: {stage['tool']}",
            f"- Kind: {stage['kind']}",
            f"- Date: {datetime.date.today().isoformat()}",
            f"- Worktree (read only): {self.worktree}",
            f"- Worktree checkpoint: {self.head()}",
            f"- Run base commit: {self.state['base_commit']}",
            f"- v2 design: {self.worktree / V2}",
            f"- Harness plan: {self.worktree / HARNESS / 'plan.md'}",
            f"- Driver source (read only): {self.settings['driver_source']}",
            f"- Other read-only references: "
            f"{', '.join(self.settings['read_roots'])}",
            f"- Output root: {out_dir}",
            "",
            "Files that you may change, relative to the output root:",
            "",
            *([f"- {rel}" for rel in kind["writes"]] or ["- none"]),
            "",
            "Required outputs, relative to the output root:",
            "",
            *[f"- {rel}" for rel in self.outputs(stage)],
            "",
            "Parameters:",
            "",
            *([f"- {k}: {v}" for k, v in stage["params"].items()]
              or ["- none"]),
            "",
        ]
        values = self.stage_values(stage)
        texts = [fill((PROMPTS_DIR / name).read_text(), values)
                 for name in ("common.md", kind["prompt"])]
        return "\n".join(lines) + "\n" + "\n".join(texts)

    def write_run_md(self) -> None:
        atomic_write(self.worktree / f"{OUT}/RUN.md", self.render_run_md())

    def render_run_md(self, state: dict | None = None) -> str:
        state = state or self.state
        stages = [state["stages"][i] for i in state["order"]]
        last = state.get("last_checkpoint")
        lines = [
            "# Step 1 run",
            "",
            "The runner writes this file. Do not edit it by hand.",
            "",
            f"- Status: {state['status']}",
            f"- Updated: {stamp(now())}",
            f"- Run base commit: {state['base_commit'][:11]}",
            "- Last completed checkpoint: " + (
                f"{last['stage']} ({last['commit'][:11]})" if last
                else "none"),
            f"- Push pending: {state['push']['pending']}",
        ]
        if state["status"] == "stopped":
            lines.append(f"- Stop reason: {state.get('stop_reason', '')}")
        lines += ["", "## Next step", ""]
        lines += self.next_step_lines(state, stages)
        lines += ["", "## Tools", ""]
        pauses = [("claude", state["tools"]["claude"])]
        pauses += [(f"claude ({name})", info)
                   for name, info in state.get("accounts", {}).items()]
        pauses.append(("codex", state["tools"]["codex"]))
        for tool, info in pauses:
            if info["paused_until"] > now():
                lines.append(f"- {tool}: paused until "
                             f"{stamp(info['paused_until'])}. {info['reason']}")
            else:
                lines.append(f"- {tool}: available")
        lines += ["", "## Stages", "",
                  "| Stage | Tool | Status | Attempts | Result | Commit |",
                  "|---|---|---|---|---|---|"]
        for s in stages:
            result = s.get("result") or {}
            verdict = {True: "pass", False: "fail"}.get(result.get("passed"),
                                                        "")
            lines.append(f"| {s['id']} | {s['tool']} | {s['status']} | "
                         f"{len(s['attempts'])} | {verdict} | "
                         f"{(s['commit'] or '')[:10]} |")
        camera = state.get("camera")
        lines += ["", "## Camera", ""]
        if camera is None:
            lines.append("- No camera stage is open. The last cleanup was "
                         "verified.")
        else:
            lines.append(f"- Stage {camera['stage']} is open. Driver groups: "
                         f"{camera['pgids']}. Cleanup verified: no.")
        if state.get("baseline"):
            lines.append(f"- Baseline values: {json.dumps(state['baseline'])}")
        if state["errors"]:
            lines += ["", "## Errors", ""]
            for error in state["errors"][-10:]:
                detail = error["detail"].replace("\n", " ")[:400]
                lines.append(f"- {error['time']} {error['kind']} "
                             f"{error['stage'] or ''}: {detail}")
        return "\n".join(lines) + "\n"

    def next_step_lines(self, state: dict, stages: list[dict]) -> list[str]:
        command = f"python3 {HARNESS}/runner/run.py"
        if state["status"] == "complete":
            return [f"The run is complete. Read {OUT}/report.md.", "",
                    "After this commit, the runner pushes and checks that "
                    "the remote branch has it. If the push fails, the runner "
                    "prints the retry command and writes it to "
                    "final-status.txt in the run folder."]
        lines = []
        for s in stages:
            if s["status"] in ("done", "skipped"):
                continue
            if s["status"] != "pending" or s["attempts"]:
                last = s["attempts"][-1] if s["attempts"] else {}
                lines.append(f"- Unfinished: {s['id']} ({s['tool']}), status "
                             f"{s['status']}, last outcome "
                             f"{last.get('outcome') or 'running'}.")
        if state["status"] == "stopped":
            lines += ["", "The run stopped. What to do:", "",
                      state.get("stop_action") or "Read the stop reason and "
                      "the errors below, and fix the cause.", "",
                      "Then run this command from the worktree root to "
                      "resume from the last checkpoint:", "",
                      f"    {command}"]
        else:
            lines += ["", "If the workstation restarted, run this command "
                      "from the worktree root. The runner resumes from the "
                      "last checkpoint:", "", f"    {command}"]
        return lines


# --- Entry point --------------------------------------------------------------


def interrupted(signum, frame) -> None:
    raise KeyboardInterrupt(f"signal {signum}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Runs the step 1 harness.")
    parser.add_argument("--settings", type=Path, default=SETTINGS_FILE)
    parser.add_argument("--stop-before", default="", choices=["", *KINDS],
                        help="stop the run before the first stage of this "
                             "kind, for a rehearsal")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    return Runner(args.settings, args.stop_before).run()


if __name__ == "__main__":
    sys.exit(main())
