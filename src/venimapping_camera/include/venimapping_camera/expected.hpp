// -----------------------------------------------------------------------------
//  Filename: expected.hpp
//
//  Purpose:  Defines the shared success/error vocabulary returned by the camera
//            feature layers.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <version>

#if !defined(__cpp_lib_expected) || __cpp_lib_expected < 202211L
#error "venimapping_camera requires std::expected with monadic operations (__cpp_lib_expected >= 202211L)"
#endif

#include <cstdint>
#include <expected>
#include <string>

namespace venimapping::camera {

// Who reported the failure. Recorded explicitly because the gateway knows it
// with certainty at the moment each Error is constructed (Section 10.2).
enum class ErrorOrigin : std::uint8_t {
  driver,   // reported by vimbax_ros2_driver; code/text are verbatim wire values
  gateway,  // originated in the gateway; no driver response existed
};

// Mirrors the driver's wire error pair (vimbax_camera_msgs/msg/Error: int32
// code, string text) so driver errors pass through without loss, and adds
// origin -- the one fact the wire cannot carry (Section 9.1).
struct Error {
  ErrorOrigin origin;
  std::int32_t code;  // driver: verbatim VmbC code; gateway: diagnostic constant (Section 9.3)
  std::string text;   // driver: verbatim wire text; gateway: contextual diagnostic (Section 10.4)
};

// Expected<void> is valid and is what the set operations return.
template <typename T>
using Expected = std::expected<T, Error>;

}  // namespace venimapping::camera
