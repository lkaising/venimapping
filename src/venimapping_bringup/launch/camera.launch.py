# ------------------------------------------------------------------------------
#  Filename: camera.launch.py
#
#  Purpose:  Launches the Vimba X camera driver with a namespace and YAML parameters.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from tempfile import NamedTemporaryFile

import yaml
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

PARAMS_KEY = "ros__parameters"


def driver_parameter_overrides():
    """Return the launch overrides. settings_file stays a string and skips YAML rules."""
    return {
        "use_ros_time": LaunchConfiguration("use_ros_time"),
        "settings_file": ParameterValue(
            LaunchConfiguration("settings_file"), value_type=str
        ),
    }


def mirror_override_entries(document, overrides):
    """Return each params_file entry that sets an override name, with the launch value.

    rcl merges all parameter files into one node list in order of first key
    appearance. A later matching wildcard entry can then win over the launch
    override. The mirror writes the launch value into each such entry.
    """
    mirror = {}
    if not isinstance(document, dict):
        return mirror
    for key, value in document.items():
        if not isinstance(value, dict):
            continue
        if key == PARAMS_KEY:
            entry = {name: overrides[name] for name in overrides if name in value}
        else:
            entry = mirror_override_entries(value, overrides)
        if entry:
            mirror[key] = entry
    return mirror


def launch_driver(context):
    params_file = LaunchConfiguration("params_file").perform(context)
    # The same value rules as driver_parameter_overrides: YAML for use_ros_time,
    # the raw string for settings_file.
    use_ros_time = LaunchConfiguration("use_ros_time").perform(context)
    overrides = {
        "use_ros_time": yaml.safe_load(use_ros_time),
        "settings_file": LaunchConfiguration("settings_file").perform(context),
    }
    with open(params_file, encoding="utf-8") as stream:
        mirror = mirror_override_entries(yaml.safe_load(stream), overrides)

    parameters = [params_file]
    if mirror:
        with NamedTemporaryFile(
            mode="w", prefix="venimapping_camera_overrides_", suffix=".yaml", delete=False
        ) as stream:
            yaml.safe_dump(mirror, stream, default_flow_style=False)
        parameters.append(stream.name)
    parameters.append(driver_parameter_overrides())

    return [
        Node(
            package="vimbax_camera",
            executable="vimbax_camera_node",
            namespace=LaunchConfiguration("camera_namespace"),
            name="vimbax_camera",
            parameters=parameters,
        )
    ]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "camera_namespace",
                default_value="/vimbax_camera",
                description="Namespace the driver services resolve under.",
            ),
            DeclareLaunchArgument(
                "params_file",
                default_value=PathJoinSubstitution(
                    [
                        FindPackageShare("venimapping_bringup"),
                        "config",
                        "camera.yaml",
                    ]
                ),
                description="Driver parameter file.",
            ),
            DeclareLaunchArgument(
                "use_ros_time",
                default_value="true",
                description="Host header stamps. Only the device stamp probe sets false.",
            ),
            DeclareLaunchArgument(
                "settings_file",
                default_value=PathJoinSubstitution(
                    [
                        FindPackageShare("venimapping_bringup"),
                        "config",
                        "camera_settings.xml",
                    ]
                ),
                description="Camera feature file that the driver loads on each open.",
            ),
            OpaqueFunction(function=launch_driver),
        ]
    )
