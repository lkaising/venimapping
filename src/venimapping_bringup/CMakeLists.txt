# ------------------------------------------------------------------------------
#  Filename: CMakeLists.txt
#
#  Purpose:  Installs the VeniMapping bringup launch files.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

cmake_minimum_required(VERSION 3.20)
project(venimapping_bringup LANGUAGES NONE)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})

ament_package()
