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

#include "venimapping_camera/expected.hpp"

namespace venimapping::camera::detail {

// Identifies which gateway code path produced a failure, for logs and tests.
// Not a taxonomy and not API: classification is Error::domain() only.
enum class GatewayDiagnostic : std::int32_t {
  kServiceUnavailable = 1,
  kResponseTimeout = 2,
  kConstructionFailed = 3,
  kRosClientFailure = 4,
  kThreadContractViolation = 5,
};

Error GatewayError(GatewayDiagnostic diagnostic, std::string text);

std::string ServiceName(std::string_view camera_namespace, std::string_view leaf);

Expected<void> CheckDriverError(std::int32_t code, const std::string& text);

}  // namespace venimapping::camera::detail
