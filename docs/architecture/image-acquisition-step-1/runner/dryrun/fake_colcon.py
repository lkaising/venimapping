# ------------------------------------------------------------------------------
#  Filename: fake_colcon.py
#
#  Purpose:  Stands in for colcon in the dry run. The build installs the
#            bring-up files. The test passes only when the step 1 files hold
#            the keys that the real configuration test checks.
#
#  Usage:    python3 fake_colcon.py <build|test|test-result> [options]
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PKG = Path("src/venimapping_bringup")
SHARE = Path("install/venimapping_bringup/share/venimapping_bringup")
RESULTS = Path("build/venimapping_bringup/test_results/venimapping_bringup")


def build(args: list[str]) -> int:
    packages = (args[args.index("--packages-select") + 1:]
                if "--packages-select" in args else
                ["venimapping_camera", "venimapping_bringup"])
    if "venimapping_camera" in packages:
        probe = Path("install/venimapping_camera/lib/venimapping_camera")
        probe.mkdir(parents=True, exist_ok=True)
        (probe / "camera_gateway_probe").write_text("fake\n")
    if "venimapping_bringup" in packages:
        if "SYNTAX ERROR" in (PKG / "CMakeLists.txt").read_text():
            print("CMake Error at CMakeLists.txt: parse error")
            return 1
        for folder in ("config", "launch"):
            shutil.rmtree(SHARE / folder, ignore_errors=True)
            shutil.copytree(PKG / folder, SHARE / folder)
    Path("install/setup.bash").write_text("# fake overlay\n")
    print(f"Summary: {len(packages)} packages finished")
    return 0


def test(args: list[str]) -> int:
    problems = []
    camera = (PKG / "config/camera.yaml").read_text()
    for key in ("use_ros_time: true", "buffer_count: 7"):
        if key not in camera:
            problems.append(f"camera.yaml has no {key}")
    if "settings_file" not in (PKG / "launch/camera.launch.py").read_text():
        problems.append("the launch file has no settings_file argument")
    for rel in ("config/acquisition_profile.yaml",
                "test/test_camera_config.py"):
        if not (PKG / rel).is_file():
            problems.append(f"missing {rel}")
    RESULTS.mkdir(parents=True, exist_ok=True)
    cases = "".join(
        f'<testcase classname="test_camera_config" name="check_{i}">'
        + (f'<failure message="{problems[0]}"/>' if problems and i == 0
           else "") + "</testcase>" for i in range(3))
    (RESULTS / "test_camera_config.xunit.xml").write_text(
        f'<testsuite name="test_camera_config" tests="3" errors="0" '
        f'failures="{1 if problems else 0}" skipped="0">{cases}</testsuite>')
    print("\n".join(problems) or "3 passed")
    return 1 if problems and "--return-code-on-test-failure" in args else 0


def test_result() -> int:
    tests = errors = failures = 0
    for path in RESULTS.glob("*.xml"):
        text = path.read_text()
        tests += int(re.search(r'tests="(\d+)"', text).group(1))
        errors += int(re.search(r'errors="(\d+)"', text).group(1))
        failures += int(re.search(r'failures="(\d+)"', text).group(1))
    print(f"Summary: {tests} tests, {errors} errors, {failures} failures, "
          f"0 skipped")
    return 1 if errors or failures else 0


def main() -> int:
    command, args = sys.argv[1], sys.argv[2:]
    if command == "build":
        return build(args)
    if command == "test":
        return test(args)
    if command == "test-result":
        return test_result()
    print(f"fake colcon: unknown command {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
