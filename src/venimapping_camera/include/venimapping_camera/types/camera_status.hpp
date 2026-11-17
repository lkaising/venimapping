// -----------------------------------------------------------------------------
//  Filename: camera_status.hpp
//
//  Purpose:  Defines the camera status reported by the driver.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace venimapping::camera {

// The trigger configuration under one trigger selector.
//
// Upstream: vimbax_camera_msgs/msg/TriggerInfo.
struct TriggerInfo {
  std::string selector;
  std::string mode;
  std::string source;
};

// The camera's identity and its acquisition state at the moment of the query.
//
// Upstream: the response of vimbax_camera_msgs/srv/Status, in the same field
// order.
struct CameraStatus {
  std::string display_name;
  std::string model_name;
  std::string device_firmware_version;
  std::string device_id;
  std::string device_user_id;
  std::string device_serial_number;
  std::string interface_id;
  std::string transport_layer_id;
  bool streaming;
  std::uint32_t width;
  std::uint32_t height;
  double frame_rate;
  std::string pixel_format;
  std::vector<TriggerInfo> trigger_info;  // one entry per available trigger selector
  // Empty when the camera reports no such address, as a camera that is not
  // GigE does. Upstream sends an empty string in that case.
  std::optional<std::string> ip_address;
  std::optional<std::string> mac_address;
};

}  // namespace venimapping::camera
