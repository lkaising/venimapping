// -----------------------------------------------------------------------------
//  Filename: feature_list.hpp
//
//  Purpose:  Defines the names of the features in a module.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <string>
#include <vector>

namespace venimapping::camera {

struct FeatureList {
  std::vector<std::string> names;
};

}  // namespace venimapping::camera
