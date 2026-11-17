// -----------------------------------------------------------------------------
//  Filename: feature_float_info.hpp
//
//  Purpose:  Defines the range metadata of a float feature.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

namespace venimapping::camera {

// Upstream: the response of vimbax_camera_msgs/srv/FeatureFloatInfoGet.
struct FeatureFloatInfo {
  double min;
  double max;
  double inc;  // meaningful only when inc_available is true
  bool inc_available;
};

}  // namespace venimapping::camera
