# ------------------------------------------------------------------------------
#  Filename: camera.launch.py
#
#  Purpose:  Brings up the vimbax_camera driver under a stable namespace so its
#            service paths do not depend on the driver's pid-suffixed default.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'camera_namespace',
            default_value='/vimbax_camera',
            description='Namespace the driver services resolve under.',
        ),
        DeclareLaunchArgument(
            'camera_id',
            default_value='',
            description='Camera to open (id, serial, MAC, or IP); empty opens '
                        'the first camera found.',
        ),
        DeclareLaunchArgument(
            'autostream',
            default_value='0',
            description='1 starts streaming when the camera opens; default 0 '
                        'because feature access modes change while streaming.',
        ),
        Node(
            package='vimbax_camera',
            executable='vimbax_camera_node',
            namespace=LaunchConfiguration('camera_namespace'),
            name='vimbax_camera',
            parameters=[{
                'camera_id': ParameterValue(
                    LaunchConfiguration('camera_id'), value_type=str),
                'autostream': ParameterValue(
                    LaunchConfiguration('autostream'), value_type=int),
            }],
        ),
    ])
