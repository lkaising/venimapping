# ------------------------------------------------------------------------------
#  Filename: fake_agent.py
#
#  Purpose:  Stands in for the claude and codex CLIs in the dry run. Each call
#            plays the next behavior that the scenario lists for its task.
#
#  Usage:    python3 fake_agent.py <claude|codex> [CLI arguments ignored]
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# --- Prompt parsing -----------------------------------------------------------


def section(prompt: str, heading: str) -> list[str]:
    lines = prompt.splitlines()
    start = lines.index(heading) + 2
    items = []
    for line in lines[start:]:
        if not line.startswith("- "):
            break
        items.append(line[2:])
    return [] if items == ["none"] else items


def field(prompt: str, name: str) -> str:
    match = re.search(rf"^- {re.escape(name)}: (.+)$", prompt, re.MULTILINE)
    return match.group(1).strip()


# --- Behaviors ----------------------------------------------------------------


def next_behavior(state_dir: Path, scenario: dict, task: str) -> str:
    counter = state_dir / f"{task}.count"
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    plan = scenario.get("tasks", {}).get(task, {}).get("attempts", ["ok"])
    return plan[count] if count < len(plan) else "ok"


def peers_visible(prompt: str, task: str, run_dir: Path, tool: str) -> list:
    worktree = Path(field(prompt, "Worktree (read only)"))
    other = "codex" if tool == "claude" else "claude"
    visible = []
    required = section(prompt,
                       "Required outputs, relative to the output root:")
    for rel in required:
        peer = worktree / rel.replace(f"/{tool}/", f"/{other}/")
        if peer.exists():
            visible.append(str(peer))
    peer_task = task.replace(tool, other)
    for out in (run_dir / "attempts" / peer_task).glob("*/out"):
        try:
            visible += [str(p) for p in out.rglob("*") if p.is_file()]
        except PermissionError:
            pass
    return visible


def write_outputs(prompt: str, task: str, tool: str, scenario: dict,
                  run_dir: Path) -> None:
    root = Path(field(prompt, "Output root"))
    required = section(prompt, "Required outputs, relative to the output root:")
    optional = section(prompt, "Optional outputs, relative to the output root:")
    visible = peers_visible(prompt, task, run_dir, tool)
    for rel in required:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Stub output of {task}\n\nTool: {tool}\n\n"
                        f"Peer outputs visible: {json.dumps(visible)}\n")
    emit = scenario.get("tasks", {}).get(task, {}).get("emit")
    if emit is not None:
        target = next(rel for rel in optional
                      if rel.endswith(f"emits/{task}.json"))
        path = root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(emit, indent=2))


def failure_text(behavior: str) -> str:
    kind, _, arg = behavior.partition(":")
    if kind == "transient":
        return ("API Error: 529 {\"type\":\"error\",\"error\":{\"type\":"
                "\"overloaded_error\",\"message\":\"Overloaded\"}}")
    if kind == "transient-codex":
        return ("stream disconnected before completion: error sending "
                "request for url (https://chatgpt.com/backend-api/codex)")
    if kind == "quota-epoch":
        return f"Claude AI usage limit reached|{int(time.time()) + int(arg)}"
    if kind == "quota-tryagain":
        moment = datetime.datetime.now() + datetime.timedelta(seconds=int(arg))
        moment = moment.replace(second=0, microsecond=0)
        moment += datetime.timedelta(minutes=1)
        day = moment.day
        suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd",
                                               3: "rd"}.get(day % 10, "th")
        text = moment.strftime(f"%b {day}{suffix}, %Y %-I:%M %p")
        return ("You've hit your usage limit. Upgrade to Pro "
                "(https://chatgpt.com/explore/pro), visit "
                "https://chatgpt.com/codex/settings/usage to purchase more "
                f"credits or try again at {text}.")
    if kind == "quota-noreset":
        return "You've hit your usage limit."
    return "API Error: 400 invalid_request_error: dry run unrecognized failure"


def report(tool: str, ok: bool, text: str) -> int:
    if tool == "claude":
        print(json.dumps({"type": "result",
                          "subtype": "success",
                          "is_error": not ok,
                          "result": "done" if ok else text}))
        return 0 if ok else 1
    print(json.dumps({"type": "thread.started", "thread_id": "dryrun"}))
    print(json.dumps({"type": "turn.started"}))
    if ok:
        print(json.dumps({"type": "item.completed",
                          "item": {"type": "agent_message", "text": "done"}}))
        print(json.dumps({"type": "turn.completed", "usage": {}}))
        return 0
    print(json.dumps({"type": "error", "message": text}))
    print(json.dumps({"type": "turn.failed", "error": {"message": text}}))
    return 1


# --- Entry point --------------------------------------------------------------


def main() -> int:
    tool = sys.argv[1]
    prompt = sys.stdin.read()
    task = re.search(r"^# Task (\S+)$", prompt, re.MULTILINE).group(1)
    scenario = json.loads(Path(os.environ["PLANRUN_FAKE_SCENARIO"]).read_text())
    state_dir = Path(os.environ["PLANRUN_FAKE_STATE"])
    run_dir = Path(os.environ["PLANRUN_FAKE_RUN_DIR"])
    behavior = next_behavior(state_dir, scenario, task)
    with open(state_dir / "calls.log", "a") as log:
        log.write(f"{time.time():.3f} {tool} {task} {behavior}\n")
    if behavior.startswith("stream:"):
        streaming = state_dir / "streaming"
        (state_dir / "stream-started.log").open("a").write(
            f"{time.time():.3f}\n")
        streaming.touch()
        time.sleep(float(behavior.split(":")[1]))
        (state_dir / "stream-on-at-end").write_text(str(streaming.exists()))
        behavior = "ok"
    if behavior == "decoy":
        decoy = subprocess.Popen(
            [sys.executable, str(Path(__file__).parent / "vimbax_camera_node")],
            env={**os.environ, "PLANRUN_DECOY": "1"},
            start_new_session=True, stdin=subprocess.DEVNULL)
        time.sleep(0.5)
        (state_dir / "decoy-started").write_text(str(decoy.pid))
        behavior = "ok"
    if behavior == "ok":
        write_outputs(prompt, task, tool, scenario, run_dir)
        return report(tool, True, "")
    return report(tool, False, failure_text(behavior))


if __name__ == "__main__":
    sys.exit(main())
