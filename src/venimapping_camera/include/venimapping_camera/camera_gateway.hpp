// -----------------------------------------------------------------------------
//  Filename: camera_gateway.hpp
//
//  Purpose:  Declares the ROS-independent camera gateway contract.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "venimapping_camera/types/camera_status.hpp"
#include "venimapping_camera/types/expected.hpp"
#include "venimapping_camera/types/feature_access_mode.hpp"
#include "venimapping_camera/types/feature_enum_info.hpp"
#include "venimapping_camera/types/feature_float_info.hpp"
#include "venimapping_camera/types/feature_int_info.hpp"
#include "venimapping_camera/types/feature_module.hpp"

namespace venimapping::camera {

// The primitive camera operations available to VeniMapping layers.
//
// Implementations report metadata and current state; they do not decide how the
// application responds. Clamping, fallback selection, retry, and configuration
// ordering belong to future layers. A failure the driver reports is returned
// verbatim, neither translated nor classified.
//
// Every feature call names the module it addresses, and there is no default
// module: a feature of one module is unknown to the others. The typed calls do
// not check that the feature has that type; a mismatch is the driver's to
// report.
//
// Setters request a value and report only success or failure: no automatic
// readback, and no local validation against feature metadata.
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

  // Answers connectivity as a value: false is a successful negative answer. It
  // reports the driver's connection state and is not a precondition for any
  // other call.
  [[nodiscard]] virtual Expected<bool> connection_status_get() = 0;

  [[nodiscard]] virtual Expected<CameraStatus> camera_status_get() = 0;

  // Start and stop image acquisition. The images themselves are not part of
  // this contract.
  [[nodiscard]] virtual Expected<void> stream_start() = 0;
  [[nodiscard]] virtual Expected<void> stream_stop() = 0;

  // Save the camera's feature values to a file, or load them from one.
  // filename is a path on the machine that runs the driver, which need not be
  // the machine that runs the gateway.
  [[nodiscard]] virtual Expected<void> settings_save(const std::string& filename) = 0;
  [[nodiscard]] virtual Expected<void> settings_load(const std::string& filename) = 0;

  // Returns the names of the features the module defines. This is not an
  // availability check: a listed name may be currently unreadable or
  // unwritable, and current access state comes from feature_access_mode_get().
  // An empty list on success is a valid answer, not an error.
  [[nodiscard]] virtual Expected<std::vector<std::string>> features_list_get(
      FeatureModule feature_module) = 0;

  [[nodiscard]] virtual Expected<FeatureAccessMode> feature_access_mode_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;

  [[nodiscard]] virtual Expected<std::int64_t> feature_int_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<void> feature_int_set(
      const std::string& feature_name,
      std::int64_t value,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<FeatureIntInfo> feature_int_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;

  [[nodiscard]] virtual Expected<double> feature_float_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<void> feature_float_set(
      const std::string& feature_name,
      double value,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<FeatureFloatInfo> feature_float_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;

  [[nodiscard]] virtual Expected<std::string> feature_string_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<void> feature_string_set(
      const std::string& feature_name,
      const std::string& value,
      FeatureModule feature_module) = 0;
  // Returns the maximum length of the feature's value.
  [[nodiscard]] virtual Expected<std::int64_t> feature_string_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;

  [[nodiscard]] virtual Expected<bool> feature_bool_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<void> feature_bool_set(
      const std::string& feature_name,
      bool value,
      FeatureModule feature_module) = 0;

  // An enum feature's value is the name of the selected option.
  [[nodiscard]] virtual Expected<std::string> feature_enum_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<void> feature_enum_set(
      const std::string& feature_name,
      const std::string& value,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<FeatureEnumInfo> feature_enum_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;

 protected:
  CameraGateway() = default;
};

}  // namespace venimapping::camera
