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
#include "venimapping_camera/types/feature_info.hpp"
#include "venimapping_camera/types/feature_int_info.hpp"
#include "venimapping_camera/types/feature_module.hpp"

namespace venimapping::camera {

// Primitive camera operations with no policy: no clamping, fallback, retry,
// readback, or validation (not even of a feature's type). Driver failures are
// returned verbatim.
class CameraGateway {
 public:
  CameraGateway(const CameraGateway&) = delete;
  CameraGateway(CameraGateway&&) = delete;
  CameraGateway& operator=(const CameraGateway&) = delete;
  CameraGateway& operator=(CameraGateway&&) = delete;
  virtual ~CameraGateway() = default;

  [[nodiscard]] virtual Expected<bool> connection_status_get() = 0;

  [[nodiscard]] virtual Expected<CameraStatus> camera_status_get() = 0;

  [[nodiscard]] virtual Expected<void> stream_start() = 0;
  [[nodiscard]] virtual Expected<void> stream_stop() = 0;

  // filename is a path on the driver's machine, which may not be this one.
  [[nodiscard]] virtual Expected<void> settings_save(const std::string& filename) = 0;
  [[nodiscard]] virtual Expected<void> settings_load(const std::string& filename) = 0;

  // Lists features whether or not they are accessible right now.
  [[nodiscard]] virtual Expected<std::vector<std::string>> features_list_get(
      FeatureModule feature_module) = 0;

  // An empty feature_names means every feature; one unknown name fails the call.
  [[nodiscard]] virtual Expected<std::vector<FeatureInfo>> feature_info_query(
      const std::vector<std::string>& feature_names,
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
  // Maximum length of the value.
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

  [[nodiscard]] virtual Expected<std::int64_t> feature_enum_as_int_get(
      const std::string& feature_name,
      const std::string& option,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<std::string> feature_enum_as_string_get(
      const std::string& feature_name,
      std::int64_t value,
      FeatureModule feature_module) = 0;

  [[nodiscard]] virtual Expected<void> feature_command_run(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<bool> feature_command_is_done(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;

  [[nodiscard]] virtual Expected<std::vector<std::uint8_t>> feature_raw_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;
  [[nodiscard]] virtual Expected<void> feature_raw_set(
      const std::string& feature_name,
      const std::vector<std::uint8_t>& buffer,
      FeatureModule feature_module) = 0;
  // Maximum length of the value, in bytes.
  [[nodiscard]] virtual Expected<std::int64_t> feature_raw_info_get(
      const std::string& feature_name,
      FeatureModule feature_module) = 0;

 protected:
  CameraGateway() = default;
};

}  // namespace venimapping::camera
