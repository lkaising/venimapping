// -----------------------------------------------------------------------------
//  Filename: feature_access_mode.hpp
//
//  Purpose:  Defines the current access state of a feature.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

namespace venimapping::camera {

struct FeatureAccessMode {
  bool readable;
  bool writable;
};

}  // namespace venimapping::camera
