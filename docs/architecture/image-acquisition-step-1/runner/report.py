# ------------------------------------------------------------------------------
#  Filename: report.py
#
#  Purpose:  Writes the step 1 report from the stage results in the runner
#            state: the exit check items, part A, the settings file, the
#            working assumptions that the run tested, the review, and the
#            camera cleanup.
#
#  Usage:    import report; report.render(state, settings, out, xml)
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import json

from common import stamp, now

# --- Configuration ------------------------------------------------------------

EXIT_ITEMS = [
    ("1", "`colcon build --packages-select venimapping_bringup` succeeds",
     ["E1"]),
    ("2", "`colcon test --packages-select venimapping_bringup` passes",
     ["E2"]),
    ("3", "Bring-up part A, steps 1 to 16", None),
    ("4", "`use_ros_time` prints `True`", ["E4"]),
    ("5", "`settings_file` is the installed path, and the file exists",
     ["E5"]),
    ("6", "`image_raw.enable_pub_plugins` is only `image_transport/raw`",
     ["E6"]),
    ("7", "`ros2 topic info` prints `Publisher count: 1`", ["E7"]),
    ("8", "No topic starts with `/vimbax_camera/image_raw/`", ["E8"]),
    ("9", "CLI reads of the seven profile values match the profile file",
     ["E9"]),
    ("9b", "CLI reads of the kept features outside the profile match the "
           "settings file (a runner check, not in v2)", ["E9b"]),
    ("10", "`camera_gateway_probe` passes", ["E10"]),
]

PART_A = {
    "A1": "Launch with `settings_file:=/nonexistent.xml`, log to "
          "`driver_control.log`",
    "A2": "Init wait on `driver_control.log`",
    "A3": "`grep -F 'Loading settings from file' driver_control.log`",
    "A4": "Step 3 printed a line",
    "A5": "Stop the driver",
    "A6": "Launch with the default arguments, log to `driver_a.log`",
    "A7": "Init wait on `driver_a.log`",
    "A8": "Write `ExposureTime` 10000.0",
    "A9": "Write `AcquisitionFrameRate` 20.0",
    "A10": "Read back both values",
    "A11": "Each value is within 0.001 of the written value",
    "A12": "Stop the driver",
    "A13": "Launch again with the default arguments, log to `driver_b.log`",
    "A14": "Init wait on `driver_b.log`",
    "A15": "`grep -F 'Loading settings from file' driver_a.log driver_b.log`",
    "A16": "Step 15 printed no line",
}


def cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")[:400]


def verdict(passed) -> str:
    return {True: "PASS", False: "FAIL"}.get(passed, "not run")


def last_passing(stages: list[dict], kind: str) -> dict | None:
    found = [s for s in stages if s["kind"] == kind and s["status"] == "done"
             and (s.get("result") or {}).get("passed")]
    return found[-1] if found else None


# --- Report -------------------------------------------------------------------


def render(state: dict, settings: dict, out: str, xml: str) -> str:
    stages = [state["stages"][i] for i in state["order"]]
    rig_stage = last_passing(stages, "rig")
    builds = [s for s in stages if s["kind"] == "build" and s["status"] == "done"
              and (s.get("result") or {}).get("passed")]
    build = builds[-1] if builds else None
    settings_stage = last_passing(stages, "settings")
    rig_result = (rig_stage or {}).get("result") or {}
    checks = {c["id"]: c for c in rig_result.get("checks", [])}
    checks.update({c["id"]: c for c in ((build or {}).get("result") or {})
                   .get("checks", [])})
    part_a = [checks.get(k) for k in PART_A]
    part_a_ok = all(c and c["passed"] for c in part_a)

    lines = [
        "# Step 1 report",
        "",
        "The runner writes this file from the results of the checks. Each "
        "check has a fixed pass rule in "
        "`docs/architecture/image-acquisition-step-1/runner/`.",
        "",
        f"- Written: {stamp(now())}",
        f"- Run base commit: `{state['base_commit'][:11]}`",
        f"- Rig check stage: {rig_stage['id'] if rig_stage else 'none'}, "
        f"logs in `{rig_result.get('log_dir', '-')}`",
        f"- Build and test stage: {build['id'] if build else 'none'}, logs in "
        f"`{((build or {}).get('result') or {}).get('log_dir', '-')}`",
        f"- Settings file stage: "
        f"{settings_stage['id'] if settings_stage else 'none'}",
        "",
        "## Exit check",
        "",
        "| Item | Check | Result | Key output |",
        "|---|---|---|---|",
    ]
    for item, text, ids in EXIT_ITEMS:
        if ids is None:
            lines.append(f"| {item} | {text} | {verdict(part_a_ok)} | "
                         f"See part A below |")
            continue
        found = checks.get(ids[0])
        lines.append(f"| {item} | {text} | "
                     f"{verdict(found['passed'] if found else None)} | "
                     f"{cell(found['detail']) if found else '-'} |")

    lines += ["", "## Part A, the controlled reopen", "",
              "| Step | Action | Result | Key output |", "|---|---|---|---|"]
    for key, text in PART_A.items():
        found = checks.get(key)
        lines.append(f"| {key[1:]} | {text} | "
                     f"{verdict(found['passed'] if found else None)} | "
                     f"{cell(found['detail']) if found else '-'} |")

    lines += settings_section(settings_stage, xml)
    lines += assumptions_section(rig_result, settings_stage, settings)
    lines += review_section(state, out)
    lines += cleanup_section(stages)
    lines += [
        "",
        "## Differences from the v2 command text",
        "",
        "1. The build uses `--symlink-install`, as the project README does.",
        "2. The CLI steps use `ros2 service call` on the driver services, "
        "with a time limit for each call.",
        "3. The runner stops the ROS daemon after each driver stop, so that "
        "no graph read sees an earlier driver. A graph read that does not "
        f"pass at once is repeated for up to "
        f"{settings['camera']['graph_retry_s']} s.",
        "4. The topic list check runs twice, 1 s apart. A plugin topic in "
        "either list fails the check.",
        "5. `camera_gateway_probe` runs with `enable_writes:=false` and "
        "`exercise_stream:=false`, its read-only defaults, set explicitly.",
        "6. The settings file is made on a driver that `ros2 run` starts with "
        "a runner parameter file and no `settings_file`.",
        "7. Part A step 11 passes a float readback within one camera "
        "increment of the written value, where v2 asks for 0.001. See the "
        "row for part A step 11 above.",
        f"8. The settings file policy is "
        f"`{settings['camera']['xml_denied_policy']}`. With `keep`, the "
        f"package copy holds only the profile features and the features "
        f"they depend on. With `strip`, it has no denied feature. v2 "
        f"installs the saved file as it is. See the camera settings file "
        f"section.",
        "",
    ]
    return "\n".join(lines)


def settings_section(stage: dict | None, xml: str) -> list[str]:
    lines = ["", "## Camera settings file", ""]
    if stage is None:
        return lines + ["No settings file stage passed."]
    result = stage["result"]
    scan = result.get("scan", {})
    lines += [f"The runner made `{xml}` in stage {stage['id']} with the steps "
              f"in v2 section 10. Logs: `{result.get('log_dir')}`.", "",
              "| Step | Result | Key output |", "|---|---|---|"]
    for check in result.get("checks", []):
        if check["id"].startswith("S"):
            lines.append(f"| {check['id']} | {verdict(check['passed'])} | "
                         f"{cell(check['detail'])} |")
    lines += ["", f"The saved file holds {scan.get('features', '?')} "
              f"features. Denied features: "
              f"{', '.join(scan.get('denied', [])) or 'none'}.", "",
              "| Feature | Expected | In the file | Match |",
              "|---|---|---|---|"]
    for name, info in (scan.get("profile") or {}).items():
        lines.append(f"| {name} | {info['expected']} | "
                     f"{cell(', '.join(info['found']) or 'absent')} | "
                     f"{'yes' if info['match'] else 'no'} |")
    stripped = result.get("stripped")
    if stripped:
        after = result.get("scan_after_strip", {})
        lines += ["", f"Policy `strip`: the runner removed {len(stripped)} "
                  f"denied names from the package copy, so the driver never "
                  f"writes them. The saved file in the logs is unchanged. "
                  f"This differs from v2 section 10, which installs the "
                  f"saved file as it is. The package copy holds "
                  f"{after.get('features', '?')} features. Removed: "
                  f"{', '.join(f'`{n}`' for n in stripped)}."]
    kept = result.get("kept")
    if kept is not None:
        after = result.get("scan_after_keep", {})
        absent = result.get("keep_absent") or []
        removed = result.get("removed") or []
        outside = sorted(set(kept) - set((scan.get("profile") or {}))
                         - {"TriggerSelector"})
        lines += ["", f"Policy `keep`: the package copy holds only the names "
                  f"in `camera.xml_keep_features` and "
                  f"`camera.xml_keep_selectors` of `settings.json`. The "
                  f"saved file in the logs is unchanged. This differs from "
                  f"v2 section 10, which installs the saved file as it is. "
                  f"The package copy holds {after.get('features', '?')} "
                  f"names: {', '.join(f'`{n}`' for n in kept)}. The runner "
                  f"removed {len(removed)} names; `results.json` of the "
                  f"settings stage lists them. Listed but not in the saved "
                  f"file: {', '.join(absent) or 'none'}.", "",
                  f"The driver writes these kept features outside the "
                  f"profile on each open: "
                  f"{', '.join(f'`{n}`' for n in outside) or 'none'}. Exit "
                  f"check 9b reads each one back after the reopen."]
        return lines
    others = scan.get("others") or {}
    lines += ["", f"The driver also writes each other writable feature of the "
              f"file on each open: {len(others)} names. v2 asks for a review "
              f"of the file content. Read `{xml}` for the full list."]
    return lines


def assumptions_section(rig_result: dict, settings_stage: dict | None,
                        settings: dict) -> list[str]:
    facts = rig_result.get("facts", {})
    waits = dict(((settings_stage or {}).get("result") or {})
                 .get("init_waits", {}))
    waits.update(rig_result.get("init_waits", {}))
    p11 = facts.get("p11", {})
    order = facts.get("control_order", {})
    host = facts.get("host", {})
    rounding = facts.get("part_a_rounding") or {}
    limit = settings["camera"]["init_wait_s"]
    longest = max((w["seconds"] for w in waits.values()), default=None)
    p11_text = {True: "Holds", False: "Contradicted"}.get(
        p11.get("holds"), "Inconclusive")
    lines = [
        "", "## Working assumptions that the run tested", "",
        "| Id | Assumption | Result | Evidence |", "|---|---|---|---|",
        f"| P11 | The camera keeps service writes across a driver restart "
        f"without a power cycle | {p11_text} | {cell(p11.get('detail', '-'))}"
        f"; written {cell(json.dumps(p11.get('written', {})))}, after the "
        f"restart {cell(json.dumps(p11.get('after_restart', {})))} |",
        f"| Init wait limit | The driver prints the init line within {limit} s"
        f" | {'Holds' if longest is not None and longest < limit else 'Open'}"
        f" | {len(waits)} init waits, longest {longest} s |",
        f"| Line order | `launch` and `tee` keep the line order of one stream "
        f"| {'Holds' if order.get('in_order') else 'Open'} | "
        f"{cell(json.dumps(order) if order else '-')} |",
        f"| Override order | A later `parameters` entry overrides an earlier "
        f"one | {'Holds' if all_pass(rig_result, ['E4', 'E5']) else 'Open'} "
        f"| Exit checks 4 and 5 read both values back |",
        f"| P2 | The settings file and the profile file describe the same "
        f"values | {'Holds' if all_pass(rig_result, ['E9']) else 'Open'} | "
        f"Exit check 9 after the controlled reopen, and the file scan |",
        f"| Part A step 11 | The camera holds 10000.0 and 20.0 within 0.001 "
        f"| {'Contradicted' if rounding else 'Holds'} | "
        f"{cell(json.dumps(rounding) if rounding else 'exact readback')} |",
        f"| Host check | `net.core.rmem_max` and `net.core.rmem_default` are "
        f"8388608 or more | "
        f"{'Below' if host.get('below_8388608') else 'Holds'} | "
        f"{cell(json.dumps(host.get('values', {})))} |",
        "",
        "Init waits:",
        "",
        "| Log | Status | Seconds |", "|---|---|---|",
    ]
    lines += [f"| {name}.log | {w['status']} | {w['seconds']} |"
              for name, w in waits.items()]
    lines += ["", "Rule for a result that contradicts v2: the runner records "
              "the result here and does not edit v2. If P11 is contradicted, "
              "the run continues with the v2 fallback in section 10, part A "
              "note 5. Part A still fails on a failed load, because the "
              "failed-load `grep` runs on each launch log and the camera "
              "defaults keep `AcquisitionFrameRateEnable` false. A slow init "
              "wait stops the run, because a new limit is a change to v2 "
              "that Logan decides. A float write that the camera rounds to "
              "its own increment passes part A step 11 when the readback is "
              "within one increment of the written value and differs from "
              "the profile value. v2 asks for 0.001, so each such rounding "
              "is listed in the row for part A step 11."]
    if p11.get("holds") is False:
        after = p11.get("after_restart", {})
        lines += ["", f"P11 is contradicted. After a restart without a file, "
                  f"the camera read {json.dumps(after)}. Exit check 9 still "
                  f"proves the load for each profile value that differs from "
                  f"these defaults."]
    return lines


def all_pass(result: dict, ids: list[str]) -> bool:
    found = {c["id"]: c["passed"] for c in result.get("checks", [])}
    return all(found.get(i) for i in ids)


def review_section(state: dict, out: str) -> list[str]:
    review = state["stages"].get("review") or {}
    findings = ((review.get("result") or {}).get("findings")) or []
    fix = state["stages"].get("fix") or {}
    lines = ["", "## Review", "",
             f"Codex reviewed the step 1 changes in stage review. Claude "
             f"answered each finding in stage fix (status {fix.get('status')})."
             f" The review is in `{out}/review.md`, and the answers are in "
             f"`{out}/fixes.md`.", ""]
    if not findings:
        return lines + ["The review had no findings."]
    lines += ["| Id | Severity | File | Finding |", "|---|---|---|---|"]
    for f in findings:
        lines.append(f"| {cell(f.get('id'))} | {cell(f.get('severity'))} | "
                     f"{cell(f.get('file', '-'))} | "
                     f"{cell(f.get('summary', '-'))} |")
    return lines


def cleanup_section(stages: list[dict]) -> list[str]:
    lines = ["", "## Camera cleanup", "",
             "After each camera stage, the runner stopped each driver, wrote "
             "back each baseline value that differed, read each value back, "
             "and checked that no driver process was left.", ""]
    for stage in stages:
        if stage["kind"] not in ("settings", "rig"):
            continue
        for attempt in stage["attempts"]:
            result = attempt.get("result") or {}
            lines.append(f"- {stage['id']} attempt {attempt['n']}: outcome "
                         f"{attempt.get('outcome')}, logs "
                         f"`{result.get('log_dir', '-')}`")
    return lines
