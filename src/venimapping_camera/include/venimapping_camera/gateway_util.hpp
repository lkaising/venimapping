// -----------------------------------------------------------------------------
//  Filename: gateway_util.hpp
//
//  Purpose:  Declares the ROS-independent gateway utilities and the
//            gateway-origin diagnostic codes.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <string>
#include <string_view>

#include "venimapping_camera/expected.hpp"

namespace venimapping::camera::gateway {

// --- Diagnostic codes --------------------------------------------------------

// Gateway-origin diagnostic codes (Error.origin == ErrorOrigin::gateway).
// These identify where a gateway-originated failure came from, for logs and
// Stage 1 tests. They are NOT a stable error taxonomy: application layers
// shall not branch on individual values, and the values may be renamed or
// renumbered until a real error model is designed from field experience.
// Positive values are a log-readability convention only; the sign carries
// no contractual meaning (Section 10.2).
inline constexpr std::int32_t kErrServiceUnavailable = 1;
inline constexpr std::int32_t kErrTimeout = 2;
inline constexpr std::int32_t kErrConstruction = 3;
inline constexpr std::int32_t kErrRclcpp = 4;
inline constexpr std::int32_t kErrCameraUnavailable = 5;  // existence pre-check found no camera (Section 9.6)
inline constexpr std::int32_t kErrDriverContract = 6;     // driver response contradicted a verified assumption (Section 9.6)

// --- Utilities ---------------------------------------------------------------

// Joins a camera namespace and a service leaf into a resolved service name:
// all trailing '/' characters are removed from camera_namespace, exactly one
// '/' is inserted, and the leaf text is preserved.
//
//   /camera    + features/float_get  ->  /camera/features/float_get
//   /camera/   + features/float_get  ->  /camera/features/float_get
//   /camera/// + status              ->  /camera/status
//   camera     + status              ->  camera/status
//   ""         + status              ->  /status
//
// The empty-namespace result is documented pure-function behavior and is
// unreachable through the gateway, which rejects an empty namespace at
// construction (Section 9.5). Validation lives at that boundary so this stays
// a pure function.
//
// Precondition (debug-asserted): leaf is non-empty and does not begin with '/'.
std::string ServiceName(
    const std::string& camera_namespace,
    std::string_view leaf);

// Wraps a driver response error pair verbatim. Any Error this produces has
// origin == ErrorOrigin::driver; it is the only sanctioned constructor of
// driver-origin errors in Stage 1.
//
// Returns success when code == 0; otherwise returns an Error carrying the
// supplied code and text unchanged. It shall never rewrite, translate, or
// classify what it is given.
Expected<void> CheckError(
    std::int32_t code,
    const std::string& text);

}  // namespace venimapping::camera::gateway
