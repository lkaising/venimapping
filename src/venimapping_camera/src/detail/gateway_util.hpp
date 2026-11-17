// -----------------------------------------------------------------------------
//  Filename: gateway_util.hpp
//
//  Purpose:  Declares internal, ROS-independent gateway diagnostics and error helpers.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include "venimapping_camera/types/error.hpp"

namespace venimapping::camera::detail {

// Identifies which gateway code path produced a failure, for logs and tests.
// Not a taxonomy and not API: classification is Error::domain() only.
enum class GatewayDiagnostic : std::int32_t {  // NOLINT(performance-enum-size): int32_t base matches the Error::code() contract
  kServiceUnavailable = 1,
  kResponseTimeout = 2,
  kConstructionFailed = 3,
  kRosClientFailure = 4,
  kThreadContractViolation = 5,
};

Error gateway_error(GatewayDiagnostic diagnostic, std::string text);

Error driver_error(std::int32_t code, std::string text);

}  // namespace venimapping::camera::detail
