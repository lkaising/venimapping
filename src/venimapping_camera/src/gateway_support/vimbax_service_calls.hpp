// -----------------------------------------------------------------------------
//  Filename: vimbax_service_calls.hpp
//
//  Purpose:  Defines the client, request, and wait helpers for Vimba X service calls.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include "rclcpp/node.hpp"
#include "vimbax_camera_msgs/msg/feature_module.hpp"

#include "venimapping_camera/types/expected.hpp"
#include "venimapping_camera/types/feature_module.hpp"

#include "gateway_errors.hpp"

namespace venimapping::camera::gateway_support {

using Clock = std::chrono::steady_clock;
using Deadline = Clock::time_point;

template <typename Service>
using Client = rclcpp::Client<Service>;

template <typename Service>
using ClientPtr = typename Client<Service>::SharedPtr;

template <typename Service>
using RequestPtr = typename Service::Request::SharedPtr;

template <typename Service>
using ResponsePtr = typename Service::Response::SharedPtr;

template <typename Service>
[[nodiscard]] ClientPtr<Service> make_client(rclcpp::Node& node,
                                             std::string_view camera_namespace,
                                             std::string_view leaf)
{
  while (camera_namespace.ends_with('/')) {
    camera_namespace.remove_suffix(1);
  }

  return node.create_client<Service>(std::format("{}/{}", camera_namespace, leaf));
}

template <typename Service>
[[nodiscard]] RequestPtr<Service> make_module_request(FeatureModule feature_module)
{
  using ModuleMsg = vimbax_camera_msgs::msg::FeatureModule;

  static_assert(
      std::to_underlying(FeatureModule::kRemoteDevice) == ModuleMsg::MODULE_REMOTE_DEVICE &&
      std::to_underlying(FeatureModule::kSystem) == ModuleMsg::MODULE_SYSTEM &&
      std::to_underlying(FeatureModule::kInterface) == ModuleMsg::MODULE_INTERFACE &&
      std::to_underlying(FeatureModule::kLocalDevice) == ModuleMsg::MODULE_LOCAL_DEVICE &&
      std::to_underlying(FeatureModule::kStream) == ModuleMsg::MODULE_STREAM);

  auto request = std::make_shared<typename Service::Request>();
  request->feature_module.id = std::to_underlying(feature_module);
  return request;
}

template <typename Service>
[[nodiscard]] RequestPtr<Service> make_feature_request(std::string_view feature_name,
                                                       FeatureModule feature_module)
{
  auto request = make_module_request<Service>(feature_module);
  request->feature_name = feature_name;
  return request;
}

[[nodiscard]] Expected<void> wait_for_service(rclcpp::ClientBase& client,
                                              const rclcpp::Context::SharedPtr& context,
                                              Deadline deadline,
                                              std::string_view service_name);

template <typename Service, typename Future>
[[nodiscard]] Expected<ResponsePtr<Service>> wait_for_response(Client<Service>& client,
                                                               Future& future,
                                                               Deadline deadline,
                                                               std::string_view service_name)
{
  if (future.wait_until(deadline) == std::future_status::ready) {
    return future.get();
  }

  client.remove_pending_request(future);

  return std::unexpected(gateway_error(
      GatewayDiagnostic::kResponseTimeout,
      std::format("timeout on {}: call deadline reached", service_name)));
}

}  // namespace venimapping::camera::gateway_support
