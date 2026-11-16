# ------------------------------------------------------------------------------
#  Filename: camera.launch.py
#
#  Purpose:  Launches the Vimba X camera driver with a namespace and YAML parameters.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


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
            Node(
                package="vimbax_camera",
                executable="vimbax_camera_node",
                namespace=LaunchConfiguration("camera_namespace"),
                name="vimbax_camera",
                parameters=[LaunchConfiguration("params_file")],
            ),
        ]
    )
