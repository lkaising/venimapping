// -----------------------------------------------------------------------------
//  Filename: vimbax_response_conversion.cpp
//
//  Purpose:  Converts Vimba X service responses to gateway types.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "vimbax_response_conversion.hpp"

#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace venimapping::camera::gateway_support {

CameraStatus to_camera_status(vimbax_camera_msgs::srv::Status::Response&& response)
{
  std::vector<TriggerInfo> triggers;
  triggers.reserve(response.trigger_info.size());
  for (auto& trigger : response.trigger_info) {
    triggers.push_back(TriggerInfo{
        .selector = std::move(trigger.selector),
        .mode = std::move(trigger.mode),
        .source = std::move(trigger.source),
    });
  }

  const auto optional_address = [](std::string&& address) -> std::optional<std::string> {
    if (address.empty()) {
      return std::nullopt;
    }
    return std::move(address);
  };

  return CameraStatus{
      .display_name = std::move(response.display_name),
      .model_name = std::move(response.model_name),
      .device_firmware_version = std::move(response.device_firmware_version),
      .device_id = std::move(response.device_id),
      .device_user_id = std::move(response.device_user_id),
      .device_serial_number = std::move(response.device_serial_number),
      .interface_id = std::move(response.interface_id),
      .transport_layer_id = std::move(response.transport_layer_id),
      .streaming = response.streaming,
      .width = response.width,
      .height = response.height,
      .frame_rate = response.frame_rate,
      .pixel_format = std::move(response.pixel_format),
      .trigger_info = std::move(triggers),
      .ip_address = optional_address(std::move(response.ip_address)),
      .mac_address = optional_address(std::move(response.mac_address)),
  };
}

std::vector<FeatureInfo> to_feature_info_list(
    vimbax_camera_msgs::srv::FeatureInfoQuery::Response&& response)
{
  std::vector<FeatureInfo> features;
  features.reserve(response.feature_info.size());
  for (auto& feature : response.feature_info) {
    // The SDK codes are contiguous through kNone.
    const auto code = feature.data_type;
    const auto data_type = code <= std::to_underlying(FeatureDataType::kNone)
        ? static_cast<FeatureDataType>(code)
        : FeatureDataType::kUnknown;

    features.push_back(FeatureInfo{
        .name = std::move(feature.name),
        .category = std::move(feature.category),
        .display_name = std::move(feature.display_name),
        .sfnc_namespace = std::move(feature.sfnc_namespace),
        .unit = std::move(feature.unit),
        .data_type = data_type,
        .flags = FeatureFlags{
            .none = feature.flags.flag_none,
            .read = feature.flags.flag_read,
            .write = feature.flags.flag_write,
            .is_volatile = feature.flags.flag_volatile,
            .modify_write = feature.flags.flag_modify_write,
        },
        .polling_time = feature.polling_time,
    });
  }
  return features;
}

}  // namespace venimapping::camera::gateway_support
