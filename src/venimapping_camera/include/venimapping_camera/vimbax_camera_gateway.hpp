// -----------------------------------------------------------------------------
//  Filename: feature_gateway.hpp
//
//  Purpose:  Declares the concrete ROS 2 implementation of FeatureAccess over
//            the vimbax_ros2_driver services.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <chrono>
#include <memory>
#include <optional>
#include <string>
#include <thread>

#include "rclcpp/client.hpp"
#include "rclcpp/node.hpp"
#include "vimbax_camera_msgs/srv/connection_status.hpp"
#include "vimbax_camera_msgs/srv/feature_access_mode_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_set.hpp"
#include "vimbax_camera_msgs/srv/feature_float_get.hpp"
#include "vimbax_camera_msgs/srv/feature_float_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_float_set.hpp"
#include "vimbax_camera_msgs/srv/feature_info_query.hpp"
#include "vimbax_camera_msgs/srv/status.hpp"

#include "venimapping_camera/expected.hpp"
#include "venimapping_camera/feature_access.hpp"

namespace venimapping::camera {

// Implements FeatureAccess through vimbax_ros2_driver services. Service names,
// request assembly, timeout handling, rclcpp exceptions, and driver-error
// passthrough are hidden here; no ROS request or response type escapes through
// the public API.
//
// Threading (Section 11): the methods are synchronous and block on service
// futures, so they must run on a worker thread while a ROS executor spins the
// node independently. Calls are serialized on that one thread; concurrent use
// from multiple threads is unsupported.
class FeatureGateway final : public FeatureAccess {
 public:
  // The only supported construction path: ROS client creation can throw, and
  // the factory converts that into an Error rather than an exception.
  //
  // node is a non-owning, mandatory reference. The gateway does not own the
  // node, the ROS executor, or the worker thread; the caller shall ensure the
  // node and ROS context outlive the gateway's use of its clients.
  // camera_namespace is taken by value because the gateway stores it.
  //
  // Returns a kErrConstruction diagnostic (origin = gateway) when
  // camera_namespace is empty, when timeout is not positive, or when client
  // construction throws (exception text preserved).
  //
  // Success means every required service client object was constructed. It
  // does not mean the services are currently available or that a camera is
  // connected; availability is checked per call.
  static Expected<std::unique_ptr<FeatureGateway>> Create(
      rclcpp::Node& node,
      std::string camera_namespace,
      std::chrono::milliseconds timeout);

  // Not copyable or movable. Assumption, not specified: every member is
  // copyable, so without this the implicit copy would hand a second gateway
  // the same live service clients.
  FeatureGateway(const FeatureGateway&) = delete;
  FeatureGateway& operator=(const FeatureGateway&) = delete;
  FeatureGateway(FeatureGateway&&) = delete;
  FeatureGateway& operator=(FeatureGateway&&) = delete;

  // Records the calling thread as the designated worker thread. A later call
  // re-binds (last call wins). Binding is not synchronized and shall only be
  // called while no gateway calls are in flight; Stage 1 binds exactly once,
  // from the worker thread, before the first call. Enforcement is a debug
  // assertion, not a runtime synchronization mechanism (Section 11.2).
  void BindCallingThread();

  Expected<double> GetFloat(const std::string& name) override;
  Expected<void> SetFloat(const std::string& name, double value) override;
  Expected<FloatInfo> GetFloatInfo(const std::string& name) override;

  Expected<AccessMode> GetAccessMode(const std::string& name) override;

  // Answers whether the camera exposes the named feature.
  //
  // Contract (Section 9.6). The driver reports an unknown feature and an
  // unavailable camera with byte-identical wire errors, so existence is
  // answered only when it can be answered truthfully:
  //
  //   - false is returned only when a camera the driver reported present
  //     immediately beforehand affirmatively fails the query with
  //     VmbErrorNotFound (-3);
  //   - camera unavailable at the connection pre-check -> kErrCameraUnavailable
  //     (origin = gateway);
  //   - any other nonzero driver code -> verbatim driver passthrough
  //     (origin = driver), exactly as in every other method;
  //   - success with an empty feature_info array -> kErrDriverContract
  //     (origin = gateway); that shape violates the driver's verified
  //     all-or-nothing query behavior, so the gateway fails loudly rather than
  //     fabricate an answer.
  //
  // Residual race, accepted and documented (Section 18.4): the pre-check
  // cannot cover a disconnect occurring between itself and the query. Within
  // that one-round-trip window the query reports the same
  // {-3, "VmbErrorNotFound"} the driver uses for an unknown feature, and this
  // method returns false. The two conditions are indistinguishable on the
  // wire, so the window is irreducible at this layer.
  //
  // Cost: two service calls per invocation (the pre-check and the query).
  Expected<bool> FeatureExists(const std::string& name) override;

  Expected<std::string> GetEnum(const std::string& name) override;
  Expected<void> SetEnum(
      const std::string& name,
      const std::string& option) override;
  Expected<EnumInfo> GetEnumInfo(const std::string& name) override;

  Expected<CameraStatus> GetStatus() override;
  Expected<bool> Connected() override;

 private:
  // Constructs the service clients; client construction can throw, which
  // Create() catches and converts.
  FeatureGateway(
      rclcpp::Node& node,
      std::string camera_namespace,
      std::chrono::milliseconds timeout);

  // The centralized call path shared by every wrapped operation, implementing
  // steps 1-9 of Section 9.6 only: the debug thread assertion, the service
  // availability check and wait, async_send_request(), the timed wait on the
  // returned future, removal of the pending request on timeout, and conversion
  // of rclcpp client exceptions into a kErrRclcpp diagnostic.
  //
  // It returns the transported response as received and deliberately does NOT
  // invoke gateway::CheckError(). The driver-error check stays in each public
  // method, which is what lets Connected() -- whose response has no error
  // member -- share this same path. CheckError() shall not be folded in here.
  //
  // Defined in feature_gateway.cpp; that is valid only while every
  // instantiation lives in that translation unit. If a second translation unit
  // ever needs Call(), the definition moves rather than being duplicated.
  template <typename Service>
  Expected<typename Service::Response::SharedPtr> Call(
      rclcpp::Client<Service>& client,
      typename Service::Request::SharedPtr request);

  // Debug-asserts that the caller is the bound worker thread. Before binding,
  // calls are unrestricted (Section 11.2).
  void AssertBoundThread() const;

  rclcpp::Node* node_;  // non-owning; the reference given to Create()
  std::string camera_namespace_;
  std::chrono::milliseconds timeout_;
  std::optional<std::thread::id> bound_thread_;

  rclcpp::Client<vimbax_camera_msgs::srv::ConnectionStatus>::SharedPtr
      connected_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::Status>::SharedPtr status_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureInfoQuery>::SharedPtr
      feature_info_query_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureAccessModeGet>::SharedPtr
      access_mode_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureFloatGet>::SharedPtr
      float_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureFloatSet>::SharedPtr
      float_set_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureFloatInfoGet>::SharedPtr
      float_info_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureEnumGet>::SharedPtr
      enum_get_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureEnumSet>::SharedPtr
      enum_set_client_;
  rclcpp::Client<vimbax_camera_msgs::srv::FeatureEnumInfoGet>::SharedPtr
      enum_info_get_client_;
};

}  // namespace venimapping::camera
