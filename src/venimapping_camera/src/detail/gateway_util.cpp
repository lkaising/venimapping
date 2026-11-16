// -----------------------------------------------------------------------------
//  Filename: gateway_util.cpp
//
//  Purpose:  Implements internal, ROS-independent gateway error helpers.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "detail/gateway_util.hpp"

namespace venimapping::camera::detail {

Error gateway_error(GatewayDiagnostic diagnostic, std::string text)
{
  return Error::from_gateway(static_cast<std::int32_t>(diagnostic), std::move(text));
}

Expected<void> check_driver_error(std::int32_t code, const std::string& text)
{
  if (code == 0) {
    return {};
  }
  return std::unexpected(Error::from_driver(code, text));
}

}  // namespace venimapping::camera::detail
