# ------------------------------------------------------------------------------
#  Filename: CMakeLists.txt
#
#  Purpose:  Installs the VeniMapping bringup launch and config files.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

cmake_minimum_required(VERSION 3.20)
project(venimapping_bringup LANGUAGES NONE)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_camera_config test/test_camera_config.py)
endif()

ament_package()
