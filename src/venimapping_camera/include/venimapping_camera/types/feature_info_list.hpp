// -----------------------------------------------------------------------------
//  Filename: feature_info_list.hpp
//
//  Purpose:  Defines the static descriptions of a set of features.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <vector>

#include "venimapping_camera/types/feature_info.hpp"

namespace venimapping::camera {

struct FeatureInfoList {
  std::vector<FeatureInfo> features;
};

}  // namespace venimapping::camera
