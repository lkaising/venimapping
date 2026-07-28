// -----------------------------------------------------------------------------
//  Filename: vimbax_camera_gateway.cpp
//
//  Purpose:  Implements the concrete ROS 2 camera gateway: client construction,
//            request assembly, service invocation with timeouts, driver-error
//            passthrough, and conversion to the interface return types.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "venimapping_camera/vimbax_camera_gateway.hpp"

#include <cassert>
#include <chrono>
#include <exception>
#include <expected>
#include <format>
#include <future>
#include <memory>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

#include "rclcpp/utilities.hpp"
#include "vimbax_camera_msgs/msg/feature_module.hpp"

#include "detail/gateway_util.hpp"
#include "venimapping_camera/expected.hpp"

namespace venimapping::camera {

namespace {

template <typename Service>
[[nodiscard]] typename rclcpp::Client<Service>::SharedPtr MakeClient(
    rclcpp::Node& node,
    const std::string& camera_namespace,
    std::string_view leaf)
{
  return node.create_client<Service>(detail::ServiceName(camera_namespace, leaf));
}

template <typename Service>
[[nodiscard]] typename Service::Request::SharedPtr MakeRemoteDeviceRequest()
{
  auto request = std::make_shared<typename Service::Request>();
  request->feature_module.id = vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  return request;
}

template <typename Service>
[[nodiscard]] typename Service::Request::SharedPtr MakeRemoteFeatureRequest(
    const std::string& name)
{
  auto request = MakeRemoteDeviceRequest<Service>();
  request->feature_name = name;
  return request;
}

}  // namespace

Expected<std::unique_ptr<VimbaXCameraGateway>> VimbaXCameraGateway::Create(
    rclcpp::Node& node,
    std::string camera_namespace,
    std::chrono::milliseconds timeout)
{
  try {
    if (camera_namespace.empty()) {
      return std::unexpected(detail::GatewayError(
          detail::GatewayDiagnostic::kConstructionFailed,
          "gateway construction failed: camera_namespace is empty"));
    }
    if (timeout <= std::chrono::milliseconds::zero()) {
      return std::unexpected(detail::GatewayError(
          detail::GatewayDiagnostic::kConstructionFailed,
          std::format("gateway construction failed: timeout is not positive "
                      "({} ms)",
                      timeout.count())));
    }
    // std::make_unique cannot reach the private constructor.
    return std::unique_ptr<VimbaXCameraGateway>{
        new VimbaXCameraGateway{node, std::move(camera_namespace), timeout}};
  } catch (const std::exception& e) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kConstructionFailed,
        std::format("gateway construction failed: {}", e.what())));
  } catch (...) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kConstructionFailed,
        "gateway construction failed: unknown exception"));
  }
}

VimbaXCameraGateway::VimbaXCameraGateway(rclcpp::Node& node,
                                         std::string camera_namespace,
                                         std::chrono::milliseconds timeout)
    : timeout_{timeout},
      context_{node.get_node_base_interface()->get_context()},
      connection_status_client_{
          MakeClient<vimbax_camera_msgs::srv::ConnectionStatus>(
              node, camera_namespace, "connected")},
      status_client_{MakeClient<vimbax_camera_msgs::srv::Status>(
          node, camera_namespace, "status")},
      features_list_get_client_{
          MakeClient<vimbax_camera_msgs::srv::FeaturesListGet>(
              node, camera_namespace, "features/list_get")},
      feature_access_mode_get_client_{
          MakeClient<vimbax_camera_msgs::srv::FeatureAccessModeGet>(
              node, camera_namespace, "features/access_mode_get")},
      feature_float_get_client_{
          MakeClient<vimbax_camera_msgs::srv::FeatureFloatGet>(
              node, camera_namespace, "features/float_get")},
      feature_float_set_client_{
          MakeClient<vimbax_camera_msgs::srv::FeatureFloatSet>(
              node, camera_namespace, "features/float_set")},
      feature_float_info_get_client_{
          MakeClient<vimbax_camera_msgs::srv::FeatureFloatInfoGet>(
              node, camera_namespace, "features/float_info_get")},
      feature_enum_get_client_{
          MakeClient<vimbax_camera_msgs::srv::FeatureEnumGet>(
              node, camera_namespace, "features/enum_get")},
      feature_enum_set_client_{
          MakeClient<vimbax_camera_msgs::srv::FeatureEnumSet>(
              node, camera_namespace, "features/enum_set")},
      feature_enum_info_get_client_{
          MakeClient<vimbax_camera_msgs::srv::FeatureEnumInfoGet>(
              node, camera_namespace, "features/enum_info_get")}
{
}

Expected<void> VimbaXCameraGateway::BindToCurrentThread()
{
  std::thread::id unbound{};
  const bool bound_now = bound_thread_.compare_exchange_strong(
      unbound, std::this_thread::get_id());
  assert(bound_now &&
         "VimbaXCameraGateway: BindToCurrentThread() called more than once");
  if (!bound_now) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kThreadContractViolation,
        "BindToCurrentThread() called more than once"));
  }
  return {};
}

Expected<void> VimbaXCameraGateway::CheckCallableFromThisThread() const
{
  const std::thread::id bound = bound_thread_.load();
  assert(bound != std::thread::id{} &&
         "VimbaXCameraGateway: call before BindToCurrentThread()");
  assert(bound == std::this_thread::get_id() &&
         "VimbaXCameraGateway: call from a thread other than the bound worker");
  if (bound == std::thread::id{}) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kThreadContractViolation,
        "gateway call before BindToCurrentThread()"));
  }
  if (bound != std::this_thread::get_id()) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kThreadContractViolation,
        "gateway call from a thread other than the bound worker"));
  }
  return {};
}

// The member templates are defined here rather than in the header
// deliberately: every instantiation lives in this translation unit, so the
// definitions never need to be visible to consumers.
template <typename Service>
Expected<typename Service::Response::SharedPtr> VimbaXCameraGateway::Call(
    rclcpp::Client<Service>& client,
    typename Service::Request::SharedPtr request)
{
  if (auto callable = CheckCallableFromThisThread(); !callable) {
    return std::unexpected(std::move(callable).error());
  }

  // Assigned inside the try so a throw during name resolution converts like
  // any other client failure; the placeholder keeps the diagnostic usable.
  std::string service_name{"(unresolved service)"};
  try {
    // rclcpp resolves the name against the node, so diagnostics carry the
    // effective path even when the configured namespace was relative.
    service_name = client.get_service_name();

    if (!client.wait_for_service(timeout_)) {
      // wait_for_service() returns false without waiting once the context is
      // shut down; asking the context directly distinguishes shutdown from
      // true unavailability.
      if (!rclcpp::ok(context_)) {
        return std::unexpected(detail::GatewayError(
            detail::GatewayDiagnostic::kServiceUnavailable,
            std::format("service {} unavailable: context shut down while "
                        "waiting",
                        service_name)));
      }
      return std::unexpected(detail::GatewayError(
          detail::GatewayDiagnostic::kServiceUnavailable,
          std::format("service {} unavailable after {} ms", service_name,
                      timeout_.count())));
    }

    auto future = client.async_send_request(std::move(request));
    if (future.wait_for(timeout_) != std::future_status::ready) {
      // Once the deadline expires, the invocation reports a timeout and stops
      // tracking the pending request; a late response is then dropped by
      // rclcpp instead of accumulating.
      client.remove_pending_request(future);
      return std::unexpected(detail::GatewayError(
          detail::GatewayDiagnostic::kResponseTimeout,
          std::format("timeout on {} after {} ms", service_name,
                      timeout_.count())));
    }

    return future.get();
  } catch (const std::exception& e) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kRosClientFailure,
        std::format("rclcpp client failure on {}: {}", service_name,
                    e.what())));
  } catch (...) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kRosClientFailure,
        std::format("rclcpp client failure on {}: unknown exception",
                    service_name)));
  }
}

template <typename Service>
Expected<typename Service::Response::SharedPtr>
VimbaXCameraGateway::CallChecked(rclcpp::Client<Service>& client,
                                 typename Service::Request::SharedPtr request)
{
  auto response = Call<Service>(client, std::move(request));
  if (!response) {
    return response;
  }
  if (auto checked = detail::CheckDriverError((*response)->error.code,
                                              (*response)->error.text);
      !checked) {
    return std::unexpected(std::move(checked).error());
  }
  return response;
}

Expected<double> VimbaXCameraGateway::FeatureFloatGet(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatGet;
  return CallChecked<ServiceT>(*feature_float_get_client_,
                               MakeRemoteFeatureRequest<ServiceT>(name))
      .transform([](auto response) { return response->value; });
}

Expected<void> VimbaXCameraGateway::FeatureFloatSet(const std::string& name,
                                                    double value)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatSet;
  auto request = MakeRemoteFeatureRequest<ServiceT>(name);
  request->value = value;
  return CallChecked<ServiceT>(*feature_float_set_client_, std::move(request))
      .transform([](auto) {});
}

Expected<FloatInfo> VimbaXCameraGateway::FeatureFloatInfoGet(
    const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatInfoGet;
  return CallChecked<ServiceT>(*feature_float_info_get_client_,
                               MakeRemoteFeatureRequest<ServiceT>(name))
      .transform([](auto response) {
        return FloatInfo{.min = response->min,
                         .max = response->max,
                         .inc = response->inc,
                         .inc_available = response->inc_available};
      });
}

Expected<std::string> VimbaXCameraGateway::FeatureEnumGet(
    const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumGet;
  return CallChecked<ServiceT>(*feature_enum_get_client_,
                               MakeRemoteFeatureRequest<ServiceT>(name))
      .transform([](auto response) { return std::move(response->value); });
}

Expected<void> VimbaXCameraGateway::FeatureEnumSet(const std::string& name,
                                                   const std::string& value)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumSet;
  auto request = MakeRemoteFeatureRequest<ServiceT>(name);
  request->value = value;
  return CallChecked<ServiceT>(*feature_enum_set_client_, std::move(request))
      .transform([](auto) {});
}

Expected<EnumInfo> VimbaXCameraGateway::FeatureEnumInfoGet(
    const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumInfoGet;
  return CallChecked<ServiceT>(*feature_enum_info_get_client_,
                               MakeRemoteFeatureRequest<ServiceT>(name))
      .transform([](auto response) {
        return EnumInfo{
            .possible_values = std::move(response->possible_values),
            .available_values = std::move(response->available_values)};
      });
}

Expected<AccessMode> VimbaXCameraGateway::FeatureAccessModeGet(
    const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureAccessModeGet;
  return CallChecked<ServiceT>(*feature_access_mode_get_client_,
                               MakeRemoteFeatureRequest<ServiceT>(name))
      .transform([](auto response) {
        return AccessMode{.readable = response->is_readable,
                          .writable = response->is_writeable};
      });
}

Expected<std::vector<std::string>> VimbaXCameraGateway::FeaturesListGet()
{
  using ServiceT = vimbax_camera_msgs::srv::FeaturesListGet;
  // The driver serves this from a per-module cache built at camera open, so
  // the list is a snapshot refreshed on reconnect, not a live query.
  return CallChecked<ServiceT>(*features_list_get_client_,
                               MakeRemoteDeviceRequest<ServiceT>())
      .transform(
          [](auto response) { return std::move(response->feature_list); });
}

Expected<CameraStatus> VimbaXCameraGateway::CameraStatusGet()
{
  using ServiceT = vimbax_camera_msgs::srv::Status;
  return CallChecked<ServiceT>(*status_client_,
                               std::make_shared<ServiceT::Request>())
      .transform([](auto response) {
        return CameraStatus{
            .model_name = std::move(response->model_name),
            .device_serial_number = std::move(response->device_serial_number),
            .pixel_format = std::move(response->pixel_format),
            .frame_rate = response->frame_rate,
            .width = response->width,
            .height = response->height,
            .streaming = response->streaming};
      });
}

Expected<bool> VimbaXCameraGateway::ConnectionStatusGet()
{
  using ServiceT = vimbax_camera_msgs::srv::ConnectionStatus;
  // Deliberately raw Call(), not CallChecked(): the ConnectionStatus response
  // is the one with no error member, so nothing after transport can fail and
  // there is no driver error to check.
  return Call<ServiceT>(*connection_status_client_,
                        std::make_shared<ServiceT::Request>())
      .transform([](auto response) { return response->connected; });
}

}  // namespace venimapping::camera
