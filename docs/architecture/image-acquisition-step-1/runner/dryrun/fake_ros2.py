# ------------------------------------------------------------------------------
#  Filename: fake_ros2.py
#
#  Purpose:  Stands in for the ros2 CLI in the dry run. It starts the fake
#            driver for launch and run, and answers service calls, parameter
#            reads, and graph reads from the fake camera state.
#
#  Usage:    python3 fake_ros2.py <launch|run|service|param|topic|daemon|pkg>
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fakelib  # noqa: E402

NODE = Path(__file__).resolve().parent / "vimbax_camera_node"
INSTALL = Path(os.environ["STEP1_FAKE_INSTALL"])
SHARE = INSTALL / "venimapping_bringup/share/venimapping_bringup"
ALL_PLUGINS = ["image_transport/raw", "image_transport/compressed",
               "image_transport/theora"]
TYPES = {"float": float, "int": int, "enum": str, "bool": bool}


def hang() -> int:
    print("waiting for service to become available...", flush=True)
    time.sleep(3600)
    return 1


def show(value) -> str:
    if isinstance(value, str):
        return repr(value)
    return repr(value) if isinstance(value, float) else str(value)


def driver_params(yaml_file: Path) -> dict:
    loaded = yaml.safe_load(yaml_file.read_text()) or {}
    params = {"use_ros_time": False, "settings_file": "",
              "image_raw.enable_pub_plugins": list(ALL_PLUGINS)}
    for key, block in loaded.items():
        values = (block or {}).get("ros__parameters", {})
        for name, value in values.items():
            if name == "image_raw" and isinstance(value, dict):
                for sub, item in value.items():
                    params[f"image_raw.{sub}"] = item
            else:
                params[name] = value
    return params


def start_node(params: dict, prefix: str) -> None:
    handle, path = tempfile.mkstemp(suffix=".json",
                                    dir=str(fakelib.STATE))
    os.write(handle, json.dumps(params).encode())
    os.close(handle)
    os.execv(sys.executable, [sys.executable, str(NODE), "--params", path,
                              "--prefix", prefix])


# --- launch and run -----------------------------------------------------------


def launch(args: list[str]) -> int:
    text = (SHARE / "launch/camera.launch.py").read_text()
    params = driver_params(SHARE / "config/camera.yaml")
    overrides = dict(arg.split(":=", 1) for arg in args[2:] if ":=" in arg)
    if "use_ros_time" in text:
        params["use_ros_time"] = yaml.safe_load(
            overrides.get("use_ros_time", "true"))
    if "settings_file" in text:
        params["settings_file"] = overrides.get(
            "settings_file", str(SHARE / "config/camera_settings.xml"))
    start_node(params, "[vimbax_camera_node-1] ")
    return 0


def run(args: list[str]) -> int:
    if args[:2] == ["vimbax_camera", "vimbax_camera_node"]:
        params_file = Path(args[args.index("--params-file") + 1])
        params = driver_params(params_file)
        start_node(params, "")
    if args[:2] == ["venimapping_camera", "camera_gateway_probe"]:
        if fakelib.driver() is None:
            return hang()
        print("[INFO] [camera_gateway_probe]: probe complete: all checks "
              "passed (0 skipped)")
        return 0
    print(f"fake ros2 run: unknown {args}", file=sys.stderr)
    return 1


# --- service call -------------------------------------------------------------


def reply(srv_type: str, code: int = 0, text: str = "", **fields) -> int:
    error = f"error=vimbax_camera_msgs.msg.Error(code={code}, text={text!r})"
    parts = [f"{k}={show(v)}" for k, v in fields.items()]
    body = ", ".join(parts[:1] + [error] + parts[1:]) if \
        srv_type == "FeatureBoolGet" else ", ".join([error] + parts)
    print(f"requester: making request: vimbax_camera_msgs.srv.{srv_type}"
          f"_Request()\n\nresponse:\nvimbax_camera_msgs.srv.{srv_type}"
          f"_Response({body})\n")
    return 0


def service(args: list[str]) -> int:
    name, srv_type = args[1], args[2].rsplit("/", 1)[1]
    request = json.loads(args[3]) if len(args) > 3 else {}
    if fakelib.driver() is None:
        return hang()
    leaf = name.split("/vimbax_camera/", 1)[1]
    scenario = fakelib.scenario()
    with fakelib.camera() as cam:
        features = cam["features"]
        fakelib.log("calls.log", f"{leaf} {json.dumps(request)}")
        if leaf == "status":
            if cam["mode_written"]:
                fakelib.log("violations.log", "status after a TriggerMode "
                                              "write and before the save")
            features["TriggerSelector"] = "AcquisitionStart"
            return reply(srv_type, streaming=cam["streaming"], width=1296,
                         height=1032, pixel_format=features["PixelFormat"])
        if leaf == "stream_stop":
            cam["streaming"] = False
            return reply(srv_type)
        if leaf == "settings/save":
            path = Path(request["filename"])
            if path.suffix != ".xml" or not path.parent.is_dir():
                return reply(srv_type, code=-7, text="bad path")
            fakelib.save_xml(path, features, scenario.get("xml_denied", False))
            cam["mode_written"] = False
            return reply(srv_type)
        kind, verb = leaf.split("/", 1)[1].split("_")
        feature = request["feature_name"]
        key = (f"TriggerMode@{features['TriggerSelector']}"
               if feature == "TriggerMode" else feature)
        if verb == "get":
            if feature == "AcquisitionFrameRate" and not features[
                    "AcquisitionFrameRateEnable"]:
                return reply(srv_type, value=fakelib.rate_max(features))
            return reply(srv_type, value=features[key])
        value = TYPES[kind](request["value"])
        failing = scenario.get("fail_set_once", [])
        if [feature, value] in failing:
            failing.remove([feature, value])
            data = json.loads(fakelib.SCENARIO.read_text())
            data["camera"]["fail_set_once"] = failing
            fakelib.SCENARIO.write_text(json.dumps(data, indent=2))
            return reply(srv_type, code=-6, text="invalid access")
        if feature == "AcquisitionFrameRate" and not features[
                "AcquisitionFrameRateEnable"]:
            return reply(srv_type, code=-6, text="invalid access")
        if scenario.get("reject_part_a") and [feature, value] == [
                "ExposureTime", 10000.0]:
            value = 9000.0
        features[key] = value
        if feature == "TriggerMode":
            cam["mode_written"] = True
        part_a = feature == "AcquisitionFrameRate" and value == 20.0
    if part_a and not (fakelib.STATE / "part-a-written").exists():
        (fakelib.STATE / "part-a-written").touch()
        time.sleep(scenario.get("pause_after_part_a", 0))
    return reply(srv_type)


# --- param, topic, daemon, pkg ------------------------------------------------


def param(args: list[str]) -> int:
    record = fakelib.driver()
    if record is None:
        print("Node not found")
        return 1
    name = args[2]
    if name not in record["params"]:
        print("Parameter not set.")
        return 1
    value = record["params"][name]
    if isinstance(value, bool):
        print(f"Boolean value is: {value}")
    elif isinstance(value, list):
        print(f"String array value is: {value}")
    else:
        print(f"String value is: {value}")
    return 0


def topic(args: list[str]) -> int:
    record = fakelib.driver()
    topics = ["/parameter_events", "/rosout"]
    if record is not None:
        plugins = record["params"]["image_raw.enable_pub_plugins"]
        topics += ["/vimbax_camera/camera_info", "/vimbax_camera/image_raw"]
        topics += [f"/vimbax_camera/image_raw/{p.split('/')[1]}"
                   for p in plugins if p != "image_transport/raw"]
    if args[1] == "list":
        print("\n".join(sorted(topics)))
        return 0
    if args[2] not in topics:
        print(f"Unknown topic '{args[2]}'")
        return 1
    print("Type: sensor_msgs/msg/Image\nPublisher count: 1\n"
          "Subscription count: 0")
    return 0


def main() -> int:
    args = sys.argv[1:]
    command = args[0]
    if command == "launch":
        return launch(args)
    if command == "run":
        return run(args[1:])
    if command == "service" and args[1] == "call":
        return service(args[1:])
    if command == "param" and args[1] == "get":
        return param(args[1:])
    if command == "topic":
        return topic(args)
    if command == "daemon":
        print("The daemon has been stopped")
        return 0
    if command == "pkg" and args[1] == "prefix":
        if args[2] == "venimapping_bringup":
            print(INSTALL / "venimapping_bringup")
            return 0
        print(f"/opt/fake/{args[2]}")
        return 0
    print(f"fake ros2: unknown command {args}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
