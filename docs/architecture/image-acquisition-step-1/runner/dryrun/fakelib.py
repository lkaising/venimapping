# ------------------------------------------------------------------------------
#  Filename: fakelib.py
#
#  Purpose:  Holds the fake camera state that the dry run fakes share: the
#            feature values, the driver process record, the scenario, and the
#            settings file format.
#
#  Usage:    import fakelib
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import fcntl
import json
import os
import time
import xml.etree.ElementTree as ElementTree
from contextlib import contextmanager
from pathlib import Path

# --- Configuration ------------------------------------------------------------

STATE = Path(os.environ["STEP1_FAKE_STATE"])
SCENARIO = Path(os.environ["STEP1_FAKE_SCENARIO"])

# The values of the fake camera at power on. ExposureTime differs from the
# profile, so that the restore must write it.
DEFAULTS = {
    "PixelFormat": "Mono8",
    "Width": 1296,
    "Height": 1032,
    "TriggerSelector": "FrameStart",
    "TriggerMode@FrameStart": "Off",
    "TriggerMode@ExposureActive": "Off",
    "ExposureTime": 5000.0,
    "AcquisitionFrameRateEnable": False,
    "AcquisitionFrameRate": 69.71556091308594,
    "ExposureMode": "Timed",
    "ExposureAuto": "Off",
}
EXTRA = {"DeviceModelName": "Fake G1-130", "DeviceLinkThroughputLimit": "115000000"}


def scenario() -> dict:
    return json.loads(SCENARIO.read_text()).get("camera", {})


def log(name: str, text: str) -> None:
    with open(STATE / name, "a", encoding="utf-8") as handle:
        handle.write(f"{time.time():.3f} {text}\n")


@contextmanager
def camera():
    """Yields the camera state dict and saves it afterwards, under a lock."""
    with open(STATE / "camera.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = STATE / "camera.json"
        data = json.loads(path.read_text()) if path.exists() else {
            "features": dict(DEFAULTS), "streaming": False,
            "mode_written": False}
        if not path.exists() and scenario().get("exposure_grid"):
            # A real camera reports a value on its grid at power on.
            data["features"]["ExposureTime"] = ON_EXPOSURE
        yield data
        tmp = path.with_name("camera.json.tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)


def driver() -> dict | None:
    path = STATE / "driver.json"
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text())
        os.kill(record["pid"], 0)
    except (ProcessLookupError, ValueError, json.JSONDecodeError):
        return None
    return record if record.get("ready") else None


# The real camera rounds an ExposureTime write to a grid with this increment.
# 4999.455 is on the grid, and 10000.0 becomes 10004.707.
EXPOSURE_INC = 13.172
EXPOSURE_BASE = 4999.455


ON_EXPOSURE = round(EXPOSURE_BASE + EXPOSURE_INC, 3)


def snap_exposure(value: float) -> float:
    steps = round((value - EXPOSURE_BASE) / EXPOSURE_INC)
    return round(EXPOSURE_BASE + steps * EXPOSURE_INC, 3)


def rate_max(features: dict) -> float:
    return min(69.71556091308594, 1e6 / max(features["ExposureTime"], 1.0))


# --- Settings file ------------------------------------------------------------


def save_xml(path: Path, features: dict, denied: bool) -> None:
    # Like the real save, each trigger selector value has its own
    # SelectorGroup, and the selected value follows as a Feature.
    root = ElementTree.Element("CameraSettings", Version="1.0")
    group = ElementTree.SubElement(root, "FeatureGroup", Module="RemoteDevice")
    values = {k: v for k, v in features.items() if "@" not in k}
    values.update(EXTRA)
    if denied:
        values["GevPersistentIPAddress"] = "3232235876"
    for key, value in features.items():
        if key.startswith("TriggerMode@"):
            selector = ElementTree.SubElement(
                group, "SelectorGroup", Name="TriggerSelector",
                Value=key.split("@", 1)[1])
            ElementTree.SubElement(selector, "Feature",
                                   Name="TriggerMode").text = str(value)
    for name, value in values.items():
        text = str(value).lower() if isinstance(value, bool) else str(value)
        ElementTree.SubElement(group, "Feature", Name=name).text = text
    ElementTree.ElementTree(root).write(path, xml_declaration=True)


def load_xml(path: Path, features: dict) -> None:
    root = ElementTree.parse(path).getroot()
    for group in root.iter("SelectorGroup"):
        for element in group.iter("Feature"):
            if element.get("Name") == "TriggerMode":
                features[f"TriggerMode@{group.get('Value')}"] = (
                    element.text or "")
    for element in root.iter("Feature"):
        name, text = element.get("Name"), element.text or ""
        if name == "TriggerMode":
            continue
        if name in features:
            kind = type(DEFAULTS[name])
            features[name] = (text == "true") if kind is bool else kind(text)
