# ------------------------------------------------------------------------------
#  Filename: run.py
#
#  Purpose:  Runs the Claude and Codex planning tasks for the image acquisition
#            design one at a time, checkpoints each result on the planning
#            branch, and pauses or stops on tool failures.
#
#  Usage:    python3 docs/architecture/image-acquisition-planning/runner/run.py
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

# --- Configuration ------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = RUNNER_DIR.parent / "prompts"
PLAN_FILE = RUNNER_DIR / "plan.json"
SETTINGS_FILE = RUNNER_DIR / "settings.json"

EXIT_COMPLETE = 0
EXIT_STOPPED = 2
EXIT_COMPLETE_LOCAL = 3

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
PARAM_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9,._-]{0,127}$")
FEATURE_TYPES = ("float", "int", "enum", "bool")

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


class Stop(Exception):
    """Ends the run with a recorded error that needs a person to look at."""


# --- Small helpers ------------------------------------------------------------


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
    text = text.strip()
    return text if len(text) <= limit else text[-limit:]


def fill(pattern: str, values: dict[str, str]) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: values[m.group(1)], pattern)


def fill_known(text: str, values: dict[str, str]) -> str:
    return re.sub(r"\{(\w+)\}",
                  lambda m: values.get(m.group(1), m.group(0)), text)


def kill_group(pgid: int, grace_s: float) -> None:
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
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if any(os.path.basename(a.decode(errors="replace")) == name
               for a in argv[:2]):
            found.append(int(entry.name))
    return found


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
    def __init__(self, settings_path: Path) -> None:
        self.settings = json.loads(settings_path.read_text())
        self.plan = json.loads(PLAN_FILE.read_text())
        self.worktree = Path(self.git(
            "rev-parse", "--show-toplevel", cwd=RUNNER_DIR).strip())
        self.run_dir = Path(self.settings["run_dir"])
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "state.json"
        self.planning = self.plan["planning_dir"]
        self.camera_env_cache: dict[str, str] | None = None
        self.camera_lock = None
        self.camera_process: subprocess.Popen | None = None
        self.lock = open(self.run_dir / "runner.lock", "w")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit("another runner holds " + str(self.run_dir))
        self.state = self.load_state()

    # --- State ----------------------------------------------------------------

    def load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        state = {
            "status": "running", "tasks": {}, "order": [], "errors": [],
            "events": [], "rounds": {}, "camera": None,
            "last_checkpoint": None,
            "push": {"pending": False, "failures": 0, "last_error": ""},
            "tools": {t: {"paused_until": 0, "quota_hits": 0, "reason": ""}
                      for t in ("claude", "codex")},
        }
        for spec in self.plan["initial"]:
            self.add_task(state, spec, emitted_by=None)
        return state

    def add_task(self, state: dict, spec: dict, emitted_by: str | None) -> None:
        state["tasks"][spec["id"]] = {
            "id": spec["id"], "template": spec["template"],
            "tool": spec["tool"], "params": spec.get("params", {}),
            "deps": list(spec.get("deps", [])), "status": "pending",
            "attempts": [], "commit": None, "not_before": 0,
            "transient_failures": 0, "camera": spec.get("camera"),
            "emitted_by": emitted_by,
        }
        state["order"].append(spec["id"])

    def save(self) -> None:
        atomic_write(self.state_path, json.dumps(self.state, indent=2))

    def event(self, text: str) -> None:
        self.state["events"].append(f"{stamp(now())} {text}")
        self.state["events"] = self.state["events"][-200:]
        with open(self.run_dir / "events.log", "a", encoding="utf-8") as log:
            log.write(f"{stamp(now())} {text}\n")
        print(f"[runner] {text}", flush=True)

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

    def commit(self, paths: list[str], subject: str,
               trailers: dict[str, str]) -> str:
        message = subject + "\n\n" + "\n".join(
            f"{k}: {v}" for k, v in trailers.items())
        self.git("add", "--", *paths)
        self.git("commit", "--quiet", "-m", message, "--", *paths)
        return self.head()

    def find_commit(self, task_id: str, attempt: int) -> str | None:
        found = self.git(
            "log", "-n", "1", "--format=%H", "--all-match",
            f"--grep=^Planning-Task: {task_id}$",
            f"--grep=^Planning-Attempt: {attempt}$").strip()
        return found or None

    def push(self) -> None:
        push = self.state["push"]
        if not push["pending"]:
            return
        output = self.git("push", "--quiet", "-u", self.settings["remote"],
                          f"HEAD:{self.settings['branch']}", check=False)
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

    def record_error(self, kind: str, task: str | None,
                     attempt: int | None, detail: str) -> None:
        self.state["errors"].append({
            "time": stamp(now()), "kind": kind, "task": task,
            "attempt": attempt, "detail": excerpt(detail)})
        self.event(f"error ({kind}) {task or ''}: {excerpt(detail, 200)}")

    def checkpoint_run_md(self, subject: str,
                          event: str = "run-record") -> None:
        run_md = f"{self.planning}/RUN.md"
        atomic_write(self.worktree / run_md, self.render_run_md())
        self.git("add", "--", run_md)
        unchanged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", run_md],
            cwd=self.worktree).returncode == 0
        if unchanged:
            return
        self.git("commit", "--quiet", "-m",
                 subject + f"\n\nPlanning-Event: {event}", "--", run_md)
        self.state["push"]["pending"] = True
        self.save()
        self.push()

    # --- Templates ------------------------------------------------------------

    def template(self, task: dict) -> dict:
        return self.plan["templates"][task["template"]]

    def values(self, task: dict) -> dict[str, str]:
        tool = task["tool"]
        values = {"P": self.planning, "V2": self.plan["v2_path"],
                  "tool": tool, "id": task["id"],
                  "other": "codex" if tool == "claude" else "claude"}
        values.update(task["params"])
        return values

    def own_sections(self, tool: str) -> list[str]:
        return [f"{self.planning}/{tool}/sections/{name}.md"
                for name, owner in self.plan["sections"].items()
                if owner == tool]

    def expand(self, task: dict, patterns: list[str]) -> list[str]:
        paths = []
        for pattern in patterns:
            if pattern == "@own-sections":
                paths.extend(self.own_sections(task["tool"]))
            else:
                paths.append(fill(pattern, self.values(task)))
        return paths

    def outputs(self, task: dict) -> tuple[list[str], list[str]]:
        template = self.template(task)
        return (self.expand(task, template["required"]),
                self.expand(task, template.get("optional", [])))

    def blind_group(self, task: dict) -> str | None:
        pattern = self.template(task).get("blind")
        return fill(pattern, self.values(task)) if pattern else None

    def group_members(self, group: str) -> list[dict]:
        return [self.state["tasks"][i] for i in self.state["order"]
                if self.blind_group(self.state["tasks"][i]) == group]

    # --- Scheduling -----------------------------------------------------------

    def ready(self, task: dict, at: float) -> bool:
        tasks = self.state["tasks"]
        return (task["status"] == "pending"
                and all(tasks[d]["status"] == "done" for d in task["deps"])
                and task["not_before"] <= at
                and self.state["tools"][task["tool"]]["paused_until"] <= at)

    def next_task(self) -> dict | None:
        at = now()
        candidates = []
        for position, task_id in enumerate(self.state["order"]):
            task = self.state["tasks"][task_id]
            if not self.ready(task, at):
                continue
            candidates.append((0 if task["attempts"] else 1, position, task))
        return min(candidates)[2] if candidates else None

    def next_wake(self) -> float | None:
        tasks = self.state["tasks"]
        times = []
        for task in tasks.values():
            if task["status"] != "pending":
                continue
            if not all(tasks[d]["status"] == "done" for d in task["deps"]):
                continue
            times.append(max(task["not_before"],
                             self.state["tools"][task["tool"]]["paused_until"]))
        return min(times) if times else None

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
                task = self.next_task()
                if task is not None:
                    self.execute(task)
                    continue
                if all(t["status"] == "done"
                       for t in self.state["tasks"].values()):
                    return self.finalize()
                wake = self.next_wake()
                if wake is None:
                    raise Stop("no task can run and none is waiting; "
                               "check the task dependencies in state.json")
                self.wait_until(wake)
        except Stop as stop:
            return self.stop(str(stop))

    def finalize(self) -> int:
        if not self.state.get("final_commit"):
            self.state["status"] = "complete"
            self.event("all tasks done")
            self.save()
            self.checkpoint_run_md(
                "docs(planning): record the completed planning run",
                event="run-complete")
            self.state["final_commit"] = self.head()
            self.save()
        else:
            self.state["push"]["pending"] = True
            self.push()
        final = self.state["final_commit"]
        branch = self.settings["branch"]
        if self.remote_head() == final:
            self.state["final_push"] = "verified"
            message = (f"The planning run is complete. "
                       f"{self.settings['remote']}/{branch} has the final "
                       f"commit {final[:11]}.")
            code = EXIT_COMPLETE
        else:
            self.state["final_push"] = "failed"
            message = (
                f"The design is complete locally, but "
                f"{self.settings['remote']}/{branch} does not have the final "
                f"commit {final[:11]}. Retry the push with this command:\n\n"
                f"    git -C {self.worktree} push {self.settings['remote']} "
                f"{final}:refs/heads/{branch}\n\n"
                f"Running the runner again also retries only the push.")
            code = EXIT_COMPLETE_LOCAL
        self.save()
        atomic_write(self.run_dir / "final-status.txt", message + "\n")
        print(f"[runner] {message}", flush=True)
        return code

    def stop(self, reason: str) -> int:
        self.state["status"] = "stopped"
        self.state["stop_reason"] = excerpt(reason)
        self.event(f"stopped: {excerpt(reason, 300)}")
        self.save()
        try:
            self.checkpoint_run_md("docs(planning): record the run stop")
        except Stop as again:
            self.write_run_md()
            print(f"[runner] could not commit the stop record: {again}",
                  file=sys.stderr)
        return EXIT_STOPPED

    # --- Recovery -------------------------------------------------------------

    def recover(self) -> None:
        if self.state["status"] == "stopped":
            self.event("restarting after a stop")
        for task_id in self.state["order"]:
            task = self.state["tasks"][task_id]
            if task["status"] == "running":
                self.recover_running(task)
            elif task["status"] == "importing":
                self.recover_importing(task)
            elif task["status"] == "held":
                os.chmod(task["attempts"][-1]["dir"], 0)
            elif task["status"] == "failed":
                task["status"] = "pending"
                task["transient_failures"] = 0
        if self.state["camera"] is not None:
            self.event("verifying camera cleanup left by an earlier attempt")
            self.camera_teardown()
        self.save()
        self.resume_groups()

    def resume_groups(self) -> None:
        groups = {self.blind_group(t) for t in self.state["tasks"].values()
                  if t["status"] == "held"}
        for group in sorted(groups):
            members = self.group_members(group)
            if all(m["status"] in ("held", "done") for m in members):
                for member in members:
                    if member["status"] == "held":
                        os.chmod(member["attempts"][-1]["dir"], 0o700)
                        self.import_task(member)

    def recover_running(self, task: dict) -> None:
        attempt = task["attempts"][-1]
        pid = attempt.get("pid")
        if pid and attempt.get("boot_id") == boot_id() and group_pids(pid):
            kill_group(pid, 5)
        if os.path.isdir(attempt["dir"]):
            os.chmod(attempt["dir"], 0o700)
        shutil.rmtree(Path(attempt["dir"]) / "out", ignore_errors=True)
        attempt["outcome"] = "interrupted"
        attempt["ended"] = now()
        task["status"] = "pending"
        self.event(f"{task['id']} attempt {attempt['n']} was interrupted; "
                   f"its output was discarded")

    def recover_importing(self, task: dict) -> None:
        attempt = task["attempts"][-1]
        found = self.find_commit(task["id"], attempt["n"])
        if found:
            self.event(f"{task['id']} was committed as {found[:10]} before "
                       f"the state update; marking it done")
            self.finish_import(task, found)
            return
        self.event(f"{task['id']} import was cut short; restoring its paths "
                   f"and importing again")
        for rel in attempt["imported"]:
            tracked = subprocess.run(
                ["git", "cat-file", "-e", f"HEAD:{rel}"],
                cwd=self.worktree, capture_output=True).returncode == 0
            if tracked:
                self.git("checkout", "HEAD", "--", rel)
            else:
                (self.worktree / rel).unlink(missing_ok=True)
        self.import_task(task)

    # --- Task execution -------------------------------------------------------

    def execute(self, task: dict) -> None:
        number = len(task["attempts"]) + 1
        attempt_dir = self.run_dir / "attempts" / task["id"] / str(number)
        out_dir = attempt_dir / "out"
        if attempt_dir.exists():
            shutil.rmtree(attempt_dir)
        out_dir.mkdir(parents=True)
        attempt = {"n": number, "dir": str(attempt_dir), "started": now(),
                   "ended": None, "pid": None, "outcome": None, "detail": ""}
        task["attempts"].append(attempt)

        attempt["start_commit"] = self.head()
        before = self.guard_snapshot()
        prompt = self.render_prompt(task, attempt_dir, out_dir)
        atomic_write(attempt_dir / "prompt.md", prompt)
        task["status"] = "running"
        self.save()
        self.event(f"start {task['id']} ({task['tool']}) attempt {number}")

        camera = bool(self.template(task).get("camera"))
        try:
            if camera:
                self.camera_begin(task, attempt_dir)
            try:
                result = self.invoke(task, attempt, prompt, attempt_dir,
                                     out_dir, camera)
            finally:
                if camera:
                    self.camera_teardown()
                    attempt["camera_cleanup"] = "verified"
        except Stop:
            task["status"] = "failed"
            attempt["outcome"] = "camera-error"
            attempt["ended"] = now()
            self.save()
            raise

        kind, detail = result
        attempt["ended"] = now()
        attempt["pid"] = None
        if kind == "ok":
            problems = self.validate(task, out_dir, before)
            if problems:
                kind, detail = "error", "output check failed: " + "; ".join(
                    problems)
        attempt["outcome"] = kind
        attempt["detail"] = excerpt(detail)

        if kind == "ok":
            self.succeed(task, attempt)
        elif kind == "transient":
            self.retry_transient(task, attempt, detail)
        elif kind == "quota":
            self.pause_on_quota(task, attempt, detail)
        else:
            task["status"] = "failed"
            self.record_error("task", task["id"], number, detail)
            self.save()
            raise Stop(f"{task['id']} attempt {number} failed with an error "
                       f"the runner does not retry. Logs: {attempt_dir}")

    def invoke(self, task: dict, attempt: dict, prompt: str, attempt_dir: Path,
               out_dir: Path, camera: bool) -> tuple[str, str]:
        tool = task["tool"]
        config = self.settings[tool]
        timeout_s = (self.settings["camera"]["task_timeout_s"] if camera
                     else config["timeout_s"])
        env = dict(self.camera_env() if camera else os.environ)
        env["ROS_LOG_DIR"] = str(Path("/tmp") / f"planrun-roslog-{task['id']}")
        env["PLANRUN_TASK"] = task["id"]
        if tool == "claude":
            command = [*config["command"], "-p", "--output-format", "json",
                       "--permission-mode", "acceptEdits",
                       "--permission-prompts", "none",
                       "--no-session-persistence",
                       "--disallowedTools", "WebFetch", "WebSearch",
                       "--allowedTools", *self.claude_tools(out_dir, camera)]
            if config.get("model"):
                command += ["--model", config["model"]]
        else:
            command = [*config["command"], "exec", "--json",
                       "--sandbox", "workspace-write",
                       "--skip-git-repo-check", "--ephemeral",
                       "--color", "never", "-C", str(out_dir),
                       "-o", str(attempt_dir / "last-message.md")]
            if camera:
                command += ["-c", "sandbox_workspace_write.network_access=true"]
            command.append("-")

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
            timed_out = self.wait_for_agent(process, attempt, timeout_s,
                                            camera)
        return classify(tool, process.returncode,
                        (attempt_dir / "stdout.log").read_text(),
                        (attempt_dir / "stderr.log").read_text(),
                        timed_out, timeout_s)

    def wait_for_agent(self, process: subprocess.Popen, attempt: dict,
                       timeout_s: int, camera: bool) -> bool:
        poll_s = self.settings["camera"]["stream_poll_s"] if camera else 5
        deadline = now() + timeout_s
        last_poll = now()
        while True:
            try:
                process.wait(timeout=poll_s)
                return False
            except subprocess.TimeoutExpired:
                pass
            if now() >= deadline:
                kill_group(process.pid, 5)
                process.wait()
                return True
            if camera:
                last_poll = self.enforce_stream_limit(attempt, last_poll)

    def enforce_stream_limit(self, attempt: dict, last_poll: float) -> float:
        settings = self.settings["camera"]
        polled = now()
        status = self.guard("status")
        streaming = bool(status.get("ok")
                         and (status.get("status") or {}).get("streaming"))
        watch = attempt.setdefault("stream", {"since": None, "limit_stops": 0})
        if not streaming:
            watch["since"] = None
            return polled
        if watch["since"] is None:
            watch["since"] = last_poll
        threshold = max(settings["max_stream_s"] - settings["stream_poll_s"]
                        - settings["stream_stop_margin_s"], 1.0)
        if polled - watch["since"] < threshold:
            return polled
        stopped = self.guard("stream-stop")
        if not stopped.get("ok"):
            raise Stop(f"the stream reached its {settings['max_stream_s']} s "
                       f"limit and the runner could not stop it: {stopped}")
        watch["limit_stops"] += 1
        watch["since"] = None
        self.event(f"stopped a stream that reached the "
                   f"{settings['max_stream_s']} s limit")
        self.save()
        return now()

    def claude_tools(self, out_dir: Path, camera: bool) -> list[str]:
        tools = ["Glob", "Grep", "TodoWrite"]
        tools += [f"Read(/{root}/**)" for root in
                  [str(self.worktree), *self.settings["read_roots"],
                   str(out_dir)]]
        for verb in ("log", "show", "diff", "grep", "ls-files", "blame"):
            tools.append(f"Bash(git -C {self.worktree} {verb}:*)")
            tools.append(f"Bash(git -C {self.settings['driver_source']} "
                         f"{verb}:*)")
        if camera:
            tools += ["Bash(ros2 topic:*)", "Bash(ros2 service:*)",
                      "Bash(ros2 node:*)", "Bash(ros2 interface:*)",
                      "Bash(ros2 run venimapping_camera "
                      "camera_gateway_probe:*)"]
        return tools

    def validate(self, task: dict, out_dir: Path, before: dict) -> list[str]:
        problems = []
        required, optional = self.outputs(task)
        written = sorted(str(p.relative_to(out_dir))
                         for p in out_dir.rglob("*")
                         if p.is_file() or p.is_symlink())
        for rel in required:
            path = out_dir / rel
            if not path.is_file() or path.is_symlink():
                problems.append(f"missing required output {rel}")
            elif path.stat().st_size == 0:
                problems.append(f"empty required output {rel}")
        for rel in written:
            if rel not in required and rel not in optional:
                problems.append(f"unexpected output {rel}")
            elif (out_dir / rel).is_symlink():
                problems.append(f"symlink output {rel}")
        after = self.guard_snapshot()
        for key, label in (("worktree_head", "worktree HEAD"),
                           ("worktree_status", "worktree files"),
                           ("driver_head", "driver HEAD"),
                           ("driver_status", "driver files")):
            if before[key] != after[key]:
                problems.append(f"{label} changed during the task")
        emit = out_dir / f"{self.planning}/coordinator/emits/{task['id']}.json"
        if emit.is_file():
            problems += self.check_emit(task, emit)
        return problems

    # --- Success, retry, and pause --------------------------------------------

    def succeed(self, task: dict, attempt: dict) -> None:
        tool_state = self.state["tools"][task["tool"]]
        tool_state.update(quota_hits=0, paused_until=0, reason="")
        task["transient_failures"] = 0
        group = self.blind_group(task)
        if group:
            task["status"] = "held"
            os.chmod(attempt["dir"], 0)
            self.save()
            members = self.group_members(group)
            if not all(m["status"] == "held" for m in members):
                self.event(f"{task['id']} held until blind group {group} "
                           f"finishes")
                return
            for member in members:
                os.chmod(member["attempts"][-1]["dir"], 0o700)
                self.import_task(member)
            return
        self.import_task(task)

    def retry_transient(self, task: dict, attempt: dict, detail: str) -> None:
        shutil.rmtree(Path(attempt["dir"]) / "out", ignore_errors=True)
        task["transient_failures"] += 1
        backoff = self.settings["transient_backoff_s"]
        if task["transient_failures"] > len(backoff):
            task["status"] = "failed"
            self.record_error("transient-exhausted", task["id"], attempt["n"],
                              detail)
            self.save()
            raise Stop(f"{task['id']} kept failing with transient errors "
                       f"after {len(backoff)} retries")
        delay = backoff[task["transient_failures"] - 1]
        task["status"] = "pending"
        task["not_before"] = now() + delay
        self.event(f"{task['id']} transient failure "
                   f"{task['transient_failures']}/{len(backoff)}; retry in "
                   f"{delay} s")
        self.save()

    def pause_on_quota(self, task: dict, attempt: dict, detail: str) -> None:
        shutil.rmtree(Path(attempt["dir"]) / "out", ignore_errors=True)
        tool = task["tool"]
        tool_state = self.state["tools"][tool]
        tool_state["quota_hits"] += 1
        reset = parse_reset(detail, now())
        if reset is not None:
            until = reset + self.settings["quota_margin_s"]
            how = f"reported reset {stamp(reset)}"
        else:
            steps = self.settings["quota_backoff_s"]
            until = now() + steps[min(tool_state["quota_hits"], len(steps)) - 1]
            how = "no reset time reported; backing off"
        tool_state["paused_until"] = until
        tool_state["reason"] = f"quota on {task['id']}: {how}"
        task["status"] = "pending"
        task["not_before"] = until
        attempt["resume_at"] = until
        self.event(f"{tool} paused on quota until {stamp(until)} ({how}); "
                   f"{task['id']} resumes with {tool}")
        self.save()
        self.checkpoint_run_md(f"docs(planning): record the {tool} quota pause")

    # --- Import and checkpoint ------------------------------------------------

    def import_task(self, task: dict) -> None:
        attempt = task["attempts"][-1]
        out_dir = Path(attempt["dir"]) / "out"
        files = sorted(str(p.relative_to(out_dir)) for p in out_dir.rglob("*")
                       if p.is_file())
        run_md = f"{self.planning}/RUN.md"
        imported = files + [run_md]
        if self.template(task).get("camera"):
            imported.append(f"{self.planning}/camera-log.md")
        attempt["imported"] = imported
        task["status"] = "importing"
        self.save()

        for rel in files:
            target = self.worktree / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(out_dir / rel, target)
        if self.template(task).get("camera"):
            self.append_camera_log(task, attempt)

        projected = json.loads(json.dumps(self.state))
        projected["tasks"][task["id"]]["status"] = "done"
        projected["last_checkpoint"] = {"task": task["id"],
                                        "commit": "this commit"}
        atomic_write(self.worktree / run_md, self.render_run_md(projected))

        subject = "docs(planning): " + fill(self.template(task)["commit"],
                                            self.values(task))
        found = self.commit(imported, subject, {
            "Planning-Task": task["id"], "Planning-Attempt": str(attempt["n"]),
            "Planning-Tool": task["tool"]})
        self.finish_import(task, found)

    def finish_import(self, task: dict, commit: str) -> None:
        task["status"] = "done"
        task["commit"] = commit
        self.state["last_checkpoint"] = {"task": task["id"], "commit": commit}
        self.apply_emit(task)
        self.state["push"]["pending"] = True
        self.event(f"checkpoint {commit[:10]} for {task['id']}")
        self.save()
        self.push()

    def append_camera_log(self, task: dict, attempt: dict) -> None:
        log = self.worktree / f"{self.planning}/camera-log.md"
        report = Path(attempt["dir"]) / "camera-cleanup.json"
        cleanup = json.loads(report.read_text()) if report.exists() else {}
        entry = [
            f"## {task['params'].get('check', task['id'])} "
            f"({task['tool']}, {stamp(attempt['started'])})",
            "",
            f"Question: {(task.get('camera') or {}).get('question', '-')}",
            "",
            f"Result file: `{self.outputs(task)[0][0]}`",
            "",
            "Runner cleanup:",
            "",
            f"- Stream stopped and verified: {cleanup.get('stream_stopped')}",
            f"- Features restored and verified: "
            f"{cleanup.get('features_restored')}",
            f"- Driver processes left: {cleanup.get('driver_pids_left')}",
            "",
        ]
        header = "" if log.exists() else "# Camera checks\n\n"
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(header + "\n".join(entry) + "\n")

    # --- Emitted tasks --------------------------------------------------------

    def check_emit(self, task: dict, path: Path) -> list[str]:
        template = self.template(task)
        try:
            emit = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            return [f"emit file is not JSON: {error}"]
        problems = []
        allowed = template.get("emits", [])
        new_ids = {spec.get("id") for spec in emit.get("tasks", [])}
        known = set(self.state["tasks"]) | new_ids
        dispute_tools: dict[tuple[str, str], set[str]] = {}
        for spec in emit.get("tasks", []):
            label = spec.get("id", "?")
            name = spec.get("template")
            if name not in allowed:
                problems.append(f"{label}: {task['template']} cannot emit "
                                f"{name}")
                continue
            if not ID_PATTERN.match(str(label)) or label in self.state["tasks"]:
                problems.append(f"{label}: bad or duplicate task id")
            tool = spec.get("tool")
            if tool not in self.plan["templates"][name]["tools"]:
                problems.append(f"{label}: {name} cannot run on {tool}")
            params = spec.get("params", {})
            for key in self.plan["templates"][name].get("params", []):
                if not PARAM_PATTERN.match(str(params.get(key, ""))):
                    problems.append(f"{label}: missing or bad param {key}")
            for dep in spec.get("deps", []):
                if dep not in known:
                    problems.append(f"{label}: unknown dependency {dep}")
            for blocked in spec.get("blocks", []):
                if blocked not in template.get("may_block", []):
                    problems.append(f"{label}: may not block {blocked}")
            problems += self.check_ownership(spec, label, name, tool, params)
            if name.startswith("dispute-"):
                dispute_tools.setdefault(
                    (name, params.get("issue", "")), set()).add(tool)
            if name == "camera-check":
                problems += self.check_camera_spec(label, spec.get("camera"))
            if name == "integrate":
                problems += self.check_round(task, emit, label, params)
        for (name, issue), tools in dispute_tools.items():
            if tools != {"claude", "codex"}:
                problems.append(f"{name} for {issue} needs one task per tool")
        return problems

    def check_ownership(self, spec: dict, label: str, name: str, tool: str,
                        params: dict) -> list[str]:
        if name not in ("fix", "recheck"):
            return []
        problems = []
        for section in str(params.get("sections", "")).split(","):
            owner = self.plan["sections"].get(section)
            if owner is None:
                problems.append(f"{label}: unknown section {section}")
            elif name == "fix" and owner != tool:
                problems.append(f"{label}: {section} belongs to {owner}")
            elif name == "recheck" and owner == tool:
                problems.append(f"{label}: {tool} cannot recheck its own "
                                f"section {section}")
        return problems

    def check_camera_spec(self, label: str, camera: dict | None) -> list[str]:
        if not isinstance(camera, dict) or not camera.get("question"):
            return [f"{label}: camera-check needs a camera.question"]
        problems = []
        for feature in camera.get("features", []):
            if (not isinstance(feature, dict) or not feature.get("name")
                    or feature.get("type") not in FEATURE_TYPES):
                problems.append(f"{label}: bad feature entry {feature}")
        return problems

    def check_round(self, task: dict, emit: dict, label: str,
                    params: dict) -> list[str]:
        current = int(task["params"].get("round", "0"))
        if params.get("round") != str(current + 1):
            return [f"{label}: next integrate round must be {current + 1}"]
        if current + 1 > self.settings["max_integrate_rounds"]:
            return [f"{label}: integrate round limit reached"]
        if "prose" not in emit_blocks(emit, label):
            return [f"{label}: next integrate round must block prose"]
        return []

    def apply_emit(self, task: dict) -> None:
        path = (self.worktree /
                f"{self.planning}/coordinator/emits/{task['id']}.json")
        if not path.is_file() or task["commit"] is None:
            return
        emit = json.loads(path.read_text())
        specs = emit.get("tasks", [])
        if task["template"] == "integrate":
            specs = self.limit_rounds(task, emit, specs)
        for spec in specs:
            if spec["id"] in self.state["tasks"]:
                continue
            self.add_task(self.state, spec, emitted_by=task["id"])
            for blocked in spec.get("blocks", []):
                deps = self.state["tasks"][blocked]["deps"]
                if spec["id"] not in deps:
                    deps.append(spec["id"])
            self.event(f"{task['id']} added {spec['id']} ({spec['tool']})")

    def limit_rounds(self, task: dict, emit: dict, specs: list) -> list:
        rounds = self.state["rounds"]
        closed = int((emit.get("progress") or {}).get("closed", 0))
        rounds[task["params"]["round"]] = closed
        history = [rounds[k] for k in sorted(rounds, key=int)]
        if len(history) >= 2 and history[-1] == 0 and history[-2] == 0:
            self.event("two integrate rounds closed no issues; moving to the "
                       "prose pass without more rounds")
            return []
        return specs

    # --- Camera ---------------------------------------------------------------

    def camera_env(self) -> dict[str, str]:
        if self.camera_env_cache is None:
            script = self.settings["camera"]["env_script"]
            result = subprocess.run(
                ["bash", "-c", 'source "$1" >/dev/null 2>&1 && env -0', "_",
                 script], capture_output=True, stdin=subprocess.DEVNULL)
            if result.returncode != 0:
                raise Stop(f"could not source {script}")
            pairs = [item.split(b"=", 1) for item in result.stdout.split(b"\0")
                     if b"=" in item]
            self.camera_env_cache = {k.decode(): v.decode() for k, v in pairs}
        return self.camera_env_cache

    def guard(self, *args: str) -> dict:
        command = [part.replace("{runner}", str(RUNNER_DIR))
                   for part in self.settings["camera"]["guard"]]
        result = subprocess.run(
            [*command, *args, "--namespace",
             self.settings["camera"]["namespace"]],
            env=self.camera_env(), capture_output=True, text=True,
            stdin=subprocess.DEVNULL, timeout=120)
        try:
            report = json.loads(result.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            report = {"ok": False, "error": excerpt(result.stderr, 600)}
        if result.returncode != 0:
            report["ok"] = False
        return report

    def camera_begin(self, task: dict, attempt_dir: Path) -> None:
        settings = self.settings["camera"]
        self.camera_lock = open(self.run_dir / "camera.lock", "w")
        try:
            fcntl.flock(self.camera_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Stop("another process holds the camera lock")
        if pids_named(settings["driver_process"]):
            raise Stop("a camera driver is already running; the runner will "
                       "not take the camera from it")
        features = (task.get("camera") or {}).get("features", [])
        features_file = attempt_dir / "camera-features.json"
        atomic_write(features_file, json.dumps(features))
        self.state["camera"] = {
            "task": task["id"], "attempt_dir": str(attempt_dir),
            "features_file": str(features_file), "originals": None,
            "pgid": None}
        self.save()
        self.camera_launch(attempt_dir)
        originals = attempt_dir / "camera-originals.json"
        report = self.guard("snapshot", "--features", str(features_file),
                            "--out", str(originals))
        if not report.get("ok"):
            raise Stop(f"could not read the original camera feature values: "
                       f"{report}")
        self.state["camera"]["originals"] = str(originals)
        self.save()

    def camera_launch(self, attempt_dir: Path) -> None:
        settings = self.settings["camera"]
        log = open(attempt_dir / "driver.log", "a")
        process = subprocess.Popen(
            settings["launch"], env=self.camera_env(), stdout=log,
            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True)
        self.camera_process = process
        self.state["camera"]["pgid"] = process.pid
        self.state["camera"]["boot_id"] = boot_id()
        self.save()
        report = self.guard("wait", "--timeout",
                            str(settings["ready_timeout_s"]))
        if not report.get("ok"):
            raise Stop(f"the camera driver did not become ready: {report}")

    def own_launch_group(self, camera: dict) -> int | None:
        pgid = camera.get("pgid")
        if not pgid or camera.get("boot_id") != boot_id():
            return None
        return pgid if group_pids(pgid) else None

    def camera_teardown(self) -> None:
        camera = self.state["camera"]
        if camera is None:
            return
        settings = self.settings["camera"]
        attempt_dir = Path(camera["attempt_dir"])
        attempt_dir.mkdir(parents=True, exist_ok=True)
        report: dict = {"stream_stopped": False, "features_restored": False,
                        "driver_pids_left": None}
        failures = []
        try:
            if not self.guard("wait", "--timeout", "5").get("ok"):
                ours = self.own_launch_group(camera)
                if ours:
                    kill_group(ours, 10)
                self.camera_launch(attempt_dir)
        except Stop as stop:
            failures.append(str(stop))

        if not failures:
            stopped = self.guard("stream-stop")
            report["stream_stopped"] = bool(stopped.get("ok"))
            if not stopped.get("ok"):
                failures.append(f"could not verify that streaming stopped: "
                                f"{stopped}")
            if camera.get("originals"):
                restored = self.guard("restore", "--originals",
                                      camera["originals"])
                report["features_restored"] = bool(restored.get("ok"))
                if not restored.get("ok"):
                    failures.append(f"could not restore and verify the camera "
                                    f"features: {restored}")
            else:
                report["features_restored"] = "no feature values were saved"

        ours = self.own_launch_group(camera)
        if ours:
            kill_group(ours, 15)
        if self.camera_process is not None:
            try:
                self.camera_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        left = group_pids(ours) if ours else []
        foreign = [pid for pid in pids_named(settings["driver_process"])
                   if pid not in left]
        report["driver_pids_left"] = left
        report["foreign_driver_pids"] = foreign
        if left:
            failures.append(f"processes from the driver launch of the runner "
                            f"are still running: {left}")
        else:
            camera["pgid"] = None
        if foreign:
            failures.append(f"a camera driver that the runner did not start "
                            f"is running, and the runner left it alone: "
                            f"{foreign}")
        ros2 = shutil.which("ros2", path=self.camera_env().get("PATH"))
        if ros2:
            subprocess.run([ros2, "daemon", "stop"], env=self.camera_env(),
                           capture_output=True, stdin=subprocess.DEVNULL)

        if failures:
            report["errors"] = failures
            atomic_write(attempt_dir / "camera-cleanup.json",
                         json.dumps(report, indent=2))
            camera["dirty"] = True
            detail = " | ".join(failures)
            self.record_error("camera-cleanup", camera["task"], None, detail)
            self.save()
            raise Stop(f"camera cleanup could not be verified: {detail}")
        atomic_write(attempt_dir / "camera-cleanup.json",
                     json.dumps(report, indent=2))
        self.state["camera"] = None
        if self.camera_lock is not None:
            fcntl.flock(self.camera_lock, fcntl.LOCK_UN)
            self.camera_lock.close()
            self.camera_lock = None
        self.event("camera cleanup verified")
        self.save()

    # --- Prompts and RUN.md ---------------------------------------------------

    def render_prompt(self, task: dict, attempt_dir: Path,
                      out_dir: Path) -> str:
        required, optional = self.outputs(task)
        done = [t for t in (self.state["tasks"][i] for i in self.state["order"])
                if t["status"] == "done"]
        lines = [
            f"# Task {task['id']}",
            "",
            f"- Tool: {task['tool']}",
            f"- Template: {task['template']}",
            f"- Parameters: {json.dumps(task['params'])}",
            f"- Date: {datetime.date.today().isoformat()}",
            f"- Worktree (read only): {self.worktree}",
            f"- Worktree checkpoint: {self.head()}",
            f"- Planning folder: {self.worktree / self.planning}",
            f"- v1 design: {self.worktree / self.plan['v1_path']}",
            f"- v2 design: {self.worktree / self.plan['v2_path']}",
            f"- Driver source (read only): {self.settings['driver_source']}",
            f"- Other read-only references: "
            f"{', '.join(self.settings['read_roots'])}",
            f"- Output root: {out_dir}",
            "",
            "Required outputs, relative to the output root:",
            "",
            *[f"- {rel}" for rel in required],
            "",
            "Optional outputs, relative to the output root:",
            "",
            *([f"- {rel}" for rel in optional] or ["- none"]),
            "",
            "Section owners:",
            "",
            *[f"- {name}: {owner}"
              for name, owner in self.plan["sections"].items()],
            "",
            "Completed tasks (read their outputs in the worktree):",
            "",
            *([f"- {t['id']} ({t['tool']}) commit {t['commit'][:10]}"
               for t in done] or ["- none"]),
            "",
        ]
        if self.template(task).get("camera"):
            camera = task.get("camera") or {}
            lines += [
                "Camera assignment:",
                "",
                f"- Namespace: {self.settings['camera']['namespace']}",
                f"- Question: {camera.get('question', '-')}",
                f"- Features you may change: "
                f"{json.dumps(camera.get('features', []))}",
                "- Longest stream: "
                f"{self.settings['camera']['max_stream_s']} s. The runner "
                "stops any stream that reaches this limit.",
                "",
            ]
        template = self.template(task)
        values = self.values(task)
        values["emits"] = ", ".join(template.get("emits", []))
        values["may_block"] = ", ".join(template.get("may_block", [])) or "none"
        parts = ["common.md", template["prompt"]]
        if template.get("emits"):
            parts.append("emit.md")
        texts = [fill_known((PROMPTS_DIR / name).read_text(), values)
                 for name in parts]
        return "\n".join(lines) + "\n" + "\n".join(texts)

    def write_run_md(self) -> None:
        atomic_write(self.worktree / f"{self.planning}/RUN.md",
                     self.render_run_md())

    def render_run_md(self, state: dict | None = None) -> str:
        state = state or self.state
        tasks = [state["tasks"][i] for i in state["order"]]
        last = state.get("last_checkpoint")
        waiting = [t for t in tasks if t["status"] != "done"]
        lines = [
            "# Planning run",
            "",
            "The runner writes this file. Do not edit it by hand.",
            "",
            f"- Status: {state['status']}",
            f"- Updated: {stamp(now())}",
            "- Last completed checkpoint: " + (
                f"{last['task']} ({last['commit'][:11]})" if last
                else "none"),
            f"- Push pending: {state['push']['pending']}",
        ]
        if state.get("stop_reason") and state["status"] == "stopped":
            lines.append(f"- Stop reason: {state['stop_reason']}")
        lines += ["", "## Next step", ""]
        lines += self.next_step_lines(state, waiting)
        lines += ["", "## Tools", ""]
        for tool, info in state["tools"].items():
            if info["paused_until"] > now():
                lines.append(f"- {tool}: paused until "
                             f"{stamp(info['paused_until'])}. {info['reason']}")
            else:
                lines.append(f"- {tool}: available")
        lines += ["", "## Tasks", "",
                  "| Task | Tool | Status | Attempts | Commit |",
                  "|---|---|---|---|---|"]
        for t in tasks:
            lines.append(f"| {t['id']} | {t['tool']} | {t['status']} | "
                         f"{len(t['attempts'])} | {(t['commit'] or '')[:10]} |")
        if state["errors"]:
            lines += ["", "## Errors", ""]
            for error in state["errors"][-10:]:
                detail = error["detail"].replace("\n", " ")[:400]
                lines.append(f"- {error['time']} {error['kind']} "
                             f"{error['task'] or ''}: {detail}")
        return "\n".join(lines) + "\n"

    def next_step_lines(self, state: dict, waiting: list[dict]) -> list[str]:
        command = ("python3 " + str(Path(self.planning) / "runner" / "run.py"))
        if state["status"] == "complete":
            return ["The run is complete. Review the v2 design.", "",
                    "After this commit, the runner pushes and checks that "
                    "the remote branch has it. If the push fails, the runner "
                    "prints the retry command and writes it to "
                    "final-status.txt in the run folder."]
        unfinished = [t for t in waiting if t["status"] != "pending"
                      or t["attempts"]]
        lines = []
        for t in unfinished:
            last = t["attempts"][-1] if t["attempts"] else {}
            lines.append(f"- Unfinished: {t['id']} ({t['tool']}), status "
                         f"{t['status']}, last outcome "
                         f"{last.get('outcome') or 'running'}.")
        if state["status"] == "stopped":
            lines += ["", "The run stopped. Read the stop reason and the "
                      "errors below, fix the cause, then run this command "
                      "from the worktree root:", "", f"    {command}"]
        else:
            lines += ["", "If the workstation restarted, run this command "
                      "from the worktree root. The runner resumes from the "
                      "last checkpoint:", "", f"    {command}"]
        return lines


def emit_blocks(emit: dict, label: str) -> list[str]:
    for spec in emit.get("tasks", []):
        if spec.get("id") == label:
            return spec.get("blocks", [])
    return []


# --- Entry point --------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, default=SETTINGS_FILE)
    args = parser.parse_args()
    return Runner(args.settings).run()


if __name__ == "__main__":
    sys.exit(main())
