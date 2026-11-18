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

// Enumerator values are the Vimba X SDK's VmbFeatureDataType codes.
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

// Static flags; for current access use CameraGateway::feature_access_mode_get().
// Correct only from driver fork tag v1.0.1-beta1-venimapping.1 on.
struct FeatureFlags {
  bool none;
  bool read;
  bool write;
  bool is_volatile;   // the value can change without a write
  bool modify_write;  // a write can store a different value than the one sent
};

struct FeatureInfo {
  std::string name;
  std::string category;
  std::string display_name;
  std::string sfnc_namespace;
  std::string unit;
  FeatureDataType data_type;
  FeatureFlags flags;
  std::uint32_t polling_time;
};

}  // namespace venimapping::camera
