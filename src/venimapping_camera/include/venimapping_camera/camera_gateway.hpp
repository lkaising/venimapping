// -----------------------------------------------------------------------------
//  Filename: camera_gateway.hpp
//
//  Purpose:  Declares the ROS-independent camera gateway contract.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <string>
#include <vector>

#include "venimapping_camera/types/camera_status.hpp"
#include "venimapping_camera/types/expected.hpp"
#include "venimapping_camera/types/feature_access_mode.hpp"
#include "venimapping_camera/types/feature_enum_info.hpp"
#include "venimapping_camera/types/feature_float_info.hpp"

namespace venimapping::camera {

// The primitive camera operations available to VeniMapping layers.
//
// Implementations report metadata and current state; they do not decide how the
// application responds. Clamping, fallback selection, retry, and configuration
// ordering belong to future layers. A failure the driver reports is returned
// verbatim, neither translated nor classified.
//
// Methods are intentionally non-const: they perform I/O against external
// mutable state, and concrete implementations mutate internal client state.
class CameraGateway {
 public:
  CameraGateway(const CameraGateway&) = delete;
  CameraGateway(CameraGateway&&) = delete;
  CameraGateway& operator=(const CameraGateway&) = delete;
  CameraGateway& operator=(CameraGateway&&) = delete;
  virtual ~CameraGateway() = default;

  [[nodiscard]] virtual Expected<double> feature_float_get(const std::string& name) = 0;

  // Setters request a value and report only success or failure: no automatic
  // readback, and no local validation against feature metadata.
  [[nodiscard]] virtual Expected<void> feature_float_set(const std::string& name, double value) = 0;

  [[nodiscard]] virtual Expected<FeatureFloatInfo> feature_float_info_get(const std::string& name) = 0;

  [[nodiscard]] virtual Expected<std::string> feature_enum_get(const std::string& name) = 0;
  [[nodiscard]] virtual Expected<void> feature_enum_set(const std::string& name,
                                                        const std::string& value) = 0;
  [[nodiscard]] virtual Expected<FeatureEnumInfo> feature_enum_info_get(const std::string& name) = 0;

  [[nodiscard]] virtual Expected<FeatureAccessMode> feature_access_mode_get(const std::string& name) = 0;

  // Returns the names of the features the camera defines. This is not an
  // availability check: a listed name may be currently unreadable or
  // unwritable, and current access state comes from feature_access_mode_get().
  // An empty list on success is a valid answer, not an error.
  [[nodiscard]] virtual Expected<std::vector<std::string>> features_list_get() = 0;

  [[nodiscard]] virtual Expected<CameraStatus> camera_status_get() = 0;

  // Answers connectivity as a value: false is a successful negative answer. It
  // reports the driver's connection state and is not a precondition for any
  // other call.
  [[nodiscard]] virtual Expected<bool> connection_status_get() = 0;

 protected:
  CameraGateway() = default;
};

}  // namespace venimapping::camera
