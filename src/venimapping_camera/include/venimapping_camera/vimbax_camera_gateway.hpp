// -----------------------------------------------------------------------------
//  Filename: vimbax_camera_gateway.hpp
//
//  Purpose:  Declares the concrete ROS 2 implementation of CameraGateway over
//            the vimbax_ros2_driver services.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include "rclcpp/client.hpp"
#include "rclcpp/context.hpp"
#include "rclcpp/node.hpp"
#include "vimbax_camera_msgs/srv/connection_status.hpp"
#include "vimbax_camera_msgs/srv/feature_access_mode_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_set.hpp"
#include "vimbax_camera_msgs/srv/feature_float_get.hpp"
#include "vimbax_camera_msgs/srv/feature_float_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_float_set.hpp"
#include "vimbax_camera_msgs/srv/features_list_get.hpp"
#include "vimbax_camera_msgs/srv/status.hpp"

#include "venimapping_camera/camera_gateway.hpp"
#include "venimapping_camera/expected.hpp"

namespace venimapping::camera {

// Implements CameraGateway through vimbax_ros2_driver services. Service names,
// request assembly, timeout handling, rclcpp exceptions, and driver-error
// passthrough are hidden here; no ROS request or response type escapes through
// the public API.
//
// The methods are synchronous and block on service futures. They are designed
// to run on a dedicated worker thread that is not an executor thread, while a
// ROS executor spins the node independently. If the bound thread is a
// single-threaded executor's callback thread, a call from it prevents that
// executor from processing the response and fails with a timeout error rather
// than blocking indefinitely; use from executor callbacks under any other
// executor configuration is unsupported. Calls are serialized on the bound
// thread, and a call from any other thread -- or before binding -- fails with
// a gateway error before any ROS interaction. That checking is misuse
// detection, not thread synchronization; concurrent use from multiple threads
// is unsupported.
//
// A setter that fails with a timeout does not establish whether the camera
// applied the requested value; a caller that needs to know shall read the
// feature back.
class VimbaXCameraGateway final : public CameraGateway {
 public:
  // The only supported construction path: ROS client creation can throw, and
  // the factory converts that into an Error rather than an exception.
  //
  // node is a non-owning, mandatory reference. The gateway does not own the
  // node, the ROS executor, or the worker thread; the caller shall ensure the
  // node and ROS context outlive the gateway's use of its clients.
  //
  // timeout bounds each call as a whole: one deadline, started when the call
  // begins, is shared by the service-availability wait and the response wait.
  // Thread-scheduling overhead can stretch it slightly, so it is not a hard
  // limit.
  //
  // Fails with domain() == ErrorDomain::kGateway when camera_namespace is empty,
  // when timeout is not positive, or when client construction throws (exception
  // text preserved).
  //
  // Success means every service client object was constructed. It does not mean
  // the services are currently available or that a camera is connected;
  // availability is checked per call.
  [[nodiscard]] static Expected<std::unique_ptr<VimbaXCameraGateway>> create(
      rclcpp::Node& node,
      const std::string& camera_namespace,
      std::chrono::milliseconds timeout);

  // Records the calling thread as the designated worker thread. It shall be
  // called exactly once, from that thread, before the first gateway call, and
  // every later call shall come from that same thread. Violations are reported
  // as a gateway error: a second bind fails, and gateway calls made before
  // binding or from another thread fail without touching ROS.
  [[nodiscard]] Expected<void> bind_to_current_thread();

  [[nodiscard]] Expected<double> feature_float_get(const std::string& name) override;
  [[nodiscard]] Expected<void> feature_float_set(const std::string& name, double value) override;
  [[nodiscard]] Expected<FloatInfo> feature_float_info_get(const std::string& name) override;

  [[nodiscard]] Expected<std::string> feature_enum_get(const std::string& name) override;
  [[nodiscard]] Expected<void> feature_enum_set(const std::string& name,
                                                const std::string& value) override;
  [[nodiscard]] Expected<EnumInfo> feature_enum_info_get(const std::string& name) override;

  [[nodiscard]] Expected<AccessMode> feature_access_mode_get(const std::string& name) override;

  // The Vimba X driver serves this list from a per-module cache built when it
  // opens the camera, so the result is a snapshot refreshed on reopen after a
  // reconnect rather than a live query.
  [[nodiscard]] Expected<std::vector<std::string>> features_list_get() override;

  [[nodiscard]] Expected<CameraStatus> camera_status_get() override;
  [[nodiscard]] Expected<bool> connection_status_get() override;

 private:
  VimbaXCameraGateway(rclcpp::Node& node,
                      const std::string& camera_namespace,
                      std::chrono::milliseconds timeout);

  template <typename Service>
  [[nodiscard]] Expected<typename Service::Response::SharedPtr> call(
      rclcpp::Client<Service>& client,
      typename Service::Request::SharedPtr request);

  // connection_status_get() alone stays on call(), because its response has no
  // error member.
  template <typename Service>
  [[nodiscard]] Expected<typename Service::Response::SharedPtr> call_checked(
      rclcpp::Client<Service>& client,
      typename Service::Request::SharedPtr request);

  [[nodiscard]] Expected<void> check_callable_from_this_thread() const;

  std::chrono::milliseconds timeout_;
  // Default-constructed thread::id is the unbound sentinel: the standard
  // guarantees it never equals the id of a running thread.
  std::atomic<std::thread::id> bound_thread_{std::thread::id{}};
  rclcpp::Context::SharedPtr context_;

  rclcpp::Client<vimbax_camera_msgs::srv::ConnectionStatus>::SharedPtr
      connection_status_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::Status>::SharedPtr status_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeaturesListGet>::SharedPtr
      features_list_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureAccessModeGet>::SharedPtr
      feature_access_mode_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureFloatGet>::SharedPtr
      feature_float_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureFloatSet>::SharedPtr
      feature_float_set_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureFloatInfoGet>::SharedPtr
      feature_float_info_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureEnumGet>::SharedPtr
      feature_enum_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureEnumSet>::SharedPtr
      feature_enum_set_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureEnumInfoGet>::SharedPtr
      feature_enum_info_get_client_;
};

}  // namespace venimapping::camera
