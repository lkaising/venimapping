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
#include <expected>
#include <future>
#include <memory>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "rclcpp/utilities.hpp"
#include "vimbax_camera_msgs/msg/feature_module.hpp"

#include "detail/gateway_util.hpp"
#include "venimapping_camera/expected.hpp"

namespace venimapping::camera {

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
          "gateway construction failed: timeout is not positive (" +
              std::to_string(timeout.count()) + " ms)"));
    }
    // std::make_unique cannot reach the private constructor.
    return std::unique_ptr<VimbaXCameraGateway>{
        new VimbaXCameraGateway{node, std::move(camera_namespace), timeout}};
  } catch (const std::exception& e) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kConstructionFailed,
        std::string{"gateway construction failed: "} + e.what()));
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
      connection_status_client_{
          node.create_client<vimbax_camera_msgs::srv::ConnectionStatus>(
              detail::ServiceName(camera_namespace, "connected"))},
      status_client_{node.create_client<vimbax_camera_msgs::srv::Status>(
          detail::ServiceName(camera_namespace, "status"))},
      features_list_get_client_{
          node.create_client<vimbax_camera_msgs::srv::FeaturesListGet>(
              detail::ServiceName(camera_namespace, "features/list_get"))},
      feature_access_mode_get_client_{
          node.create_client<vimbax_camera_msgs::srv::FeatureAccessModeGet>(
              detail::ServiceName(camera_namespace, "features/access_mode_get"))},
      feature_float_get_client_{
          node.create_client<vimbax_camera_msgs::srv::FeatureFloatGet>(
              detail::ServiceName(camera_namespace, "features/float_get"))},
      feature_float_set_client_{
          node.create_client<vimbax_camera_msgs::srv::FeatureFloatSet>(
              detail::ServiceName(camera_namespace, "features/float_set"))},
      feature_float_info_get_client_{
          node.create_client<vimbax_camera_msgs::srv::FeatureFloatInfoGet>(
              detail::ServiceName(camera_namespace, "features/float_info_get"))},
      feature_enum_get_client_{
          node.create_client<vimbax_camera_msgs::srv::FeatureEnumGet>(
              detail::ServiceName(camera_namespace, "features/enum_get"))},
      feature_enum_set_client_{
          node.create_client<vimbax_camera_msgs::srv::FeatureEnumSet>(
              detail::ServiceName(camera_namespace, "features/enum_set"))},
      feature_enum_info_get_client_{
          node.create_client<vimbax_camera_msgs::srv::FeatureEnumInfoGet>(
              detail::ServiceName(camera_namespace, "features/enum_info_get"))}
{
}

void VimbaXCameraGateway::BindToCurrentThread()
{
  assert(!bound_thread_.has_value() &&
         "VimbaXCameraGateway: BindToCurrentThread() called more than once");
  bound_thread_ = std::this_thread::get_id();
}

void VimbaXCameraGateway::AssertCallableFromThisThread() const
{
  assert(bound_thread_.has_value() &&
         "VimbaXCameraGateway: call before BindToCurrentThread()");
  assert(*bound_thread_ == std::this_thread::get_id() &&
         "VimbaXCameraGateway: call from a thread other than the bound worker");
}

// Defined here rather than in the header deliberately: every instantiation
// lives in this translation unit, so the definition never needs to be visible
// to consumers.
template <typename Service>
Expected<typename Service::Response::SharedPtr> VimbaXCameraGateway::Call(
    rclcpp::Client<Service>& client,
    typename Service::Request::SharedPtr request)
{
  AssertCallableFromThisThread();

  // Assigned inside the try so a throw during name resolution converts like
  // any other client failure; the placeholder keeps the diagnostic usable.
  std::string service_name{"(unresolved service)"};
  try {
    // rclcpp resolves the name against the node, so diagnostics carry the
    // effective path even when the configured namespace was relative.
    service_name = client.get_service_name();

    if (!client.wait_for_service(timeout_)) {
      // wait_for_service() also returns false, immediately, once the context
      // is shut down; that case must not claim the full timeout elapsed.
      // rclcpp::ok() checks the default context, which is the one Stage 1
      // runs on; a node on a custom context would blur this distinction only.
      if (!rclcpp::ok()) {
        return std::unexpected(detail::GatewayError(
            detail::GatewayDiagnostic::kServiceUnavailable,
            "service " + service_name +
                " unavailable: context shut down while waiting"));
      }
      return std::unexpected(detail::GatewayError(
          detail::GatewayDiagnostic::kServiceUnavailable,
          "service " + service_name + " unavailable after " +
              std::to_string(timeout_.count()) + " ms"));
    }

    auto future = client.async_send_request(std::move(request));
    if (future.wait_for(timeout_) != std::future_status::ready) {
      // Releases the client's bookkeeping for a reply that may never arrive;
      // a late response is then dropped by rclcpp instead of accumulating. A
      // response landing between the wait expiring and this removal is
      // discarded with it, so a timeout on a setter does not prove the write
      // failed to reach the camera.
      client.remove_pending_request(future);
      return std::unexpected(detail::GatewayError(
          detail::GatewayDiagnostic::kResponseTimeout,
          "timeout on " + service_name + " after " +
              std::to_string(timeout_.count()) + " ms"));
    }

    return future.get();
  } catch (const std::exception& e) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kRosClientFailure,
        "rclcpp client failure on " + service_name + ": " + e.what()));
  } catch (...) {
    return std::unexpected(detail::GatewayError(
        detail::GatewayDiagnostic::kRosClientFailure,
        "rclcpp client failure on " + service_name + ": unknown exception"));
  }
}

Expected<double> VimbaXCameraGateway::FeatureFloatGet(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatGet;
  auto request = std::make_shared<ServiceT::Request>();
  request->feature_name = name;
  request->feature_module.id =
      vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  return Call<ServiceT>(*feature_float_get_client_, std::move(request))
      .and_then([](auto response) -> Expected<double> {
        return detail::CheckDriverError(response->error.code, response->error.text)
            .transform([&] { return response->value; });
      });
}

Expected<void> VimbaXCameraGateway::FeatureFloatSet(const std::string& name,
                                                    double value)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatSet;
  auto request = std::make_shared<ServiceT::Request>();
  request->feature_name = name;
  request->feature_module.id =
      vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  request->value = value;
  return Call<ServiceT>(*feature_float_set_client_, std::move(request))
      .and_then([](auto response) {
        return detail::CheckDriverError(response->error.code, response->error.text);
      });
}

Expected<FloatInfo> VimbaXCameraGateway::FeatureFloatInfoGet(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatInfoGet;
  auto request = std::make_shared<ServiceT::Request>();
  request->feature_name = name;
  request->feature_module.id =
      vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  return Call<ServiceT>(*feature_float_info_get_client_, std::move(request))
      .and_then([](auto response) -> Expected<FloatInfo> {
        return detail::CheckDriverError(response->error.code, response->error.text)
            .transform([&] {
              return FloatInfo{.min = response->min,
                               .max = response->max,
                               .inc = response->inc,
                               .inc_available = response->inc_available};
            });
      });
}

Expected<std::string> VimbaXCameraGateway::FeatureEnumGet(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumGet;
  auto request = std::make_shared<ServiceT::Request>();
  request->feature_name = name;
  request->feature_module.id =
      vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  return Call<ServiceT>(*feature_enum_get_client_, std::move(request))
      .and_then([](auto response) -> Expected<std::string> {
        return detail::CheckDriverError(response->error.code, response->error.text)
            .transform([&] { return std::move(response->value); });
      });
}

Expected<void> VimbaXCameraGateway::FeatureEnumSet(const std::string& name,
                                                   const std::string& value)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumSet;
  auto request = std::make_shared<ServiceT::Request>();
  request->feature_name = name;
  request->feature_module.id =
      vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  request->value = value;
  return Call<ServiceT>(*feature_enum_set_client_, std::move(request))
      .and_then([](auto response) {
        return detail::CheckDriverError(response->error.code, response->error.text);
      });
}

Expected<EnumInfo> VimbaXCameraGateway::FeatureEnumInfoGet(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumInfoGet;
  auto request = std::make_shared<ServiceT::Request>();
  request->feature_name = name;
  request->feature_module.id =
      vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  return Call<ServiceT>(*feature_enum_info_get_client_, std::move(request))
      .and_then([](auto response) -> Expected<EnumInfo> {
        return detail::CheckDriverError(response->error.code, response->error.text)
            .transform([&] {
              return EnumInfo{
                  .possible_values = std::move(response->possible_values),
                  .available_values = std::move(response->available_values)};
            });
      });
}

Expected<AccessMode> VimbaXCameraGateway::FeatureAccessModeGet(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureAccessModeGet;
  auto request = std::make_shared<ServiceT::Request>();
  request->feature_name = name;
  request->feature_module.id =
      vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  return Call<ServiceT>(*feature_access_mode_get_client_, std::move(request))
      .and_then([](auto response) -> Expected<AccessMode> {
        return detail::CheckDriverError(response->error.code, response->error.text)
            .transform([&] {
              return AccessMode{.readable = response->is_readable,
                                .writable = response->is_writeable};
            });
      });
}

Expected<std::vector<std::string>> VimbaXCameraGateway::FeaturesListGet()
{
  using ServiceT = vimbax_camera_msgs::srv::FeaturesListGet;
  auto request = std::make_shared<ServiceT::Request>();
  request->feature_module.id =
      vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  // The driver serves this from a per-module cache built at camera open, so
  // the list is a snapshot refreshed on reconnect, not a live query.
  return Call<ServiceT>(*features_list_get_client_, std::move(request))
      .and_then([](auto response) -> Expected<std::vector<std::string>> {
        return detail::CheckDriverError(response->error.code, response->error.text)
            .transform([&] { return std::move(response->feature_list); });
      });
}

Expected<CameraStatus> VimbaXCameraGateway::CameraStatusGet()
{
  using ServiceT = vimbax_camera_msgs::srv::Status;
  auto request = std::make_shared<ServiceT::Request>();
  return Call<ServiceT>(*status_client_, std::move(request))
      .and_then([](auto response) -> Expected<CameraStatus> {
        return detail::CheckDriverError(response->error.code, response->error.text)
            .transform([&] {
              return CameraStatus{
                  .model_name = std::move(response->model_name),
                  .device_serial_number = std::move(response->device_serial_number),
                  .pixel_format = std::move(response->pixel_format),
                  .frame_rate = response->frame_rate,
                  .width = response->width,
                  .height = response->height,
                  .streaming = response->streaming};
            });
      });
}

Expected<bool> VimbaXCameraGateway::ConnectionStatusGet()
{
  using ServiceT = vimbax_camera_msgs::srv::ConnectionStatus;
  auto request = std::make_shared<ServiceT::Request>();
  // The ConnectionStatus response is the one with no error member, so nothing
  // after transport can fail and the chain has no driver-error check.
  return Call<ServiceT>(*connection_status_client_, std::move(request))
      .transform([](auto response) { return response->connected; });
}

}  // namespace venimapping::camera
