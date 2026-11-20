// -----------------------------------------------------------------------------
//  Filename: feature_float_info.hpp
//
//  Purpose:  Defines the range metadata of a float feature.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

namespace venimapping::camera {

struct FeatureFloatInfo {
  double min;
  double max;
  double inc;
  bool inc_available;
};

}  // namespace venimapping::camera
