// -----------------------------------------------------------------------------
//  Filename: expected.hpp
//
//  Purpose:  Defines the result vocabulary returned by the camera layers.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <expected>

#include "venimapping_camera/types/error.hpp"

namespace venimapping::camera {

template <typename T>
using Expected = std::expected<T, Error>;

}  // namespace venimapping::camera
