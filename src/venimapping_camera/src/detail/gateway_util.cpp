// -----------------------------------------------------------------------------
//  Filename: gateway_util.cpp
//
//  Purpose:  Implements the internal, ROS-independent gateway mechanics:
//            service name construction, driver-error conversion, and gateway
//            diagnostic production.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "detail/gateway_util.hpp"

#include "venimapping_camera/expected.hpp"

namespace venimapping::camera::detail {

Error GatewayError(GatewayDiagnostic diagnostic, std::string text)
{
  return Error::FromGateway(static_cast<std::int32_t>(diagnostic), std::move(text));
}

std::string ServiceName(std::string_view camera_namespace, std::string_view leaf)
{
  assert(!leaf.empty() && "ServiceName: leaf shall be non-empty");
  assert(leaf.front() != '/' && "ServiceName: leaf shall not begin with '/'");

  const std::size_t last_kept = camera_namespace.find_last_not_of('/');
  std::string name{camera_namespace.substr(
      0, last_kept == std::string_view::npos ? 0 : last_kept + 1)};
  name += '/';
  name += leaf;
  return name;
}

Expected<void> CheckDriverError(std::int32_t code, const std::string& text)
{
  if (code == 0) {
    return {};
  }
  return std::unexpected(Error::FromDriver(code, text));
}

}  // namespace venimapping::camera::detail
