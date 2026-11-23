# ------------------------------------------------------------------------------
#  Filename: preflight.py
#
#  Purpose:  Checks in a few minutes that the step 1 run can start: the git
#            state, the remote, both CLIs and both Claude accounts, the ROS
#            environment, the build and test, and a read-only camera answer.
#            Prints one PASS or FAIL line for each item.
#
#  Usage:    python3 docs/architecture/image-acquisition-step-1/runner/preflight.py
#            [--settings <file>] [--skip-camera] [--skip-agents]
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

import checks  # noqa: E402
import rig  # noqa: E402
from common import Stop, excerpt, pids_named, ros_env  # noqa: E402
from run import SETTINGS_FILE, classify  # noqa: E402

# --- Configuration ------------------------------------------------------------

RUNNER_DIR = Path(__file__).resolve().parent
AGENT_PROMPT = "Reply with the single word OK. Do not use any tool."


class Preflight:
    def __init__(self, settings: dict) -> None:
        self.settings = settings
        self.worktree = Path(self.git("rev-parse", "--show-toplevel",
                                      cwd=RUNNER_DIR)[1].strip())
        self.failures = 0
        self.env: dict[str, str] | None = None

    def item(self, ok: bool, name: str, detail: str = "") -> bool:
        if not ok:
            self.failures += 1
        print(f"{'PASS' if ok else 'FAIL'}  {name}"
              + (f"  [{detail}]" if detail else ""), flush=True)
        return ok

    def git(self, *args: str, cwd: Path | None = None) -> tuple[int, str]:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
        result = subprocess.run(["git", *args], cwd=cwd or self.worktree,
                                env=env, capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=60)
        return result.returncode, result.stdout + result.stderr

    # --- Items ----------------------------------------------------------------

    def git_items(self) -> None:
        branch = self.git("rev-parse", "--abbrev-ref", "HEAD")[1].strip()
        want = self.settings["branch"]
        self.item(branch == want, "branch", f"on {branch}, want {want}")
        code, status = self.git("status", "--porcelain=v1", "-uall")
        self.item(code == 0 and not status.strip(), "worktree is clean",
                  excerpt(status, 200) or "no changes")
        remote = self.settings["remote"]
        code, listing = self.git("ls-remote", remote, f"refs/heads/{want}")
        remote_head = listing.split("\t")[0].strip() if code == 0 else ""
        local = self.git("rev-parse", "HEAD")[1].strip()
        self.item(code == 0 and bool(remote_head), "remote is reachable",
                  f"{remote}/{want} at {remote_head[:11] or excerpt(listing)}")
        self.item(remote_head == local, "remote branch has the local HEAD",
                  f"local {local[:11]}, remote {remote_head[:11]}")

    def run_items(self) -> None:
        run_dir = Path(self.settings["run_dir"])
        state = run_dir / "state.json"
        if state.exists():
            data = json.loads(state.read_text())
            self.item(True, "run folder", f"{run_dir} holds a run with status "
                      f"{data.get('status')}; the run command resumes it")
        else:
            self.item(not run_dir.exists() or not any(run_dir.iterdir()),
                      "run folder", f"{run_dir} is new; the run starts fresh")

    def driver_item(self) -> bool:
        found = pids_named(self.settings["camera"]["driver_process"])
        return self.item(not found, "no camera driver is running",
                         f"running: {found}" if found else "none")

    def env_item(self) -> bool:
        try:
            self.env = ros_env(self.worktree / self.settings["env_script"])
        except Stop as error:
            return self.item(False, "environment loads", str(error))
        defaults = self.worktree / ".devcontainer/colcon-defaults.yaml"
        if defaults.is_file():
            self.env.setdefault("COLCON_DEFAULTS_FILE", str(defaults))
        tools = [name for name in ("ros2", "colcon")
                 if not any(Path(p, name).exists() for p in
                            self.env.get("PATH", "").split(":"))]
        rmw = self.env.get("RMW_IMPLEMENTATION", "default")
        return self.item(not tools, "environment loads",
                         f"missing {tools}" if tools else f"rmw={rmw}")

    def python_item(self) -> None:
        code = ("import yaml, pytest, launch, launch_ros; "
                "print(yaml.__version__, pytest.__version__)")
        result = subprocess.run(["python3", "-c", code], env=self.env,
                                capture_output=True, text=True, timeout=60)
        prefix = subprocess.run(["ros2", "pkg", "prefix", "ament_cmake_pytest"],
                                env=self.env, capture_output=True, text=True,
                                timeout=60)
        self.item(result.returncode == 0 and prefix.returncode == 0,
                  "test packages exist",
                  f"yaml and pytest {result.stdout.strip()}, "
                  f"ament_cmake_pytest at {prefix.stdout.strip()}"
                  if result.returncode == 0 and prefix.returncode == 0
                  else excerpt(result.stderr + prefix.stderr, 300))

    def build_item(self, scratch: Path) -> None:
        shell = rig.Shell(self.env, scratch, scratch / "build.log")
        colcon = self.settings["build"]["colcon"]
        code, _, _ = shell.run([*colcon, "build", "--symlink-install"],
                               self.settings["build"]["timeout_s"],
                               cwd=self.worktree)
        self.item(code == 0, "workspace build",
                  f"colcon build --symlink-install exit {code}; log "
                  f"{scratch / 'build.log'}")
        code, output, _ = shell.run(
            [*colcon, "test", "--packages-select", checks.PACKAGE,
             "--return-code-on-test-failure"],
            self.settings["build"]["timeout_s"], cwd=self.worktree)
        self.item(code == 0, "bring-up test runs",
                  f"colcon test --packages-select {checks.PACKAGE} exit {code}")
        defaults = self.env.get("COLCON_DEFAULTS_FILE")
        self.env = ros_env(self.worktree / self.settings["env_script"])
        if defaults:
            self.env["COLCON_DEFAULTS_FILE"] = defaults
        result = subprocess.run(["ros2", "pkg", "prefix", checks.PACKAGE],
                                env=self.env, capture_output=True, text=True,
                                timeout=60)
        expected = self.worktree / "install" / checks.PACKAGE
        found = result.stdout.strip()
        self.item(Path(found) == expected, "this worktree's overlay comes first",
                  f"ros2 pkg prefix gives {found or excerpt(result.stderr)}")

    def camera_item(self, scratch: Path) -> None:
        settings = self.settings["camera"]
        shell = rig.Shell(self.env, scratch, scratch / "camera.log")
        cli = rig.Cli(shell, settings["namespace"],
                      settings["service_timeout_s"],
                      lambda: (_ for _ in ()).throw(
                          rig.CameraError("preflight writes nothing")))
        params = scratch / "bare-params.yaml"
        rig.write_bare_params(params, settings)
        driver = rig.Driver(shell, settings, params, lambda pgid: None,
                            lambda pgid: None)
        detail = ""
        ok = False
        try:
            driver.launch("driver_preflight", bare=True)
            if driver.init_wait("driver_preflight") != 0:
                raise rig.CameraError(
                    f"no init line within {settings['init_wait_s']} s")
            seconds = driver.init_waits["driver_preflight"]["seconds"]
            exposure = cli.get("ExposureTime")
            streaming = cli.streaming()
            ok = not streaming
            detail = (f"init after {seconds} s, ExposureTime {exposure}, "
                      f"streaming {streaming}")
        except rig.CameraError as error:
            detail = str(error)
        finally:
            try:
                driver.stop_all()
            except rig.CameraError as error:
                detail += f"; {error}"
                ok = False
        left = pids_named(settings["driver_process"])
        self.item(ok and not left, "camera answers (read only)",
                  f"{detail}; drivers left: {left or 'none'}; log "
                  f"{scratch / 'camera.log'}")

    def agent_items(self, scratch: Path) -> None:
        claude = self.settings["claude"]
        for account in claude.get("accounts") or [{"name": "default",
                                                    "config_dir": None}]:
            env = dict(os.environ)
            env.pop("CLAUDE_CONFIG_DIR", None)
            if account["config_dir"]:
                env["CLAUDE_CONFIG_DIR"] = os.path.expanduser(
                    account["config_dir"])
            command = [*claude["command"], "-p", "--output-format", "json",
                       "--no-session-persistence", "--permission-prompts",
                       "none", AGENT_PROMPT]
            self.agent_item(f"claude account {account['name']}", "claude",
                            command, env, scratch)
        codex = self.settings["codex"]
        command = [*codex["command"], "exec", "--json", "--sandbox",
                   "read-only", "--skip-git-repo-check", "--ephemeral",
                   "--color", "never", "-C", str(scratch), AGENT_PROMPT]
        self.agent_item("codex", "codex", command, dict(os.environ), scratch)

    def agent_item(self, name: str, tool: str, command: list[str],
                   env: dict, scratch: Path) -> None:
        try:
            result = subprocess.run(command, env=env, cwd=scratch,
                                    capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL, timeout=300)
            kind, detail = classify(tool, result.returncode, result.stdout,
                                    result.stderr, False, 300)
        except subprocess.TimeoutExpired:
            kind, detail = "error", "no answer in 300 s"
        except OSError as error:
            kind, detail = "error", str(error)
        self.item(kind == "ok", f"{name} works",
                  "answered" if kind == "ok" else
                  f"{kind}: {excerpt(detail, 300)}")


# --- Entry point --------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Checks the step 1 run.")
    parser.add_argument("--settings", type=Path, default=SETTINGS_FILE)
    parser.add_argument("--skip-camera", action="store_true")
    parser.add_argument("--skip-agents", action="store_true")
    args = parser.parse_args()
    check = Preflight(json.loads(args.settings.read_text()))
    scratch = Path(tempfile.mkdtemp(prefix="step1-preflight-"))
    print(f"preflight logs: {scratch}", flush=True)

    check.git_items()
    check.run_items()
    driver_free = check.driver_item()
    if check.env_item():
        check.python_item()
        check.build_item(scratch)
        if args.skip_camera:
            print("SKIP  camera answers (read only)", flush=True)
        elif driver_free:
            check.camera_item(scratch)
        else:
            check.item(False, "camera answers (read only)",
                       "not tried while another driver runs")
    if args.skip_agents:
        print("SKIP  claude and codex", flush=True)
    else:
        check.agent_items(scratch)
    print(f"\npreflight: {'PASS' if check.failures == 0 else 'FAIL'} "
          f"({check.failures} failed)", flush=True)
    return 0 if check.failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
