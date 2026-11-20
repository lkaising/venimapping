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

struct FeatureIntInfo {
  std::int64_t min;
  std::int64_t max;
  std::int64_t inc;
};

}  // namespace venimapping::camera
