// -----------------------------------------------------------------------------
//  Filename: gateway_util.hpp
//
//  Purpose:  Declares the internal, ROS-independent gateway mechanics: service
//            name construction, driver-error conversion, and the gateway
//            diagnostic vocabulary.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <string>
#include <string_view>

#include "venimapping_camera/expected.hpp"

namespace venimapping::camera::detail {

// Identifies which gateway code path produced a failure, for logs and tests.
// Not a taxonomy and not API: classification is Error::domain() only.
enum class GatewayDiagnostic : std::int32_t {
  kServiceUnavailable = 1,
  kResponseTimeout = 2,
  kConstructionFailed = 3,
  kRosClientFailure = 4,
};

Error GatewayError(GatewayDiagnostic diagnostic, std::string text);

// Joins a camera namespace and a service leaf: every trailing '/' is removed
// from camera_namespace, exactly one '/' is inserted, and the leaf text is
// preserved.
//
// Precondition (debug-asserted): leaf is non-empty and does not begin with '/'.
std::string ServiceName(const std::string& camera_namespace, std::string_view leaf);

// How VimbaXCameraGateway converts a driver response error. Returns success
// when code == 0; otherwise carries the code and text through unchanged,
// without rewriting, translating, or classifying them.
Expected<void> CheckDriverError(std::int32_t code, const std::string& text);

}  // namespace venimapping::camera::detail
