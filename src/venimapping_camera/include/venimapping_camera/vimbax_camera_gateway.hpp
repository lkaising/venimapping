// -----------------------------------------------------------------------------
//  Filename: vimbax_camera_gateway.hpp
//
//  Purpose:  Declares the concrete ROS 2 camera gateway backed by Vimba X driver services.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "rclcpp/client.hpp"
#include "rclcpp/context.hpp"
#include "rclcpp/node.hpp"
#include "vimbax_camera_msgs/srv/connection_status.hpp"
#include "vimbax_camera_msgs/srv/feature_access_mode_get.hpp"
#include "vimbax_camera_msgs/srv/feature_bool_get.hpp"
#include "vimbax_camera_msgs/srv/feature_bool_set.hpp"
#include "vimbax_camera_msgs/srv/feature_command_is_done.hpp"
#include "vimbax_camera_msgs/srv/feature_command_run.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_as_int_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_as_string_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_set.hpp"
#include "vimbax_camera_msgs/srv/feature_float_get.hpp"
#include "vimbax_camera_msgs/srv/feature_float_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_float_set.hpp"
#include "vimbax_camera_msgs/srv/feature_info_query.hpp"
#include "vimbax_camera_msgs/srv/feature_int_get.hpp"
#include "vimbax_camera_msgs/srv/feature_int_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_int_set.hpp"
#include "vimbax_camera_msgs/srv/feature_raw_get.hpp"
#include "vimbax_camera_msgs/srv/feature_raw_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_raw_set.hpp"
#include "vimbax_camera_msgs/srv/feature_string_get.hpp"
#include "vimbax_camera_msgs/srv/feature_string_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_string_set.hpp"
#include "vimbax_camera_msgs/srv/features_list_get.hpp"
#include "vimbax_camera_msgs/srv/settings_load_save.hpp"
#include "vimbax_camera_msgs/srv/status.hpp"
#include "vimbax_camera_msgs/srv/stream_start_stop.hpp"

#include "venimapping_camera/camera_gateway.hpp"

namespace venimapping::camera {

// Calls block and must come from the thread given to bind_to_current_thread(),
// which must not spin the node (under a single-threaded executor every call
// would time out). The thread check catches misuse; it is not synchronization.
//
// A setter that times out may still have been applied; read back to be sure.
//
// The driver answers an unknown module with error -7, and any call but
// connection_status_get() with -3 while it holds no camera.
class VimbaXCameraGateway final : public CameraGateway {
 public:
  // node must outlive the gateway. timeout bounds each whole call, including
  // the wait for the service. Success does not mean the services are up or a
  // camera is connected.
  [[nodiscard]] static Expected<std::unique_ptr<VimbaXCameraGateway>> create(
      rclcpp::Node& node,
      const std::string& camera_namespace,
      std::chrono::milliseconds timeout);

  // Call once, from the worker thread, before any other call.
  [[nodiscard]] Expected<void> bind_to_current_thread();

  // True means only that the driver currently holds a camera object.
  [[nodiscard]] Expected<bool> connection_status_get() override;

  // Leaves TriggerSelector on its last value. Fields the camera lacks hold the
  // driver's placeholders: "N/A", or 0.0 for frame_rate.
  [[nodiscard]] Expected<CameraStatus> camera_status_get() override;

  [[nodiscard]] Expected<void> stream_start() override;
  [[nodiscard]] Expected<void> stream_stop() override;

  [[nodiscard]] Expected<void> settings_save(const std::string& filename) override;
  [[nodiscard]] Expected<void> settings_load(const std::string& filename) override;

  [[nodiscard]] Expected<std::vector<std::string>> features_list_get(
      FeatureModule feature_module) override;

  [[nodiscard]] Expected<std::vector<FeatureInfo>> feature_info_query(
      const std::vector<std::string>& feature_names,
      FeatureModule feature_module) override;

  [[nodiscard]] Expected<FeatureAccessMode> feature_access_mode_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;

  [[nodiscard]] Expected<std::int64_t> feature_int_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<void> feature_int_set(
      const std::string& feature_name,
      std::int64_t value,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<FeatureIntInfo> feature_int_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;

  [[nodiscard]] Expected<double> feature_float_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<void> feature_float_set(
      const std::string& feature_name,
      double value,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<FeatureFloatInfo> feature_float_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;

  [[nodiscard]] Expected<std::string> feature_string_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<void> feature_string_set(
      const std::string& feature_name,
      const std::string& value,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<std::int64_t> feature_string_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;

  [[nodiscard]] Expected<bool> feature_bool_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<void> feature_bool_set(
      const std::string& feature_name,
      bool value,
      FeatureModule feature_module) override;

  [[nodiscard]] Expected<std::string> feature_enum_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<void> feature_enum_set(
      const std::string& feature_name,
      const std::string& value,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<FeatureEnumInfo> feature_enum_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<std::int64_t> feature_enum_as_int_get(
      const std::string& feature_name,
      const std::string& option,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<std::string> feature_enum_as_string_get(
      const std::string& feature_name,
      std::int64_t value,
      FeatureModule feature_module) override;

  // Takes at least ~100 ms. A gateway timeout below the driver's
  // command_feature_timeout (default 1 s) can leave the outcome unknown.
  [[nodiscard]] Expected<void> feature_command_run(
      const std::string& feature_name,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<bool> feature_command_is_done(
      const std::string& feature_name,
      FeatureModule feature_module) override;

  [[nodiscard]] Expected<std::vector<std::uint8_t>> feature_raw_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<void> feature_raw_set(
      const std::string& feature_name,
      const std::vector<std::uint8_t>& buffer,
      FeatureModule feature_module) override;
  [[nodiscard]] Expected<std::int64_t> feature_raw_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) override;

 private:
  template <typename Service>
  using Client = rclcpp::Client<Service>;

  template <typename Service>
  using ClientPtr = typename Client<Service>::SharedPtr;

  template <typename Service>
  using RequestPtr = typename Service::Request::SharedPtr;

  template <typename Service>
  using ResponsePtr = typename Service::Response::SharedPtr;

  VimbaXCameraGateway(rclcpp::Node& node,
                      const std::string& camera_namespace,
                      std::chrono::milliseconds timeout);

  template <typename Service>
  [[nodiscard]] Expected<ResponsePtr<Service>> call(Client<Service>& client,
                                                    RequestPtr<Service> request);

  template <typename Service>
  [[nodiscard]] Expected<ResponsePtr<Service>> call_checked(Client<Service>& client,
                                                            RequestPtr<Service> request);

  [[nodiscard]] Expected<void> check_callable_from_this_thread() const;

  std::chrono::milliseconds timeout_;
  std::atomic<std::thread::id> bound_thread_{std::thread::id{}};
  rclcpp::Context::SharedPtr context_;

  ClientPtr<vimbax_camera_msgs::srv::ConnectionStatus> connection_status_client_;
  ClientPtr<vimbax_camera_msgs::srv::Status> status_client_;
  ClientPtr<vimbax_camera_msgs::srv::StreamStartStop> stream_start_client_;
  ClientPtr<vimbax_camera_msgs::srv::StreamStartStop> stream_stop_client_;
  ClientPtr<vimbax_camera_msgs::srv::SettingsLoadSave> settings_save_client_;
  ClientPtr<vimbax_camera_msgs::srv::SettingsLoadSave> settings_load_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeaturesListGet> features_list_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureInfoQuery> feature_info_query_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureAccessModeGet> feature_access_mode_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureIntGet> feature_int_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureIntSet> feature_int_set_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureIntInfoGet> feature_int_info_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureFloatGet> feature_float_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureFloatSet> feature_float_set_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureFloatInfoGet> feature_float_info_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureStringGet> feature_string_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureStringSet> feature_string_set_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureStringInfoGet> feature_string_info_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureBoolGet> feature_bool_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureBoolSet> feature_bool_set_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureEnumGet> feature_enum_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureEnumSet> feature_enum_set_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureEnumInfoGet> feature_enum_info_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureEnumAsIntGet> feature_enum_as_int_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureEnumAsStringGet> feature_enum_as_string_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureCommandRun> feature_command_run_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureCommandIsDone> feature_command_is_done_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureRawGet> feature_raw_get_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureRawSet> feature_raw_set_client_;
  ClientPtr<vimbax_camera_msgs::srv::FeatureRawInfoGet> feature_raw_info_get_client_;
};

}  // namespace venimapping::camera
