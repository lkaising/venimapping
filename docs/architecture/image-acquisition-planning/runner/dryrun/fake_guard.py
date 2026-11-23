# ------------------------------------------------------------------------------
#  Filename: fake_guard.py
#
#  Purpose:  Stands in for camera_guard.py in the dry run. It checks the stub
#            driver and fails the restore calls that the scenario names.
#
#  Usage:    python3 fake_guard.py <command> --namespace <ns> [options]
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def driver_up(state_dir: Path) -> bool:
    pid_file = state_dir / "driver.pid"
    if not pid_file.exists():
        return False
    try:
        os.kill(int(pid_file.read_text()), 0)
    except (ProcessLookupError, ValueError):
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("--namespace")
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--features")
    parser.add_argument("--out")
    parser.add_argument("--originals")
    args = parser.parse_args()
    state_dir = Path(os.environ["PLANRUN_FAKE_STATE"])
    scenario = json.loads(Path(os.environ["PLANRUN_FAKE_SCENARIO"]).read_text())

    with open(state_dir / "guard.log", "a") as log:
        log.write(f"{time.time():.3f} {args.command}\n")

    if args.command == "wait":
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            if driver_up(state_dir):
                print(json.dumps({"ok": True}))
                return 0
            time.sleep(0.1)
        print(json.dumps({"ok": False, "error": "stub driver not running"}))
        return 1

    if not driver_up(state_dir):
        print(json.dumps({"ok": False, "error": "stub driver not running"}))
        return 1

    if args.command == "snapshot":
        features = json.loads(Path(args.features).read_text())
        originals = [{**f, "value": 1.0} for f in features]
        Path(args.out).write_text(json.dumps(originals))
        print(json.dumps({"ok": True, "originals": originals}))
        return 0

    if args.command == "restore":
        counter = state_dir / "restore.count"
        count = int(counter.read_text()) + 1 if counter.exists() else 1
        counter.write_text(str(count))
        if count in scenario.get("fail_restore_calls", []):
            print(json.dumps({"ok": False,
                              "error": "features differ after restore"}))
            return 1
        print(json.dumps({"ok": True, "restored": [], "verified": 1}))
        return 0

    streaming = state_dir / "streaming"
    if args.command == "status":
        print(json.dumps({"ok": True,
                          "status": {"streaming": streaming.exists()}}))
        return 0

    if args.command == "stream-stop":
        if streaming.exists():
            streaming.unlink()
            with open(state_dir / "stream-stops.log", "a") as log:
                log.write(f"{time.time():.3f}\n")
        print(json.dumps({"ok": True}))
        return 0

    print(json.dumps({"ok": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
