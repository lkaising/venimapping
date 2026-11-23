# ------------------------------------------------------------------------------
#  Filename: fake_agent.py
#
#  Purpose:  Stands in for the claude and codex CLIs in the dry run. Each call
#            plays the next behavior that the scenario lists for its stage,
#            and writes step 1 files with the bugs that the scenario names.
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

PKG = "src/venimapping_bringup"
OUT = "docs/architecture/image-acquisition-step-1/output"

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


# --- Step 1 files -------------------------------------------------------------


def step1_files(bugs: list[str]) -> dict[str, str]:
    plugins = "" if "plugins" in bugs else (
        "    image_raw:\n"
        "      enable_pub_plugins: [\"image_transport/raw\"]\n")
    ros_time = "" if "use_ros_time" in bugs else "    use_ros_time: true\n"
    return {
        f"{PKG}/config/camera.yaml": (
            "# Fake camera.yaml for the dry run.\n"
            "/**/vimbax_camera:\n"
            "  ros__parameters:\n"
            "    camera_id: \"0GPF3\"\n"
            "    autostream: 0\n"
            "    buffer_count: 7\n"
            f"{ros_time}"
            "    use_sim_time: false\n"
            f"{plugins}"),
        f"{PKG}/config/acquisition_profile.yaml": (
            "/**:\n"
            "  ros__parameters:\n"
            "    use_sim_time: false\n"
            "    profile:\n"
            "      pixel_format: \"Mono8\"\n"
            "      width: 1296\n"
            "      height: 1032\n"
            "      trigger_mode: \"Off\"\n"
            "      acquisition_frame_rate_enable: true\n"
            "      acquisition_frame_rate: 30.0\n"
            "      exposure_time: 4999.455\n"
            "      allowed_formats: [\"Mono8\"]\n"),
        f"{PKG}/launch/camera.launch.py": (
            "# Fake launch file: declares use_ros_time and settings_file.\n"),
        f"{PKG}/CMakeLists.txt": (
            "SYNTAX ERROR\n" if "cmake" in bugs else
            "# Fake CMakeLists.txt with ament_add_pytest_test.\n"),
        f"{PKG}/package.xml": "<!-- Fake package.xml with test_depend. -->\n",
        f"{PKG}/test/test_camera_config.py": "# Fake test.\n",
    }


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_outputs(prompt: str, stage: str, plan: dict, behavior: str) -> None:
    root = Path(field(prompt, "Output root"))
    kind = field(prompt, "Kind")
    worktree = Path(field(prompt, "Worktree (read only)"))
    required = section(prompt, "Required outputs, relative to the output root:")
    if kind in ("implement", "repair") and behavior != "nochange":
        for rel, text in step1_files(plan.get("bugs", [])).items():
            write(root, rel, text)
    if kind == "review":
        findings = plan.get("findings", [
            {"id": "r1", "severity": "minor", "file": f"{PKG}/package.xml",
             "summary": "dry run finding"}])
        write(root, f"{OUT}/review.json", json.dumps({"findings": findings}))
        write(root, f"{OUT}/review.md", "# Review\n\n| Id |\n|---|\n" + "".join(
            f"| {f['id']} |\n" for f in findings))
    if kind == "fix":
        review = json.loads((worktree / f"{OUT}/review.json").read_text())
        write(root, f"{OUT}/fixes.md", "# Fixes\n\n" + "".join(
            f"- {f['id']}: Fixed\n" for f in review["findings"]))
        camera = root / f"{PKG}/config/camera.yaml"
        camera.write_text(camera.read_text() + "# Reviewed in the dry run.\n")
    for rel in required:
        if not (root / rel).exists():
            write(root, rel, f"# Notes of {stage}\n\nBehavior: {behavior}\n")
    if behavior == "forbidden":
        write(root, "src/venimapping_camera/CMakeLists.txt", "# forbidden\n")
        write(root, f"{PKG}/config/camera_settings.xml", "<forbidden/>\n")


# --- Behaviors ----------------------------------------------------------------


def next_behavior(state_dir: Path, plan: dict, stage: str) -> str:
    counter = state_dir / f"{stage}.count"
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    attempts = plan.get("attempts", ["ok"])
    return attempts[count] if count < len(attempts) else "ok"


def failure_text(behavior: str) -> str:
    kind, _, arg = behavior.partition(":")
    if kind == "transient":
        return ("API Error: 529 {\"type\":\"error\",\"error\":{\"type\":"
                "\"overloaded_error\",\"message\":\"Overloaded\"}}")
    if kind == "quota-epoch":
        return f"Claude AI usage limit reached|{int(time.time()) + int(arg)}"
    if kind == "quota-noreset":
        return "You've hit your usage limit."
    if kind == "quota-tryagain":
        moment = datetime.datetime.now() + datetime.timedelta(seconds=int(arg))
        return ("You've hit your usage limit. Try again at "
                f"{moment.strftime('%-I:%M %p')}.")
    return "API Error: 400 invalid_request_error: dry run unrecognized failure"


def report(tool: str, ok: bool, text: str) -> int:
    if tool == "claude":
        print(json.dumps({"type": "result", "subtype": "success",
                          "is_error": not ok,
                          "result": "done" if ok else text}))
        return 0 if ok else 1
    print(json.dumps({"type": "thread.started", "thread_id": "dryrun"}))
    print(json.dumps({"type": "turn.started"}))
    if ok:
        print(json.dumps({"type": "turn.completed", "usage": {}}))
        return 0
    print(json.dumps({"type": "error", "message": text}))
    print(json.dumps({"type": "turn.failed", "error": {"message": text}}))
    return 1


# --- Entry point --------------------------------------------------------------


def main() -> int:
    tool = sys.argv[1]
    prompt = sys.stdin.read()
    stage = re.search(r"^# Task (\S+)$", prompt, re.MULTILINE).group(1)
    scenario = json.loads(Path(os.environ["STEP1_FAKE_SCENARIO"]).read_text())
    state_dir = Path(os.environ["STEP1_FAKE_STATE"])
    plan = scenario.get("stages", {}).get(stage, {})
    behavior = next_behavior(state_dir, plan, stage)
    with open(state_dir / "agents.log", "a") as log:
        log.write(f"{time.time():.3f} {tool} {stage} {behavior} "
                  f"{os.environ.get('CLAUDE_CONFIG_DIR', '-')}\n")
    (state_dir / f"{stage}.prompt.md").write_text(prompt)
    if behavior.startswith("sleep:"):
        (state_dir / f"{stage}.sleeping").write_text(str(os.getpid()))
        time.sleep(float(behavior.split(":")[1]))
        behavior = "ok"
    if behavior == "decoy":
        node = Path(__file__).parent / "vimbax_camera_node"
        subprocess.Popen([sys.executable, str(node)],
                         env={**os.environ, "STEP1_DECOY": "1"},
                         start_new_session=True, stdin=subprocess.DEVNULL)
        time.sleep(0.5)
    if behavior in ("ok", "forbidden", "decoy", "nochange"):
        write_outputs(prompt, stage, plan, behavior)
        return report(tool, True, "")
    return report(tool, False, failure_text(behavior))


if __name__ == "__main__":
    sys.exit(main())
