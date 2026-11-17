// -----------------------------------------------------------------------------
//  Filename: feature_info.hpp
//
//  Purpose:  Defines the static description of a feature.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <string>

namespace venimapping::camera {

// The value type of a feature, which tells a caller which typed gateway calls
// apply to it.
//
// Upstream: the uint32 data_type of vimbax_camera_msgs/msg/FeatureInfo, which
// carries the Vimba X SDK's VmbFeatureDataType. The enumerator values are the
// SDK's codes.
enum class FeatureDataType : std::uint8_t {
  kUnknown = 0,
  kInt = 1,
  kFloat = 2,
  kEnum = 3,
  kString = 4,
  kBool = 5,
  kCommand = 6,
  kRaw = 7,
  kNone = 8,  // a feature that holds no data
};

// What a feature is, as opposed to its current value or access state.
//
// Upstream: vimbax_camera_msgs/msg/FeatureInfo, without its flags field.
// The driver fills those flags from the wrong SDK field, so they are left
// out; current access state comes from CameraGateway::feature_access_mode_get().
struct FeatureInfo {
  std::string name;
  std::string category;
  std::string display_name;
  std::string sfnc_namespace;
  std::string unit;
  FeatureDataType data_type;
  std::uint32_t polling_time;  // the SDK's predefined polling time for a volatile feature
};

}  // namespace venimapping::camera
