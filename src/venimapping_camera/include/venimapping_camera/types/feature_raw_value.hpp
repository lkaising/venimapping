// -----------------------------------------------------------------------------
//  Filename: feature_raw_value.hpp
//
//  Purpose:  Defines the value of a raw feature.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <vector>

namespace venimapping::camera {

struct FeatureRawValue {
  std::vector<std::uint8_t> bytes;
};

}  // namespace venimapping::camera
