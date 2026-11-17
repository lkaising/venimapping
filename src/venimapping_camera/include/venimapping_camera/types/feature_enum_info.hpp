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

// Upstream: the response of vimbax_camera_msgs/srv/FeatureEnumInfoGet.
struct FeatureEnumInfo {
  std::vector<std::string> possible_values;   // every option the feature defines
  std::vector<std::string> available_values;  // the subset selectable right now
};

}  // namespace venimapping::camera
