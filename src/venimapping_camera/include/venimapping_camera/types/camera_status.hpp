// -----------------------------------------------------------------------------
//  Filename: camera_status.hpp
//
//  Purpose:  Defines the camera status reported by the driver.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <string>

namespace venimapping::camera {

// The consumed subset of the driver's camera status.
//
// Upstream: the response of vimbax_camera_msgs/srv/Status.
struct CameraStatus {
  std::string model_name;
  std::string device_serial_number;
  std::string pixel_format;
  double frame_rate;
  std::uint32_t width;
  std::uint32_t height;
  bool streaming;
};

}  // namespace venimapping::camera
