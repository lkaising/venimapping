# ------------------------------------------------------------------------------
#  Filename: checks.py
#
#  Purpose:  Runs the checks of step 1 that need no camera: the bring-up
#            colcon build and test, and the scan of the saved settings file
#            for the profile values and for features that must not change.
#
#  Usage:    import checks
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from rig import PROFILE, Shell, same

# --- Configuration ------------------------------------------------------------

PACKAGE = "venimapping_bringup"
PROBE = "install/venimapping_camera/lib/venimapping_camera/camera_gateway_probe"
SUMMARY_RE = re.compile(
    r"Summary: (\d+) tests?, (\d+) errors?, (\d+) failures?, (\d+) skipped")


# --- Build and test -----------------------------------------------------------


def build_and_test(shell: Shell, colcon: list[str], worktree: Path,
                   timeout_s: float) -> dict:
    """Exit checks 1 and 2. Also builds the gateway probe if it is missing."""
    checks = []

    def record(check: str, passed: bool, detail: str) -> bool:
        checks.append({"id": check, "passed": passed, "detail": detail})
        shell.note(f"# check {check}: {'PASS' if passed else 'FAIL'} {detail}")
        return passed

    def colcon_run(*args: str) -> tuple[int, str]:
        code, output, _ = shell.run([*colcon, *args], timeout_s, cwd=worktree)
        return code, output

    if not (worktree / PROBE).exists():
        code, _ = colcon_run("build", "--symlink-install", "--packages-select",
                             "venimapping_camera")
        if not record("E0", code == 0,
                      f"build of venimapping_camera for exit check 10 "
                      f"ended with exit {code}"):
            return {"passed": False, "checks": checks, "repairable": False}

    code, _ = colcon_run("build", "--symlink-install", "--packages-select",
                         PACKAGE, "--event-handlers", "console_cohesion+")
    if not record("E1", code == 0,
                  f"colcon build --packages-select {PACKAGE} ended with "
                  f"exit {code}"):
        return {"passed": False, "checks": checks, "repairable": True}

    code, _ = colcon_run("test", "--packages-select", PACKAGE,
                         "--return-code-on-test-failure",
                         "--event-handlers", "console_cohesion+")
    result_code, output = colcon_run(
        "test-result", "--test-result-base", f"build/{PACKAGE}", "--verbose")
    match = SUMMARY_RE.search(output)
    counts = tuple(int(x) for x in match.groups()) if match else None
    results = worktree / "build" / PACKAGE / "test_results"
    named = any("test_camera_config" in p.read_text(errors="replace")
                for p in results.rglob("*.xml")) if results.exists() else False
    passed = (code == 0 and result_code == 0 and counts is not None
              and counts[0] > 0 and counts[1] == 0 and counts[2] == 0
              and named)
    record("E2", passed,
           f"colcon test exit {code}, test-result exit {result_code}, "
           f"{match.group(0) if match else 'no summary line'}, "
           f"test_camera_config results found: {named}")
    return {"passed": passed, "checks": checks, "repairable": True}


# --- Settings file ------------------------------------------------------------


def xml_features(path: Path) -> dict[str, list[str]]:
    """Returns each feature name in the file with its values."""
    root = ElementTree.parse(path).getroot()
    found: dict[str, list[str]] = {}
    for element in root.iter():
        name = element.get("Name") or element.get("name")
        if not name:
            continue
        value = (element.text or "").strip()
        if not value:
            value = element.get("Value") or element.get("value") or ""
        found.setdefault(name, []).append(value)
    return found


def xml_value_matches(name: str, raw: str, expected) -> bool:
    if isinstance(expected, bool):
        return raw.strip().lower() in (("true", "1") if expected
                                       else ("false", "0"))
    try:
        if isinstance(expected, float):
            return same(name, float(raw), expected)
        if isinstance(expected, int):
            return int(raw) == expected
    except ValueError:
        return False
    return raw.strip() == expected


def scan_settings(path: Path, denied: list[str]) -> dict:
    """Checks the profile values in the file and finds denied features."""
    try:
        features = xml_features(path)
    except (OSError, ElementTree.ParseError) as error:
        return {"passed": False, "detail": f"cannot parse {path.name}: {error}",
                "features": 0, "denied": [], "profile": {}}
    profile = {}
    for name, _, value in PROFILE:
        values = features.get(name, [])
        profile[name] = {"expected": value, "found": values,
                         "match": any(xml_value_matches(name, v, value)
                                      for v in values)}
    patterns = [re.compile(p) for p in denied]
    hits = sorted(name for name in features
                  if any(p.search(name) for p in patterns))
    missing = [n for n, info in profile.items() if not info["match"]]
    detail = (f"{len(features)} features; profile values missing or wrong: "
              f"{missing or 'none'}; denied features: {hits or 'none'}")
    profile_names = {name for name, _, _ in PROFILE} | {"TriggerSelector"}
    others = {name: values for name, values in sorted(features.items())
              if name not in profile_names}
    return {"passed": not missing and not hits, "detail": detail,
            "features": len(features), "denied": hits, "profile": profile,
            "missing": missing, "others": others}
