// -----------------------------------------------------------------------------
//  Filename: feature_access_mode.hpp
//
//  Purpose:  Defines the current access state of a feature.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

namespace venimapping::camera {

// Current access state of a feature. It changes with streaming and with other
// feature values, so a result describes the moment it was queried.
//
// Upstream: the response of vimbax_camera_msgs/srv/FeatureAccessModeGet, which
// spells the fields is_readable and is_writeable.
struct FeatureAccessMode {
  bool readable;
  bool writable;
};

}  // namespace venimapping::camera
