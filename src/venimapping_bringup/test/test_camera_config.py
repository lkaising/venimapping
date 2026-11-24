# ------------------------------------------------------------------------------
#  Filename: test_camera_config.py
#
#  Purpose:  Checks the bring-up parameter files and launch arguments without a
#            camera, a driver, a network, or a built overlay.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

import importlib.util
from pathlib import Path

import launch.logging
import yaml
from launch.actions import DeclareLaunchArgument
from launch.substitutions import PathJoinSubstitution, TextSubstitution
from launch_ros.substitutions import FindPackageShare

PACKAGE_DIR = Path(__file__).resolve().parents[1]
CAMERA_YAML = PACKAGE_DIR / "config" / "camera.yaml"
PROFILE_YAML = PACKAGE_DIR / "config" / "acquisition_profile.yaml"
LAUNCH_FILE = PACKAGE_DIR / "launch" / "camera.launch.py"

DRIVER_NODE_KEY = "/**/vimbax_camera"

# The values in v2 section 10, "Driver parameters". camera.yaml holds these keys
# and no other key. The launch file sets settings_file.
EXPECTED_DRIVER_PARAMETERS = {
    "camera_id": "0GPF3",
    "autostream": 0,
    "buffer_count": 7,
    "use_ros_time": True,
    "use_sim_time": False,
    "image_raw": {"enable_pub_plugins": ["image_transport/raw"]},
}

ALLOWED_PIXEL_FORMATS = {"Mono8", "Mono12"}


def load_yaml(path):
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def load_launch_arguments(log_dir):
    # DeclareLaunchArgument opens the launch log file. Keep it out of ~/.ros.
    if not launch.logging.launch_config.file_handlers:
        launch.logging.launch_config.log_dir = str(log_dir)

    spec = importlib.util.spec_from_file_location(
        "venimapping_bringup_camera_launch", LAUNCH_FILE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    description = module.generate_launch_description()
    return {
        entity.name: entity
        for entity in description.entities
        if isinstance(entity, DeclareLaunchArgument)
    }


def text_of(substitutions):
    """Return the text of a substitution list that holds one TextSubstitution."""
    assert len(substitutions) == 1, f"expected one substitution, got {substitutions!r}"
    assert isinstance(substitutions[0], TextSubstitution), (
        f"expected a TextSubstitution, got {substitutions[0]!r}"
    )
    return substitutions[0].text


def test_camera_yaml_has_driver_parameters():
    document = load_yaml(CAMERA_YAML)
    assert list(document) == [DRIVER_NODE_KEY]
    parameters = document[DRIVER_NODE_KEY]["ros__parameters"]

    assert parameters == EXPECTED_DRIVER_PARAMETERS

    # Python compares True equal to 1, so the dict compare alone accepts a
    # wrong YAML type.
    assert type(parameters["camera_id"]) is str
    assert type(parameters["autostream"]) is int
    assert type(parameters["buffer_count"]) is int
    assert parameters["use_ros_time"] is True
    assert parameters["use_sim_time"] is False

    assert "camera_info_url" not in parameters
    assert "settings_file" not in parameters


def test_profile_allowed_formats_are_mono8_or_mono12():
    document = load_yaml(PROFILE_YAML)
    allowed_formats = document["/**"]["ros__parameters"]["profile"]["allowed_formats"]

    assert isinstance(allowed_formats, list)
    assert allowed_formats, "allowed_formats is empty"
    for pixel_format in allowed_formats:
        assert pixel_format in ALLOWED_PIXEL_FORMATS, (
            f"{pixel_format!r} is not Mono8 or Mono12"
        )


def test_launch_arguments_have_defaults(tmp_path):
    arguments = load_launch_arguments(tmp_path)

    for name in ("camera_namespace", "params_file", "use_ros_time", "settings_file"):
        assert name in arguments, f"launch argument {name} is missing"

    assert text_of(arguments["use_ros_time"].default_value) == "true"

    settings_default = arguments["settings_file"].default_value
    assert len(settings_default) == 1
    path_join = settings_default[0]
    # FindPackageShare is a subclass of PathJoinSubstitution, so exclude its type.
    assert isinstance(path_join, PathJoinSubstitution)
    assert not isinstance(path_join, FindPackageShare)

    components = path_join.substitutions
    assert len(components) == 3

    # The package attribute holds the name. No package lookup runs.
    assert len(components[0]) == 1
    package_share = components[0][0]
    assert isinstance(package_share, FindPackageShare)
    assert text_of(package_share.package) == "venimapping_bringup"

    assert text_of(components[1]) == "config"
    assert text_of(components[2]) == "camera_settings.xml"
