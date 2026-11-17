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

// using Unexpected = std::unexpected<Error>;

// [[nodiscard]] constexpr Unexpected make_driver_error(std::int32_t code, std::string text) noexcept
// {
//   return Unexpected{Error::from_driver(code, std::move(text))};
// }

// [[nodiscard]] constexpr Unexpected make_gateway_error(std::int32_t code, std::string text) noexcept
// {
//   return Unexpected{Error::from_gateway(code, std::move(text))};
// }

}  // namespace venimapping::camera
