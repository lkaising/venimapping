# ------------------------------------------------------------------------------
#  Filename: CMakeLists.txt
#
#  Purpose:  Builds the ROS-free gateway API, the concrete Vimba X gateway
#            library, and the temporary integration probe.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

cmake_minimum_required(VERSION 3.20)
project(venimapping_camera LANGUAGES CXX)

set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(vimbax_camera_msgs REQUIRED)

# --- venimapping_camera_gateway_api -------------------------------------------
# Header-only target for the ROS-free contract (expected.hpp,
# camera_gateway.hpp); vimbax_camera_gateway.hpp needs the gateway library.

add_library(venimapping_camera_gateway_api INTERFACE)
target_compile_features(venimapping_camera_gateway_api INTERFACE cxx_std_23)
target_include_directories(venimapping_camera_gateway_api INTERFACE
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include/${PROJECT_NAME}>")

# --- venimapping_camera_vimbax_gateway ----------------------------------------
# Concrete gateway over the vimbax_ros2_driver services. rclcpp and
# vimbax_camera_msgs are PUBLIC because both appear in the installed header
# vimbax_camera_gateway.hpp.

add_library(venimapping_camera_vimbax_gateway
  src/vimbax_camera_gateway.cpp
  src/detail/gateway_util.cpp)
target_compile_features(venimapping_camera_vimbax_gateway PUBLIC cxx_std_23)
target_include_directories(venimapping_camera_vimbax_gateway PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}/src")
target_link_libraries(venimapping_camera_vimbax_gateway PUBLIC
  venimapping_camera_gateway_api
  rclcpp::rclcpp
  ${vimbax_camera_msgs_TARGETS})

# --- camera_gateway_probe -----------------------------------------------------
# Temporary integration probe; nothing depends on it.

add_executable(camera_gateway_probe src/camera_gateway_probe.cpp)
target_link_libraries(camera_gateway_probe PRIVATE
  venimapping_camera_vimbax_gateway
  rclcpp::rclcpp)

# --- Install ------------------------------------------------------------------
# Only the public headers are installed; nothing under src/ is, which keeps
# the detail/ diagnostic vocabulary off every consumer's include path.

install(DIRECTORY include/ DESTINATION include/${PROJECT_NAME}
  FILES_MATCHING PATTERN "*.hpp")

install(TARGETS venimapping_camera_gateway_api venimapping_camera_vimbax_gateway
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)

install(TARGETS camera_gateway_probe
  DESTINATION lib/${PROJECT_NAME})

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_dependencies(rclcpp vimbax_camera_msgs)

ament_package()
