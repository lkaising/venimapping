// -----------------------------------------------------------------------------
//  Filename: feature_module.hpp
//
//  Purpose:  Defines the modules whose features a gateway call can address.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>

namespace venimapping::camera {

// Selects the module a feature call addresses. Each module has its own set of
// features: the camera's own (exposure, gain, pixel format, ...) belong to
// kRemoteDevice, and the others describe the host side of the connection.
//
// Upstream: vimbax_camera_msgs/msg/FeatureModule. The enumerator values are
// its MODULE_* constants.
enum class FeatureModule : std::uint8_t {
  kRemoteDevice = 0,
  kSystem = 1,
  kInterface = 2,
  kLocalDevice = 3,
  kStream = 4,
};

}  // namespace venimapping::camera
