// -----------------------------------------------------------------------------
//  Filename: vimbax_response_conversion.cpp
//
//  Purpose:  Converts Vimba X service responses to gateway types.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include "vimbax_response_conversion.hpp"

#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace venimapping::camera::gateway_support {

namespace {

[[nodiscard]] std::optional<std::string> to_optional_address(std::string& address)
{
  if (address.empty()) {
    return std::nullopt;
  }
  return std::move(address);
}

[[nodiscard]] constexpr FeatureDataType to_feature_data_type(std::uint32_t code) noexcept
{
  if (code > std::to_underlying(FeatureDataType::kNone)) {
    return FeatureDataType::kUnknown;
  }
  return static_cast<FeatureDataType>(code);
}

}  // namespace

CameraStatus to_camera_status(vimbax_srv::Status::Response& response)
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
      .ip_address = to_optional_address(response.ip_address),
      .mac_address = to_optional_address(response.mac_address),
  };
}

FeatureList to_feature_list(vimbax_srv::FeaturesListGet::Response& response)
{
  return FeatureList{
      .names = std::move(response.feature_list),
  };
}

FeatureInfoList to_feature_info_list(vimbax_srv::FeatureInfoQuery::Response& response)
{
  std::vector<FeatureInfo> features;
  features.reserve(response.feature_info.size());
  for (auto& feature : response.feature_info) {
    features.push_back(FeatureInfo{
        .name = std::move(feature.name),
        .category = std::move(feature.category),
        .display_name = std::move(feature.display_name),
        .sfnc_namespace = std::move(feature.sfnc_namespace),
        .unit = std::move(feature.unit),
        .data_type = to_feature_data_type(feature.data_type),
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
  return FeatureInfoList{.features = std::move(features)};
}

FeatureAccessMode to_feature_access_mode(const vimbax_srv::FeatureAccessModeGet::Response& response)
{
  return FeatureAccessMode{
      .readable = response.is_readable,
      .writable = response.is_writeable,
  };
}

FeatureIntInfo to_feature_int_info(const vimbax_srv::FeatureIntInfoGet::Response& response)
{
  return FeatureIntInfo{
      .min = response.min,
      .max = response.max,
      .inc = response.inc,
  };
}

FeatureFloatInfo to_feature_float_info(const vimbax_srv::FeatureFloatInfoGet::Response& response)
{
  return FeatureFloatInfo{
      .min = response.min,
      .max = response.max,
      .inc = response.inc,
      .inc_available = response.inc_available,
  };
}

FeatureEnumInfo to_feature_enum_info(vimbax_srv::FeatureEnumInfoGet::Response& response)
{
  return FeatureEnumInfo{
      .possible_values = std::move(response.possible_values),
      .available_values = std::move(response.available_values),
  };
}

FeatureRawValue to_feature_raw_value(vimbax_srv::FeatureRawGet::Response& response)
{
  return FeatureRawValue{
      .bytes = std::move(response.buffer),
  };
}

}  // namespace venimapping::camera::gateway_support
