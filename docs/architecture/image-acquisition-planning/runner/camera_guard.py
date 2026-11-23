# ------------------------------------------------------------------------------
#  Filename: camera_guard.py
#
#  Purpose:  Reads, restores, and verifies camera state for the planning
#            runner through the vimbax_camera driver services.
#
#  Usage:    python3 camera_guard.py <wait|status|stream-stop|snapshot|restore>
#            --namespace /vimbax_camera [options]. Prints one JSON line.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import argparse
import json
import math
import sys
import time

import rclpy
from rclpy.node import Node
from vimbax_camera_msgs import srv
from vimbax_camera_msgs.msg import FeatureModule

# --- Configuration ------------------------------------------------------------

CALL_TIMEOUT_S = 10.0
FLOAT_TOLERANCE = 1e-6

SERVICES = {
    "float": (srv.FeatureFloatGet, srv.FeatureFloatSet),
    "int": (srv.FeatureIntGet, srv.FeatureIntSet),
    "enum": (srv.FeatureEnumGet, srv.FeatureEnumSet),
    "bool": (srv.FeatureBoolGet, srv.FeatureBoolSet),
}


class GuardError(Exception):
    pass


# --- Service access -----------------------------------------------------------


class Camera:
    def __init__(self, node: Node, namespace: str) -> None:
        self.node = node
        self.namespace = namespace.rstrip("/")
        self.clients = {}

    def call(self, kind, name: str, request, timeout: float = CALL_TIMEOUT_S):
        full = f"{self.namespace}/{name}"
        client = self.clients.get(full)
        if client is None:
            client = self.node.create_client(kind, full)
            self.clients[full] = client
        if not client.wait_for_service(timeout_sec=timeout):
            raise GuardError(f"service {full} is not available")
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=timeout)
        if not future.done() or future.result() is None:
            raise GuardError(f"service {full} did not answer")
        response = future.result()
        if response.error.code != 0:
            raise GuardError(f"{full} returned error {response.error.code}: "
                             f"{response.error.text}")
        return response

    def status(self) -> dict:
        response = self.call(srv.Status, "status", srv.Status.Request())
        return {"streaming": response.streaming, "width": response.width,
                "height": response.height,
                "frame_rate": response.frame_rate,
                "pixel_format": response.pixel_format}

    def get(self, feature: dict):
        get_kind, _ = SERVICES[feature["type"]]
        request = get_kind.Request()
        request.feature_name = feature["name"]
        request.feature_module = FeatureModule(id=feature.get("module", 0))
        name = f"features/{feature['type']}_get"
        return self.call(get_kind, name, request).value

    def set(self, feature: dict, value) -> None:
        _, set_kind = SERVICES[feature["type"]]
        request = set_kind.Request()
        request.feature_name = feature["name"]
        request.feature_module = FeatureModule(id=feature.get("module", 0))
        request.value = value
        self.call(set_kind, f"features/{feature['type']}_set", request)


def same(kind: str, left, right) -> bool:
    if kind == "float":
        scale = max(abs(left), abs(right), 1.0)
        return math.isclose(left, right, abs_tol=FLOAT_TOLERANCE * scale)
    return left == right


# --- Commands -----------------------------------------------------------------


def wait(camera: Camera, args) -> dict:
    deadline = time.monotonic() + args.timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            return {"ok": True, "status": camera.status()}
        except GuardError as error:
            last = str(error)
            time.sleep(1.0)
    raise GuardError(f"driver not ready after {args.timeout} s: {last}")


def stream_stop(camera: Camera, args) -> dict:
    before = camera.status()
    if before["streaming"]:
        camera.call(srv.StreamStartStop, "stream_stop",
                    srv.StreamStartStop.Request())
    after = camera.status()
    if after["streaming"]:
        raise GuardError("the driver still reports streaming after stop")
    return {"ok": True, "was_streaming": before["streaming"]}


def snapshot(camera: Camera, args) -> dict:
    with open(args.features, encoding="utf-8") as handle:
        features = json.load(handle)
    originals = []
    for feature in features:
        originals.append({**feature, "value": camera.get(feature)})
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(originals, handle, indent=2)
    return {"ok": True, "originals": originals}


def restore(camera: Camera, args) -> dict:
    with open(args.originals, encoding="utf-8") as handle:
        originals = json.load(handle)
    changed = []
    for feature in reversed(originals):
        current = camera.get(feature)
        if not same(feature["type"], current, feature["value"]):
            camera.set(feature, feature["value"])
            changed.append(feature["name"])
    mismatched = []
    for feature in originals:
        current = camera.get(feature)
        if not same(feature["type"], current, feature["value"]):
            mismatched.append({"name": feature["name"],
                               "expected": feature["value"],
                               "actual": current})
    if mismatched:
        raise GuardError(f"features differ after restore: {mismatched}")
    return {"ok": True, "restored": changed, "verified": len(originals)}


def status(camera: Camera, args) -> dict:
    return {"ok": True, "status": camera.status()}


COMMANDS = {"wait": wait, "status": status, "stream-stop": stream_stop,
            "snapshot": snapshot, "restore": restore}


# --- Entry point --------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--features")
    parser.add_argument("--out")
    parser.add_argument("--originals")
    args = parser.parse_args()

    rclpy.init()
    node = rclpy.create_node("planning_camera_guard")
    try:
        report = COMMANDS[args.command](Camera(node, args.namespace), args)
        code = 0
    except GuardError as error:
        report, code = {"ok": False, "error": str(error)}, 1
    finally:
        node.destroy_node()
        rclpy.shutdown()
    print(json.dumps(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
