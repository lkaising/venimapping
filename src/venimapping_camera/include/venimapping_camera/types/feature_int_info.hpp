// -----------------------------------------------------------------------------
//  Filename: feature_int_info.hpp
//
//  Purpose:  Defines the range metadata of an integer feature.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>

namespace venimapping::camera {

// Upstream: the response of vimbax_camera_msgs/srv/FeatureIntInfoGet. Unlike
// the float counterpart it has no inc_available.
struct FeatureIntInfo {
  std::int64_t min;
  std::int64_t max;
  std::int64_t inc;
};

}  // namespace venimapping::camera
