// -----------------------------------------------------------------------------
//  Filename: vimbax_camera_gateway.cpp
//
//  Purpose:  Implements the concrete ROS 2 camera gateway backed by Vimba X driver services.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "venimapping_camera/vimbax_camera_gateway.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <exception>
#include <expected>
#include <format>
#include <future>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <thread>
#include <utility>
#include <vector>

#include "rclcpp/utilities.hpp"
#include "vimbax_camera_msgs/msg/feature_info.hpp"
#include "vimbax_camera_msgs/msg/feature_module.hpp"
#include "vimbax_camera_msgs/msg/trigger_info.hpp"

#include "detail/gateway_util.hpp"

namespace venimapping::camera {

namespace {

namespace vimbax_msgs = vimbax_camera_msgs::msg;

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
  while (camera_namespace.ends_with('/')) {
    camera_namespace.remove_suffix(1);
  }

  return node.create_client<Service>(std::format("{}/{}", camera_namespace, leaf));
}

template <typename Service>
[[nodiscard]] RequestPtr<Service> make_module_request(FeatureModule feature_module)
{
  using ModuleMsg = vimbax_msgs::FeatureModule;

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
[[nodiscard]] RequestPtr<Service> make_feature_request(StringView feature_name,
                                                       FeatureModule feature_module)
{
  auto request = make_module_request<Service>(feature_module);
  request->feature_name = feature_name;
  return request;
}

[[nodiscard]] std::vector<TriggerInfo> to_trigger_info(std::vector<vimbax_msgs::TriggerInfo>& wire)
{
  std::vector<TriggerInfo> trigger_info;
  trigger_info.reserve(wire.size());
  for (auto& entry : wire) {
    trigger_info.push_back(TriggerInfo{
        .selector = std::move(entry.selector),
        .mode = std::move(entry.mode),
        .source = std::move(entry.source),
    });
  }
  return trigger_info;
}

[[nodiscard]] std::optional<std::string> to_optional_address(std::string& wire)
{
  if (wire.empty()) {
    return std::nullopt;
  }
  return std::move(wire);
}

[[nodiscard]] constexpr FeatureDataType to_feature_data_type(std::uint32_t wire) noexcept
{
  if (wire > std::to_underlying(FeatureDataType::kNone)) {
    return FeatureDataType::kUnknown;
  }
  return static_cast<FeatureDataType>(wire);
}

[[nodiscard]] std::vector<FeatureInfo> to_feature_info(std::vector<vimbax_msgs::FeatureInfo>& wire)
{
  std::vector<FeatureInfo> feature_info;
  feature_info.reserve(wire.size());
  for (auto& entry : wire) {
    feature_info.push_back(FeatureInfo{
        .name = std::move(entry.name),
        .category = std::move(entry.category),
        .display_name = std::move(entry.display_name),
        .sfnc_namespace = std::move(entry.sfnc_namespace),
        .unit = std::move(entry.unit),
        .data_type = to_feature_data_type(entry.data_type),
        .flags = FeatureFlags{
            .none = entry.flags.flag_none,
            .read = entry.flags.flag_read,
            .write = entry.flags.flag_write,
            .is_volatile = entry.flags.flag_volatile,
            .modify_write = entry.flags.flag_modify_write,
        },
        .polling_time = entry.polling_time,
    });
  }
  return feature_info;
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
      stream_start_client_{
          make_client<vimbax_camera_msgs::srv::StreamStartStop>(
              node, camera_namespace, "stream_start")},
      stream_stop_client_{
          make_client<vimbax_camera_msgs::srv::StreamStartStop>(
              node, camera_namespace, "stream_stop")},
      settings_save_client_{
          make_client<vimbax_camera_msgs::srv::SettingsLoadSave>(
              node, camera_namespace, "settings/save")},
      settings_load_client_{
          make_client<vimbax_camera_msgs::srv::SettingsLoadSave>(
              node, camera_namespace, "settings/load")},
      features_list_get_client_{
          make_client<vimbax_camera_msgs::srv::FeaturesListGet>(
              node, camera_namespace, "features/list_get")},
      feature_info_query_client_{
          make_client<vimbax_camera_msgs::srv::FeatureInfoQuery>(
              node, camera_namespace, "feature_info_query")},
      feature_access_mode_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureAccessModeGet>(
              node, camera_namespace, "features/access_mode_get")},
      feature_int_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureIntGet>(
              node, camera_namespace, "features/int_get")},
      feature_int_set_client_{
          make_client<vimbax_camera_msgs::srv::FeatureIntSet>(
              node, camera_namespace, "features/int_set")},
      feature_int_info_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureIntInfoGet>(
              node, camera_namespace, "features/int_info_get")},
      feature_float_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureFloatGet>(
              node, camera_namespace, "features/float_get")},
      feature_float_set_client_{
          make_client<vimbax_camera_msgs::srv::FeatureFloatSet>(
              node, camera_namespace, "features/float_set")},
      feature_float_info_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureFloatInfoGet>(
              node, camera_namespace, "features/float_info_get")},
      feature_string_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureStringGet>(
              node, camera_namespace, "features/string_get")},
      feature_string_set_client_{
          make_client<vimbax_camera_msgs::srv::FeatureStringSet>(
              node, camera_namespace, "features/string_set")},
      feature_string_info_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureStringInfoGet>(
              node, camera_namespace, "features/string_info_get")},
      feature_bool_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureBoolGet>(
              node, camera_namespace, "features/bool_get")},
      feature_bool_set_client_{
          make_client<vimbax_camera_msgs::srv::FeatureBoolSet>(
              node, camera_namespace, "features/bool_set")},
      feature_enum_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureEnumGet>(
              node, camera_namespace, "features/enum_get")},
      feature_enum_set_client_{
          make_client<vimbax_camera_msgs::srv::FeatureEnumSet>(
              node, camera_namespace, "features/enum_set")},
      feature_enum_info_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureEnumInfoGet>(
              node, camera_namespace, "features/enum_info_get")},
      feature_enum_as_int_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureEnumAsIntGet>(
              node, camera_namespace, "features/enum_as_int_get")},
      feature_enum_as_string_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureEnumAsStringGet>(
              node, camera_namespace, "features/enum_as_string_get")},
      feature_command_run_client_{
          make_client<vimbax_camera_msgs::srv::FeatureCommandRun>(
              node, camera_namespace, "features/command_run")},
      feature_command_is_done_client_{
          make_client<vimbax_camera_msgs::srv::FeatureCommandIsDone>(
              node, camera_namespace, "features/command_is_done")},
      feature_raw_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureRawGet>(
              node, camera_namespace, "features/raw_get")},
      feature_raw_set_client_{
          make_client<vimbax_camera_msgs::srv::FeatureRawSet>(
              node, camera_namespace, "features/raw_set")},
      feature_raw_info_get_client_{
          make_client<vimbax_camera_msgs::srv::FeatureRawInfoGet>(
              node, camera_namespace, "features/raw_info_get")}
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

  const auto& driver = (*response)->error;
  if (driver.code != 0) {
    return std::unexpected(detail::driver_error(driver.code, driver.text));
  }

  return response;
}

Expected<bool> VimbaXCameraGateway::connection_status_get()
{
  using ServiceT = vimbax_camera_msgs::srv::ConnectionStatus;
  return call<ServiceT>(
             *connection_status_client_,
             std::make_shared<ServiceT::Request>())
      .transform([](const auto& response) { return response->connected; });
}

Expected<CameraStatus> VimbaXCameraGateway::camera_status_get()
{
  using ServiceT = vimbax_camera_msgs::srv::Status;
  return call_checked<ServiceT>(
             *status_client_,
             std::make_shared<ServiceT::Request>())
      .transform([](const auto& response) {
        return CameraStatus{
            .display_name = std::move(response->display_name),
            .model_name = std::move(response->model_name),
            .device_firmware_version = std::move(response->device_firmware_version),
            .device_id = std::move(response->device_id),
            .device_user_id = std::move(response->device_user_id),
            .device_serial_number = std::move(response->device_serial_number),
            .interface_id = std::move(response->interface_id),
            .transport_layer_id = std::move(response->transport_layer_id),
            .streaming = response->streaming,
            .width = response->width,
            .height = response->height,
            .frame_rate = response->frame_rate,
            .pixel_format = std::move(response->pixel_format),
            .trigger_info = to_trigger_info(response->trigger_info),
            .ip_address = to_optional_address(response->ip_address),
            .mac_address = to_optional_address(response->mac_address),
        };
      });
}

Expected<void> VimbaXCameraGateway::stream_start()
{
  using ServiceT = vimbax_camera_msgs::srv::StreamStartStop;
  return call_checked<ServiceT>(
             *stream_start_client_,
             std::make_shared<ServiceT::Request>())
      .transform([](const auto&) {});
}

Expected<void> VimbaXCameraGateway::stream_stop()
{
  using ServiceT = vimbax_camera_msgs::srv::StreamStartStop;
  return call_checked<ServiceT>(
             *stream_stop_client_,
             std::make_shared<ServiceT::Request>())
      .transform([](const auto&) {});
}

Expected<void> VimbaXCameraGateway::settings_save(const std::string& filename)
{
  using ServiceT = vimbax_camera_msgs::srv::SettingsLoadSave;
  auto request = std::make_shared<ServiceT::Request>();
  request->filename = filename;
  return call_checked<ServiceT>(*settings_save_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<void> VimbaXCameraGateway::settings_load(const std::string& filename)
{
  using ServiceT = vimbax_camera_msgs::srv::SettingsLoadSave;
  auto request = std::make_shared<ServiceT::Request>();
  request->filename = filename;
  return call_checked<ServiceT>(*settings_load_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<std::vector<std::string>> VimbaXCameraGateway::features_list_get(
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeaturesListGet;
  return call_checked<ServiceT>(
             *features_list_get_client_,
             make_module_request<ServiceT>(feature_module))
      .transform([](const auto& response) { return std::move(response->feature_list); });
}

Expected<std::vector<FeatureInfo>> VimbaXCameraGateway::feature_info_query(
    const std::vector<std::string>& feature_names,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureInfoQuery;
  auto request = make_module_request<ServiceT>(feature_module);
  request->feature_names = feature_names;
  return call_checked<ServiceT>(*feature_info_query_client_, std::move(request))
      .transform([](const auto& response) { return to_feature_info(response->feature_info); });
}

Expected<FeatureAccessMode> VimbaXCameraGateway::feature_access_mode_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureAccessModeGet;
  return call_checked<ServiceT>(
             *feature_access_mode_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return FeatureAccessMode{
            .readable = response->is_readable,
            .writable = response->is_writeable,
        };
      });
}

Expected<std::int64_t> VimbaXCameraGateway::feature_int_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureIntGet;
  return call_checked<ServiceT>(
             *feature_int_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->value; });
}

Expected<void> VimbaXCameraGateway::feature_int_set(
    const std::string& feature_name,
    std::int64_t value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureIntSet;
  auto request = make_feature_request<ServiceT>(feature_name, feature_module);
  request->value = value;
  return call_checked<ServiceT>(*feature_int_set_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<FeatureIntInfo> VimbaXCameraGateway::feature_int_info_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureIntInfoGet;
  return call_checked<ServiceT>(
             *feature_int_info_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return FeatureIntInfo{
            .min = response->min,
            .max = response->max,
            .inc = response->inc,
        };
      });
}

Expected<double> VimbaXCameraGateway::feature_float_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatGet;
  return call_checked<ServiceT>(
             *feature_float_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->value; });
}

Expected<void> VimbaXCameraGateway::feature_float_set(
    const std::string& feature_name,
    double value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatSet;
  auto request = make_feature_request<ServiceT>(feature_name, feature_module);
  request->value = value;
  return call_checked<ServiceT>(*feature_float_set_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<FeatureFloatInfo> VimbaXCameraGateway::feature_float_info_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatInfoGet;
  return call_checked<ServiceT>(
             *feature_float_info_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return FeatureFloatInfo{
            .min = response->min,
            .max = response->max,
            .inc = response->inc,
            .inc_available = response->inc_available,
        };
      });
}

Expected<std::string> VimbaXCameraGateway::feature_string_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureStringGet;
  return call_checked<ServiceT>(
             *feature_string_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return std::move(response->value); });
}

Expected<void> VimbaXCameraGateway::feature_string_set(
    const std::string& feature_name,
    const std::string& value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureStringSet;
  auto request = make_feature_request<ServiceT>(feature_name, feature_module);
  request->value = value;
  return call_checked<ServiceT>(*feature_string_set_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<std::int64_t> VimbaXCameraGateway::feature_string_info_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureStringInfoGet;
  return call_checked<ServiceT>(
             *feature_string_info_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->max_length; });
}

Expected<bool> VimbaXCameraGateway::feature_bool_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureBoolGet;
  return call_checked<ServiceT>(
             *feature_bool_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->value; });
}

Expected<void> VimbaXCameraGateway::feature_bool_set(
    const std::string& feature_name,
    bool value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureBoolSet;
  auto request = make_feature_request<ServiceT>(feature_name, feature_module);
  request->value = value;
  return call_checked<ServiceT>(*feature_bool_set_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<std::string> VimbaXCameraGateway::feature_enum_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumGet;
  return call_checked<ServiceT>(
             *feature_enum_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return std::move(response->value); });
}

Expected<void> VimbaXCameraGateway::feature_enum_set(
    const std::string& feature_name,
    const std::string& value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumSet;
  auto request = make_feature_request<ServiceT>(feature_name, feature_module);
  request->value = value;
  return call_checked<ServiceT>(*feature_enum_set_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<FeatureEnumInfo> VimbaXCameraGateway::feature_enum_info_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumInfoGet;
  return call_checked<ServiceT>(
             *feature_enum_info_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return FeatureEnumInfo{
            .possible_values = std::move(response->possible_values),
            .available_values = std::move(response->available_values),
        };
      });
}

Expected<std::int64_t> VimbaXCameraGateway::feature_enum_as_int_get(
    const std::string& feature_name,
    const std::string& option,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumAsIntGet;
  auto request = make_feature_request<ServiceT>(feature_name, feature_module);
  request->option = option;
  return call_checked<ServiceT>(*feature_enum_as_int_get_client_, std::move(request))
      .transform([](const auto& response) { return response->value; });
}

Expected<std::string> VimbaXCameraGateway::feature_enum_as_string_get(
    const std::string& feature_name,
    std::int64_t value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumAsStringGet;
  auto request = make_feature_request<ServiceT>(feature_name, feature_module);
  request->value = value;
  return call_checked<ServiceT>(*feature_enum_as_string_get_client_, std::move(request))
      .transform([](const auto& response) { return std::move(response->option); });
}

Expected<void> VimbaXCameraGateway::feature_command_run(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureCommandRun;
  return call_checked<ServiceT>(
             *feature_command_run_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto&) {});
}

Expected<bool> VimbaXCameraGateway::feature_command_is_done(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureCommandIsDone;
  return call_checked<ServiceT>(
             *feature_command_is_done_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->is_done; });
}

Expected<std::vector<std::uint8_t>> VimbaXCameraGateway::feature_raw_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureRawGet;
  return call_checked<ServiceT>(
             *feature_raw_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return std::move(response->buffer); });
}

Expected<void> VimbaXCameraGateway::feature_raw_set(
    const std::string& feature_name,
    const std::vector<std::uint8_t>& buffer,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureRawSet;
  auto request = make_feature_request<ServiceT>(feature_name, feature_module);
  request->buffer = buffer;
  return call_checked<ServiceT>(*feature_raw_set_client_, std::move(request))
      .transform([](const auto&) {});
}

Expected<std::int64_t> VimbaXCameraGateway::feature_raw_info_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureRawInfoGet;
  return call_checked<ServiceT>(
             *feature_raw_info_get_client_,
             make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->max_length; });
}

}  // namespace venimapping::camera
