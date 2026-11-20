// -----------------------------------------------------------------------------
//  Filename: feature_module.hpp
//
//  Purpose:  Defines the modules whose features a gateway call can address.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>

namespace venimapping::camera {

// The camera's own features are under kRemoteDevice; the others are host side.
enum class FeatureModule : std::uint8_t {
  kRemoteDevice = 0,
  kSystem = 1,
  kInterface = 2,
  kLocalDevice = 3,
  kStream = 4,
};

}  // namespace venimapping::camera
