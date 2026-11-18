// -----------------------------------------------------------------------------
//  Filename: feature_enum_info.hpp
//
//  Purpose:  Defines the option metadata of an enum feature.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <string>
#include <vector>

namespace venimapping::camera {

struct FeatureEnumInfo {
  std::vector<std::string> possible_values;
  std::vector<std::string> available_values;  // the subset selectable right now
};

}  // namespace venimapping::camera
