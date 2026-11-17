// -----------------------------------------------------------------------------
//  Filename: gateway_util.cpp
//
//  Purpose:  Implements internal, ROS-independent gateway error helpers.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "detail/gateway_util.hpp"

#include <cstdint>
#include <string>
#include <utility>

namespace venimapping::camera::detail {

Error gateway_error(GatewayDiagnostic diagnostic, std::string text)
{
  return Error::from_gateway(static_cast<std::int32_t>(diagnostic), std::move(text));
}

Error driver_error(std::int32_t code, std::string text)
{
  return Error::from_driver(code, std::move(text));
}

}  // namespace venimapping::camera::detail
