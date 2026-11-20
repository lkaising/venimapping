// -----------------------------------------------------------------------------
//  Filename: vimbax_service_calls.cpp
//
//  Purpose:  Implements the non-template Vimba X service call helpers.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "vimbax_service_calls.hpp"

namespace venimapping::camera::gateway_support {

Expected<void> wait_for_service(rclcpp::ClientBase& client,
                                const rclcpp::Context::SharedPtr& context,
                                Deadline deadline,
                                std::string_view service_name)
{
  const auto remaining = std::max(deadline - Clock::now(), Clock::duration::zero());
  if (client.wait_for_service(remaining)) {
    return {};
  }

  if (!rclcpp::ok(context)) {
    return std::unexpected(gateway_error(
        GatewayDiagnostic::kServiceUnavailable,
        std::format("service {} unavailable: context shut down while waiting", service_name)));
  }

  return std::unexpected(gateway_error(
      GatewayDiagnostic::kServiceUnavailable,
      std::format("service {} unavailable: call deadline reached", service_name)));
}

}  // namespace venimapping::camera::gateway_support
