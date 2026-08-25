// -----------------------------------------------------------------------------
//  Filename: vimbax_camera_gateway.cpp
//
//  Purpose:  Implements the concrete ROS 2 camera gateway backed by Vimba X driver services.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "venimapping_camera/vimbax_camera_gateway.hpp"

#include "rclcpp/utilities.hpp"
#include "vimbax_camera_msgs/msg/feature_module.hpp"

#include "detail/gateway_util.hpp"
#include "venimapping_camera/expected.hpp"

namespace venimapping::camera {

namespace {

using Clock = std::chrono::steady_clock;
using ContextPtr = rclcpp::Context::SharedPtr;
using Deadline = Clock::time_point;
using StringView = std::string_view;

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
                                             StringView camera_namespace,
                                             StringView leaf)
{
  return node.create_client<Service>(detail::service_name(camera_namespace, leaf));
}

template <typename Service>
[[nodiscard]] RequestPtr<Service> make_remote_device_request()
{
  auto request = std::make_shared<typename Service::Request>();
  request->feature_module.id = vimbax_camera_msgs::msg::FeatureModule::MODULE_REMOTE_DEVICE;
  return request;
}

template <typename Service>
[[nodiscard]] RequestPtr<Service> make_remote_feature_request(StringView name)
{
  auto request = make_remote_device_request<Service>();
  request->feature_name = name;
  return request;
}

template <typename Service>
[[nodiscard]] Expected<void> wait_for_service(Client<Service>& client,
                                              const ContextPtr& context,
                                              Deadline deadline,
                                              StringView service_name)
{
  const auto remaining = std::max(deadline - Clock::now(), Clock::duration::zero());
  if (client.wait_for_service(remaining)) {
    return {};
  }

  if (!rclcpp::ok(context)) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kServiceUnavailable,
        std::format("service {} unavailable: context shut down while waiting", service_name)));
  }

  return std::unexpected(detail::gateway_error(
      detail::GatewayDiagnostic::kServiceUnavailable,
      std::format("service {} unavailable: call deadline reached", service_name)));
}

template <typename Service, typename Future>
[[nodiscard]] Expected<ResponsePtr<Service>> wait_for_response(Client<Service>& client,
                                                               Future& future,
                                                               Deadline deadline,
                                                               StringView service_name)
{
  if (future.wait_until(deadline) == std::future_status::ready) {
    return future.get();
  }

  client.remove_pending_request(future);

  return std::unexpected(detail::gateway_error(
      detail::GatewayDiagnostic::kResponseTimeout,
      std::format("timeout on {}: call deadline reached", service_name)));
}

}  // namespace

Expected<std::unique_ptr<VimbaXCameraGateway>> VimbaXCameraGateway::create(
    rclcpp::Node& node,
    const std::string& camera_namespace,
    std::chrono::milliseconds timeout)
{
  if (camera_namespace.empty()) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kConstructionFailed,
        "gateway construction failed: camera_namespace is empty"));
  }

  if (timeout <= std::chrono::milliseconds::zero()) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kConstructionFailed,
        std::format(
            "gateway construction failed: timeout is not positive ({} ms)",
            timeout.count())));
  }

  try {
    return std::unique_ptr<VimbaXCameraGateway>{
        new VimbaXCameraGateway{node, camera_namespace, timeout}};
  } catch (const std::exception& e) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kConstructionFailed,
        std::format("gateway construction failed: {}", e.what())));
  } catch (...) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kConstructionFailed,
        "gateway construction failed: unknown exception"));
  }
}

VimbaXCameraGateway::VimbaXCameraGateway(rclcpp::Node& node,
                                         const std::string& camera_namespace,
                                         std::chrono::milliseconds timeout)
    : timeout_{timeout},
      context_{node.get_node_base_interface()->get_context()},
      connection_status_client_{
          make_client<vimbax_camera_msgs::srv::ConnectionStatus>(
              node, camera_namespace, "connected")},
      status_client_{
          make_client<vimbax_camera_msgs::srv::Status>(
              node, camera_namespace, "status")},
      features_list_get_client_{
          make_client<vimbax_camera_msgs::srv::FeaturesListGet>(
              node, camera_namespace, "features/list_get")},
      feature_access_mode_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureAccessModeGet>(
              node, camera_namespace, "features/access_mode_get")},
      feature_float_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureFloatGet>(
              node, camera_namespace, "features/float_get")},
      feature_float_set_client_{
          make_client<vimbax_camera_msgs::srv::FeatureFloatSet>(
              node, camera_namespace, "features/float_set")},
      feature_float_info_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureFloatInfoGet>(
              node, camera_namespace, "features/float_info_get")},
      feature_enum_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureEnumGet>(
              node, camera_namespace, "features/enum_get")},
      feature_enum_set_client_{
          make_client<vimbax_camera_msgs::srv::FeatureEnumSet>(
              node, camera_namespace, "features/enum_set")},
      feature_enum_info_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureEnumInfoGet>(
              node, camera_namespace, "features/enum_info_get")}
{
}

Expected<void> VimbaXCameraGateway::bind_to_current_thread()
{
  std::thread::id unbound{};
  if (!bound_thread_.compare_exchange_strong(unbound, std::this_thread::get_id())) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kThreadContractViolation,
        "bind_to_current_thread() called more than once"));
  }

  return {};
}

Expected<void> VimbaXCameraGateway::check_callable_from_this_thread() const
{
  const std::thread::id bound = bound_thread_.load();
  const std::thread::id current = std::this_thread::get_id();

  if (bound == std::thread::id{}) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kThreadContractViolation,
        "gateway call before bind_to_current_thread()"));
  }

  if (bound != current) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kThreadContractViolation,
        "gateway call from a thread other than the bound worker"));
  }

  return {};
}

template <typename Service>
auto VimbaXCameraGateway::call(Client<Service>& client, RequestPtr<Service> request)
    -> Expected<ResponsePtr<Service>>
{
  if (auto thread_check = check_callable_from_this_thread(); !thread_check) {
    return std::unexpected(std::move(thread_check).error());
  }

  const Deadline deadline = Clock::now() + timeout_;
  std::string service_name{"(unresolved service)"};

  try {
    service_name = client.get_service_name();

    auto service_check = wait_for_service(client, context_, deadline, service_name);
    if (!service_check) {
      return std::unexpected(std::move(service_check).error());
    }

    auto future = client.async_send_request(std::move(request));

    return wait_for_response<Service>(client, future, deadline, service_name);
  } catch (const std::exception& e) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kRosClientFailure,
        std::format("rclcpp client failure on {}: {}", service_name, e.what())));
  } catch (...) {
    return std::unexpected(detail::gateway_error(
        detail::GatewayDiagnostic::kRosClientFailure,
        std::format("rclcpp client failure on {}: unknown exception", service_name)));
  }
}

template <typename Service>
auto VimbaXCameraGateway::call_checked(Client<Service>& client, RequestPtr<Service> request)
    -> Expected<ResponsePtr<Service>>
{
  auto response = call<Service>(client, std::move(request));
  if (!response) {
    return response;
  }

  auto driver_check = detail::check_driver_error((*response)->error.code, (*response)->error.text);
  if (!driver_check) {
    return std::unexpected(std::move(driver_check).error());
  }

  return response;
}

Expected<double> VimbaXCameraGateway::feature_float_get(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatGet;
  return call_checked<ServiceT>(
             *feature_float_get_client_,
             make_remote_feature_request<ServiceT>(name))
      .transform([](const auto& response) { return response->value; });
}

Expected<void> VimbaXCameraGateway::feature_float_set(const std::string& name, double value)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatSet;
  auto request = make_remote_feature_request<ServiceT>(name);
  request->value = value;
  return call_checked<ServiceT>(*feature_float_set_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<FloatInfo> VimbaXCameraGateway::feature_float_info_get(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatInfoGet;
  return call_checked<ServiceT>(
             *feature_float_info_get_client_,
             make_remote_feature_request<ServiceT>(name))
      .transform([](const auto& response) {
        return FloatInfo{
            .min = response->min,
            .max = response->max,
            .inc = response->inc,
            .inc_available = response->inc_available,
        };
      });
}

Expected<std::string> VimbaXCameraGateway::feature_enum_get(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumGet;
  return call_checked<ServiceT>(
             *feature_enum_get_client_,
             make_remote_feature_request<ServiceT>(name))
      .transform([](const auto& response) { return std::move(response->value); });
}

Expected<void> VimbaXCameraGateway::feature_enum_set(const std::string& name,
                                                     const std::string& value)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumSet;
  auto request = make_remote_feature_request<ServiceT>(name);
  request->value = value;
  return call_checked<ServiceT>(*feature_enum_set_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<EnumInfo> VimbaXCameraGateway::feature_enum_info_get(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumInfoGet;
  return call_checked<ServiceT>(
             *feature_enum_info_get_client_,
             make_remote_feature_request<ServiceT>(name))
      .transform([](const auto& response) {
        return EnumInfo{
            .possible_values = std::move(response->possible_values),
            .available_values = std::move(response->available_values),
        };
      });
}

Expected<AccessMode> VimbaXCameraGateway::feature_access_mode_get(const std::string& name)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureAccessModeGet;
  return call_checked<ServiceT>(
             *feature_access_mode_get_client_,
             make_remote_feature_request<ServiceT>(name))
      .transform([](const auto& response) {
        return AccessMode{
            .readable = response->is_readable,
            .writable = response->is_writeable,
        };
      });
}

Expected<std::vector<std::string>> VimbaXCameraGateway::features_list_get()
{
  using ServiceT = vimbax_camera_msgs::srv::FeaturesListGet;
  return call_checked<ServiceT>(
             *features_list_get_client_,
             make_remote_device_request<ServiceT>())
      .transform([](const auto& response) { return std::move(response->feature_list); });
}

Expected<CameraStatus> VimbaXCameraGateway::camera_status_get()
{
  using ServiceT = vimbax_camera_msgs::srv::Status;
  return call_checked<ServiceT>(
             *status_client_,
             std::make_shared<ServiceT::Request>())
      .transform([](const auto& response) {
        return CameraStatus{
            .model_name = std::move(response->model_name),
            .device_serial_number = std::move(response->device_serial_number),
            .pixel_format = std::move(response->pixel_format),
            .frame_rate = response->frame_rate,
            .width = response->width,
            .height = response->height,
            .streaming = response->streaming,
        };
      });
}

Expected<bool> VimbaXCameraGateway::connection_status_get()
{
  using ServiceT = vimbax_camera_msgs::srv::ConnectionStatus;
  return call<ServiceT>(
             *connection_status_client_,
             std::make_shared<ServiceT::Request>())
      .transform([](const auto& response) { return response->connected; });
}

}  // namespace venimapping::camera
