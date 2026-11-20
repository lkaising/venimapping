// -----------------------------------------------------------------------------
//  Filename: vimbax_camera_gateway.cpp
//
//  Purpose:  Implements the concrete ROS 2 camera gateway backed by Vimba X driver services.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "venimapping_camera/vimbax_camera_gateway.hpp"

#include "gateway_support/vimbax_response_conversion.hpp"
#include "gateway_support/vimbax_service_calls.hpp"

namespace venimapping::camera {

Expected<std::unique_ptr<VimbaXCameraGateway>> VimbaXCameraGateway::create(
    rclcpp::Node& node,
    const std::string& camera_namespace,
    std::chrono::milliseconds timeout)
{
  if (camera_namespace.empty()) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kConstructionFailed,
        "gateway construction failed: camera_namespace is empty"));
  }

  if (timeout <= std::chrono::milliseconds::zero()) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kConstructionFailed,
        std::format(
            "gateway construction failed: timeout is not positive ({} ms)",
            timeout.count())));
  }

  try {
    return std::unique_ptr<VimbaXCameraGateway>{
        new VimbaXCameraGateway{node, camera_namespace, timeout}};
  } catch (const std::exception& e) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kConstructionFailed,
        std::format("gateway construction failed: {}", e.what())));
  } catch (...) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kConstructionFailed,
        "gateway construction failed: unknown exception"));
  }
}

VimbaXCameraGateway::VimbaXCameraGateway(rclcpp::Node& node,
                                         const std::string& camera_namespace,
                                         std::chrono::milliseconds timeout)
    : timeout_{timeout},
      context_{node.get_node_base_interface()->get_context()},
      connection_status_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::ConnectionStatus>(
              node, camera_namespace, "connected")},
      status_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::Status>(
              node, camera_namespace, "status")},
      stream_start_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::StreamStartStop>(
              node, camera_namespace, "stream_start")},
      stream_stop_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::StreamStartStop>(
              node, camera_namespace, "stream_stop")},
      settings_save_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::SettingsLoadSave>(
              node, camera_namespace, "settings/save")},
      settings_load_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::SettingsLoadSave>(
              node, camera_namespace, "settings/load")},
      features_list_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeaturesListGet>(
              node, camera_namespace, "features/list_get")},
      feature_info_query_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureInfoQuery>(
              node, camera_namespace, "feature_info_query")},
      feature_access_mode_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureAccessModeGet>(
              node, camera_namespace, "features/access_mode_get")},
      feature_int_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureIntGet>(
              node, camera_namespace, "features/int_get")},
      feature_int_set_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureIntSet>(
              node, camera_namespace, "features/int_set")},
      feature_int_info_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureIntInfoGet>(
              node, camera_namespace, "features/int_info_get")},
      feature_float_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureFloatGet>(
              node, camera_namespace, "features/float_get")},
      feature_float_set_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureFloatSet>(
              node, camera_namespace, "features/float_set")},
      feature_float_info_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureFloatInfoGet>(
              node, camera_namespace, "features/float_info_get")},
      feature_string_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureStringGet>(
              node, camera_namespace, "features/string_get")},
      feature_string_set_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureStringSet>(
              node, camera_namespace, "features/string_set")},
      feature_string_info_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureStringInfoGet>(
              node, camera_namespace, "features/string_info_get")},
      feature_bool_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureBoolGet>(
              node, camera_namespace, "features/bool_get")},
      feature_bool_set_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureBoolSet>(
              node, camera_namespace, "features/bool_set")},
      feature_enum_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureEnumGet>(
              node, camera_namespace, "features/enum_get")},
      feature_enum_set_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureEnumSet>(
              node, camera_namespace, "features/enum_set")},
      feature_enum_info_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureEnumInfoGet>(
              node, camera_namespace, "features/enum_info_get")},
      feature_enum_as_int_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureEnumAsIntGet>(
              node, camera_namespace, "features/enum_as_int_get")},
      feature_enum_as_string_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureEnumAsStringGet>(
              node, camera_namespace, "features/enum_as_string_get")},
      feature_command_run_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureCommandRun>(
              node, camera_namespace, "features/command_run")},
      feature_command_is_done_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureCommandIsDone>(
              node, camera_namespace, "features/command_is_done")},
      feature_raw_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureRawGet>(
              node, camera_namespace, "features/raw_get")},
      feature_raw_set_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureRawSet>(
              node, camera_namespace, "features/raw_set")},
      feature_raw_info_get_client_{
          gateway_support::make_client<vimbax_camera_msgs::srv::FeatureRawInfoGet>(
              node, camera_namespace, "features/raw_info_get")}
{
}

Expected<void> VimbaXCameraGateway::bind_to_current_thread()
{
  std::thread::id unbound{};
  if (!bound_thread_.compare_exchange_strong(unbound, std::this_thread::get_id())) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kThreadContractViolation,
        "bind_to_current_thread() called more than once"));
  }

  return {};
}

Expected<void> VimbaXCameraGateway::check_callable_from_this_thread() const
{
  const std::thread::id bound = bound_thread_.load();
  const std::thread::id current = std::this_thread::get_id();

  if (bound == std::thread::id{}) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kThreadContractViolation,
        "gateway call before bind_to_current_thread()"));
  }

  if (bound != current) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kThreadContractViolation,
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

  const gateway_support::Deadline deadline = gateway_support::Clock::now() + timeout_;
  std::string service_name{"(unresolved service)"};

  try {
    service_name = client.get_service_name();

    auto service_check =
        gateway_support::wait_for_service(client, context_, deadline, service_name);
    if (!service_check) {
      return std::unexpected(std::move(service_check).error());
    }

    auto future = client.async_send_request(std::move(request));

    return gateway_support::wait_for_response<Service>(client, future, deadline, service_name);
  } catch (const std::exception& e) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kRosClientFailure,
        std::format("rclcpp client failure on {}: {}", service_name, e.what())));
  } catch (...) {
    return std::unexpected(gateway_support::gateway_error(
        gateway_support::GatewayDiagnostic::kRosClientFailure,
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
    return std::unexpected(gateway_support::driver_error(driver.code, driver.text));
  }

  return response;
}

Expected<bool> VimbaXCameraGateway::connection_status()
{
  using ServiceT = vimbax_camera_msgs::srv::ConnectionStatus;
  return call<ServiceT>(
             *connection_status_client_,
             std::make_shared<ServiceT::Request>())
      .transform([](const auto& response) { return response->connected; });
}

Expected<CameraStatus> VimbaXCameraGateway::camera_status()
{
  using ServiceT = vimbax_camera_msgs::srv::Status;
  return call_checked<ServiceT>(
             *status_client_,
             std::make_shared<ServiceT::Request>())
      .transform([](const auto& response) {
        return gateway_support::to_camera_status(*response);
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

Expected<FeatureList> VimbaXCameraGateway::feature_list_get(
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeaturesListGet;
  return call_checked<ServiceT>(
             *features_list_get_client_,
             gateway_support::make_module_request<ServiceT>(feature_module))
      .transform([](const auto& response) {
        return gateway_support::to_feature_list(*response);
      });
}

Expected<FeatureInfoList> VimbaXCameraGateway::feature_info_list_get(
    const FeatureList& feature_list,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureInfoQuery;
  auto request = gateway_support::make_module_request<ServiceT>(feature_module);
  request->feature_names = feature_list.names;
  return call_checked<ServiceT>(*feature_info_query_client_, std::move(request))
      .transform([](const auto& response) {
        return gateway_support::to_feature_info_list(*response);
      });
}

Expected<FeatureAccessMode> VimbaXCameraGateway::feature_access_mode_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureAccessModeGet;
  return call_checked<ServiceT>(
             *feature_access_mode_get_client_,
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return gateway_support::to_feature_access_mode(*response);
      });
}

Expected<std::int64_t> VimbaXCameraGateway::feature_int_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureIntGet;
  return call_checked<ServiceT>(
             *feature_int_get_client_,
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->value; });
}

Expected<void> VimbaXCameraGateway::feature_int_set(
    const std::string& feature_name,
    std::int64_t value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureIntSet;
  auto request = gateway_support::make_feature_request<ServiceT>(feature_name, feature_module);
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
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return gateway_support::to_feature_int_info(*response);
      });
}

Expected<double> VimbaXCameraGateway::feature_float_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatGet;
  return call_checked<ServiceT>(
             *feature_float_get_client_,
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->value; });
}

Expected<void> VimbaXCameraGateway::feature_float_set(
    const std::string& feature_name,
    double value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureFloatSet;
  auto request = gateway_support::make_feature_request<ServiceT>(feature_name, feature_module);
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
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return gateway_support::to_feature_float_info(*response);
      });
}

Expected<std::string> VimbaXCameraGateway::feature_string_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureStringGet;
  return call_checked<ServiceT>(
             *feature_string_get_client_,
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return std::move(response->value); });
}

Expected<void> VimbaXCameraGateway::feature_string_set(
    const std::string& feature_name,
    const std::string& value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureStringSet;
  auto request = gateway_support::make_feature_request<ServiceT>(feature_name, feature_module);
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
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->max_length; });
}

Expected<bool> VimbaXCameraGateway::feature_bool_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureBoolGet;
  return call_checked<ServiceT>(
             *feature_bool_get_client_,
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->value; });
}

Expected<void> VimbaXCameraGateway::feature_bool_set(
    const std::string& feature_name,
    bool value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureBoolSet;
  auto request = gateway_support::make_feature_request<ServiceT>(feature_name, feature_module);
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
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return std::move(response->value); });
}

Expected<void> VimbaXCameraGateway::feature_enum_set(
    const std::string& feature_name,
    const std::string& value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumSet;
  auto request = gateway_support::make_feature_request<ServiceT>(feature_name, feature_module);
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
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return gateway_support::to_feature_enum_info(*response);
      });
}

Expected<std::int64_t> VimbaXCameraGateway::feature_enum_as_int_get(
    const std::string& feature_name,
    const std::string& option,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureEnumAsIntGet;
  auto request = gateway_support::make_feature_request<ServiceT>(feature_name, feature_module);
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
  auto request = gateway_support::make_feature_request<ServiceT>(feature_name, feature_module);
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
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto&) {});
}

Expected<bool> VimbaXCameraGateway::feature_command_is_done(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureCommandIsDone;
  return call_checked<ServiceT>(
             *feature_command_is_done_client_,
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->is_done; });
}

Expected<FeatureRawValue> VimbaXCameraGateway::feature_raw_get(
    const std::string& feature_name,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureRawGet;
  return call_checked<ServiceT>(
             *feature_raw_get_client_,
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) {
        return gateway_support::to_feature_raw_value(*response);
      });
}

Expected<void> VimbaXCameraGateway::feature_raw_set(
    const std::string& feature_name,
    const FeatureRawValue& value,
    FeatureModule feature_module)
{
  using ServiceT = vimbax_camera_msgs::srv::FeatureRawSet;
  auto request = gateway_support::make_feature_request<ServiceT>(feature_name, feature_module);
  request->buffer = value.bytes;
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
             gateway_support::make_feature_request<ServiceT>(feature_name, feature_module))
      .transform([](const auto& response) { return response->max_length; });
}

}  // namespace venimapping::camera
