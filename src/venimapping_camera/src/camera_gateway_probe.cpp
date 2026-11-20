// -----------------------------------------------------------------------------
//  Filename: camera_gateway_probe.cpp
//
//  Purpose:  Exercises VimbaXCameraGateway against a live driver and camera (temporary probe).
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <functional>
#include <memory>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "rclcpp/rclcpp.hpp"

#include "venimapping_camera/camera_gateway.hpp"
#include "venimapping_camera/types/expected.hpp"
#include "venimapping_camera/vimbax_camera_gateway.hpp"

namespace {

using venimapping::camera::CameraGateway;
using venimapping::camera::Error;
using venimapping::camera::ErrorDomain;
using venimapping::camera::Expected;
using venimapping::camera::FeatureDataType;
using venimapping::camera::FeatureFlags;
using venimapping::camera::FeatureFloatInfo;
using venimapping::camera::FeatureInfo;
using venimapping::camera::FeatureInfoList;
using venimapping::camera::FeatureModule;
using venimapping::camera::VimbaXCameraGateway;

std::string describe(const Error& error)
{
  const char* const domain =
      error.domain() == ErrorDomain::kDriver ? "driver" : "gateway";
  return std::string{"["} + domain + " error " + std::to_string(error.code()) +
         "] " + error.text();
}

std::string describe(bool value)
{
  return value ? "true" : "false";
}

std::string describe(const FeatureFlags& flags)
{
  return "none=" + describe(flags.none) + " read=" + describe(flags.read) +
         " write=" + describe(flags.write) + " volatile=" + describe(flags.is_volatile) +
         " modify_write=" + describe(flags.modify_write);
}

std::string describe(FeatureDataType data_type)
{
  switch (data_type) {
    case FeatureDataType::kUnknown:
      return "unknown";
    case FeatureDataType::kInt:
      return "int";
    case FeatureDataType::kFloat:
      return "float";
    case FeatureDataType::kEnum:
      return "enum";
    case FeatureDataType::kString:
      return "string";
    case FeatureDataType::kBool:
      return "bool";
    case FeatureDataType::kCommand:
      return "command";
    case FeatureDataType::kRaw:
      return "raw";
    case FeatureDataType::kNone:
      return "none";
  }
  return "out of range";
}

class ProbeReport {
 public:
  explicit ProbeReport(rclcpp::Logger logger)
      : logger_{std::move(logger)} {}

  void pass(const std::string& check, const std::string& detail)
  {
    RCLCPP_INFO(logger_, "PASS %s: %s", check.c_str(), detail.c_str());
  }

  void fail(const std::string& check, const std::string& detail)
  {
    failure_count_ += 1;
    RCLCPP_ERROR(logger_, "FAIL %s: %s", check.c_str(), detail.c_str());
  }

  void skip(const std::string& check, const std::string& detail)
  {
    skip_count_ += 1;
    RCLCPP_WARN(logger_, "SKIP %s: %s", check.c_str(), detail.c_str());
  }

  [[nodiscard]] bool all_passed() const noexcept { return failure_count_ == 0; }

  [[nodiscard]] int failure_count() const noexcept { return failure_count_; }

  [[nodiscard]] int skip_count() const noexcept { return skip_count_; }

 private:
  rclcpp::Logger logger_;
  int failure_count_ = 0;
  int skip_count_ = 0;
};

// An empty bool_feature, command_feature or raw_feature picks the first
// remote-device feature of that type. Nothing is written unless enable_writes.
struct ProbeOptions {
  std::string camera_namespace;
  std::chrono::milliseconds timeout{};
  std::string int_feature;
  std::string float_feature;
  std::string string_feature;
  std::string bool_feature;
  std::string enum_feature;
  std::string command_feature;
  std::string raw_feature;
  std::string absent_feature;
  bool enable_writes{};
  std::string write_enum_feature;
  std::string write_int_feature;
  std::string write_string_feature;
  std::string write_string_value;
  std::string write_bool_feature;
  std::string write_raw_feature;
  std::string run_command_feature;
  std::string settings_save_file;
  std::string settings_load_file;
  bool exercise_stream{};
};

ProbeOptions declare_options(rclcpp::Node& node)
{
  ProbeOptions options;
  options.camera_namespace =
      node.declare_parameter<std::string>("camera_namespace", "/vimbax_camera");
  options.timeout =
      std::chrono::milliseconds{node.declare_parameter<int>("timeout_ms", 2000)};
  options.int_feature =
      node.declare_parameter<std::string>("int_feature", "Width");
  options.float_feature =
      node.declare_parameter<std::string>("float_feature", "ExposureTime");
  options.string_feature =
      node.declare_parameter<std::string>("string_feature", "DeviceModelName");
  options.bool_feature = node.declare_parameter<std::string>("bool_feature", "");
  options.enum_feature =
      node.declare_parameter<std::string>("enum_feature", "PixelFormat");
  options.command_feature = node.declare_parameter<std::string>("command_feature", "");
  options.raw_feature = node.declare_parameter<std::string>("raw_feature", "");
  options.absent_feature = node.declare_parameter<std::string>(
      "absent_feature", "VeniMappingDeliberatelyAbsentFeature");
  options.enable_writes = node.declare_parameter<bool>("enable_writes", false);
  options.write_enum_feature =
      node.declare_parameter<std::string>("write_enum_feature", "LineSelector");
  options.write_int_feature = node.declare_parameter<std::string>("write_int_feature", "");
  options.write_string_feature =
      node.declare_parameter<std::string>("write_string_feature", "");
  options.write_string_value =
      node.declare_parameter<std::string>("write_string_value", "venimapping-probe");
  options.write_bool_feature = node.declare_parameter<std::string>("write_bool_feature", "");
  options.write_raw_feature = node.declare_parameter<std::string>("write_raw_feature", "");
  options.run_command_feature =
      node.declare_parameter<std::string>("run_command_feature", "");
  options.settings_save_file = node.declare_parameter<std::string>("settings_save_file", "");
  options.settings_load_file = node.declare_parameter<std::string>("settings_load_file", "");
  options.exercise_stream = node.declare_parameter<bool>("exercise_stream", false);
  return options;
}

template <typename T>
bool succeeded(const Expected<T>& result, const std::string& check, ProbeReport& report)
{
  if (!result) {
    report.fail(check, describe(result.error()));
  }
  return result.has_value();
}

void check_connection_status(CameraGateway& camera, ProbeReport& report)
{
  const auto connected = camera.connection_status();
  if (succeeded(connected, "ConnectionStatus", report)) {
    report.pass("ConnectionStatus", *connected ? "connected" : "not connected");
  }
}

void check_camera_status(CameraGateway& camera, ProbeReport& report)
{
  const auto status = camera.camera_status();
  if (!succeeded(status, "CameraStatus", report)) {
    return;
  }
  report.pass("CameraStatus",
              "model=" + status->model_name +
                  " serial=" + status->device_serial_number +
                  " pixel_format=" + status->pixel_format +
                  " frame_rate=" + std::to_string(status->frame_rate) +
                  " size=" + std::to_string(status->width) + "x" +
                  std::to_string(status->height) +
                  " streaming=" + describe(status->streaming));
  report.pass("CameraStatus/identity",
              "display_name=" + status->display_name +
                  " firmware=" + status->device_firmware_version +
                  " device_id=" + status->device_id +
                  " user_id=" + status->device_user_id +
                  " interface=" + status->interface_id +
                  " transport_layer=" + status->transport_layer_id +
                  " ip=" + status->ip_address.value_or("(none)") +
                  " mac=" + status->mac_address.value_or("(none)"));

  std::string triggers;
  for (const auto& trigger : status->trigger_info) {
    triggers += " [" + trigger.selector + ": mode=" + trigger.mode + " source=" + trigger.source + "]";
  }
  report.pass("CameraStatus/trigger_info",
              std::to_string(status->trigger_info.size()) + " selector(s)" + triggers);
}

void check_feature_list(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const auto features = camera.feature_list_get(FeatureModule::kRemoteDevice);
  if (!succeeded(features, "FeatureListGet", report)) {
    return;
  }
  const auto& names = features->names;
  report.pass("FeatureListGet", std::to_string(names.size()) + " features");

  const bool known_name_present =
      std::ranges::find(names, options.float_feature) != names.end();
  if (known_name_present) {
    report.pass("FeatureListGet/known-name",
                options.float_feature + " is present");
  } else {
    report.fail("FeatureListGet/known-name",
                options.float_feature + " is absent from the feature list");
  }

  const bool absent_name_present =
      std::ranges::find(names, options.absent_feature) != names.end();
  if (absent_name_present) {
    report.fail("FeatureListGet/absent-name",
                options.absent_feature + " unexpectedly present");
  } else {
    report.pass("FeatureListGet/absent-name",
                options.absent_feature + " is absent as expected");
  }
}

void check_other_modules(CameraGateway& camera, ProbeReport& report)
{
  struct NamedModule {
    FeatureModule feature_module;
    const char* name;
  };
  const std::array<NamedModule, 4> modules{{
      {.feature_module = FeatureModule::kSystem, .name = "system"},
      {.feature_module = FeatureModule::kInterface, .name = "interface"},
      {.feature_module = FeatureModule::kLocalDevice, .name = "local-device"},
      {.feature_module = FeatureModule::kStream, .name = "stream"},
  }};

  for (const auto& entry : modules) {
    const std::string check = std::string{"FeatureListGet/"} + entry.name;
    const auto features = camera.feature_list_get(entry.feature_module);
    if (succeeded(features, check, report)) {
      report.pass(check, std::to_string(features->names.size()) + " features");
    }
  }
}

void check_driver_error_passthrough(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const auto absent = camera.feature_float_get(options.absent_feature, FeatureModule::kRemoteDevice);
  if (absent) {
    report.fail("DriverError/absent-feature", "reading " + options.absent_feature + " unexpectedly succeeded");
  } else if (absent.error().domain() != ErrorDomain::kDriver) {
    report.fail("DriverError/absent-feature", describe(absent.error()));
  } else {
    report.pass("DriverError/absent-feature", describe(absent.error()));
  }

  // Deliberately invalid: the driver, not the gateway, must reject it.
  const auto unknown_module = camera.feature_list_get(static_cast<FeatureModule>(200));
  if (unknown_module) {
    report.fail("DriverError/unknown-module", "listing module 200 unexpectedly succeeded");
  } else if (unknown_module.error().domain() != ErrorDomain::kDriver) {
    report.fail("DriverError/unknown-module", describe(unknown_module.error()));
  } else {
    report.pass("DriverError/unknown-module", describe(unknown_module.error()));
  }
}

FeatureInfoList check_feature_info(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const auto named = camera.feature_info_list_get({.names = {options.float_feature, options.enum_feature}}, FeatureModule::kRemoteDevice);
  if (succeeded(named, "FeatureInfoListGet/named", report)) {
    const auto& entries = named->features;
    const bool as_requested =
        entries.size() == 2 &&
        entries[0].name == options.float_feature && entries[0].data_type == FeatureDataType::kFloat &&
        entries[1].name == options.enum_feature && entries[1].data_type == FeatureDataType::kEnum;
    std::string detail;
    for (const auto& info : entries) {
      detail += " [" + info.name + ": type=" + describe(info.data_type) +
                " category=" + info.category +
                " display_name=" + info.display_name +
                " sfnc_namespace=" + info.sfnc_namespace +
                " unit=" + info.unit +
                " flags={" + describe(info.flags) + "}" +
                " polling_time=" + std::to_string(info.polling_time) + "]";
    }
    if (as_requested) {
      report.pass("FeatureInfoListGet/named", std::to_string(entries.size()) + " entries" + detail);
    } else {
      report.fail("FeatureInfoListGet/named", "expected a float and an enum entry in request order, got" + detail);
    }
  }

  auto all = camera.feature_info_list_get({}, FeatureModule::kRemoteDevice);
  if (!succeeded(all, "FeatureInfoListGet/all", report)) {
    return {};
  }
  std::array<int, 9> count_by_type{};
  for (const auto& info : all->features) {
    count_by_type.at(std::to_underlying(info.data_type)) += 1;
  }
  std::string detail;
  for (std::size_t type = 0; type < count_by_type.size(); ++type) {
    detail += " " + describe(static_cast<FeatureDataType>(type)) + "=" + std::to_string(count_by_type.at(type));
  }
  report.pass("FeatureInfoListGet/all", std::to_string(all->features.size()) + " features:" + detail);
  return std::move(*all);
}

std::string resolve_feature(const std::string& configured_name,
                            FeatureDataType data_type,
                            const FeatureInfoList& feature_info)
{
  if (!configured_name.empty()) {
    return configured_name;
  }
  const auto& features = feature_info.features;
  const auto match = std::ranges::find(features, data_type, &FeatureInfo::data_type);
  return match == features.end() ? std::string{} : match->name;
}

bool readable_now(CameraGateway& camera, const std::string& feature, const std::string& check, ProbeReport& report)
{
  const auto access = camera.feature_access_mode_get(feature, FeatureModule::kRemoteDevice);
  if (!access) {
    report.fail(check, "access mode: " + describe(access.error()));
    return false;
  }
  if (!access->readable) {
    report.skip(check, "feature is not currently readable");
    return false;
  }
  return true;
}

// Also checks that the feature's static flags allow what its live access
// mode allows, which the driver gets wrong before v1.0.1-beta1-venimapping.1.
void check_access_mode(CameraGateway& camera, const ProbeOptions& options,
                       const FeatureInfoList& feature_info, ProbeReport& report)
{
  const std::string check = "FeatureAccessModeGet(" + options.float_feature + ")";
  const auto access = camera.feature_access_mode_get(options.float_feature, FeatureModule::kRemoteDevice);
  if (!succeeded(access, check, report)) {
    return;
  }
  report.pass(check, "readable=" + describe(access->readable) + " writable=" + describe(access->writable));

  const std::string flags_check = check + "/flags";
  const auto& features = feature_info.features;
  const auto info = std::ranges::find(features, options.float_feature, &FeatureInfo::name);
  if (info == features.end()) {
    report.skip(flags_check, "feature is not in the FeatureInfoListGet/all result");
    return;
  }
  const std::string detail = "static " + describe(info->flags);
  if ((access->readable && !info->flags.read) || (access->writable && !info->flags.write)) {
    report.fail(flags_check, "live access mode is not allowed by the " + detail);
  } else {
    report.pass(flags_check, detail);
  }
}

void check_int_feature(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.int_feature;

  const auto value = camera.feature_int_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(value, "FeatureIntGet(" + feature + ")", report)) {
    report.pass("FeatureIntGet(" + feature + ")", std::to_string(*value));
  }

  const auto info = camera.feature_int_info_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(info, "FeatureIntInfoGet(" + feature + ")", report)) {
    report.pass("FeatureIntInfoGet(" + feature + ")",
                "min=" + std::to_string(info->min) +
                    " max=" + std::to_string(info->max) +
                    " inc=" + std::to_string(info->inc));
  }
}

void check_float_feature(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.float_feature;

  const auto value = camera.feature_float_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(value, "FeatureFloatGet(" + feature + ")", report)) {
    report.pass("FeatureFloatGet(" + feature + ")", std::to_string(*value));
  }

  const auto info = camera.feature_float_info_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(info, "FeatureFloatInfoGet(" + feature + ")", report)) {
    report.pass("FeatureFloatInfoGet(" + feature + ")",
                "min=" + std::to_string(info->min) +
                    " max=" + std::to_string(info->max) +
                    " inc=" +
                    (info->inc_available ? std::to_string(info->inc)
                                         : std::string{"(unavailable)"}));
  }
}

void check_string_feature(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.string_feature;

  const auto value = camera.feature_string_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(value, "FeatureStringGet(" + feature + ")", report)) {
    report.pass("FeatureStringGet(" + feature + ")", "\"" + *value + "\"");
  }

  const auto max_length = camera.feature_string_info_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(max_length, "FeatureStringInfoGet(" + feature + ")", report)) {
    report.pass("FeatureStringInfoGet(" + feature + ")", "max_length=" + std::to_string(*max_length));
  }
}

void check_bool_feature(CameraGateway& camera, const std::string& feature, ProbeReport& report)
{
  if (feature.empty()) {
    report.skip("FeatureBoolGet", "the camera reports no bool feature");
    return;
  }
  if (!readable_now(camera, feature, "FeatureBoolGet(" + feature + ")", report)) {
    return;
  }
  const auto value = camera.feature_bool_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(value, "FeatureBoolGet(" + feature + ")", report)) {
    report.pass("FeatureBoolGet(" + feature + ")", describe(*value));
  }
}

void check_enum_feature(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.enum_feature;

  const auto info = camera.feature_enum_info_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(info, "FeatureEnumInfoGet(" + feature + ")", report)) {
    report.pass("FeatureEnumInfoGet(" + feature + ")",
                std::to_string(info->possible_values.size()) + " possible, " +
                    std::to_string(info->available_values.size()) +
                    " available");
  }

  const auto value = camera.feature_enum_get(feature, FeatureModule::kRemoteDevice);
  if (!succeeded(value, "FeatureEnumGet(" + feature + ")", report)) {
    return;
  }
  report.pass("FeatureEnumGet(" + feature + ")", *value);

  const auto as_int = camera.feature_enum_as_int_get(feature, *value, FeatureModule::kRemoteDevice);
  if (!succeeded(as_int, "FeatureEnumAsIntGet(" + feature + ")", report)) {
    return;
  }
  report.pass("FeatureEnumAsIntGet(" + feature + ")", *value + " = " + std::to_string(*as_int));

  const auto as_string = camera.feature_enum_as_string_get(feature, *as_int, FeatureModule::kRemoteDevice);
  if (!succeeded(as_string, "FeatureEnumAsStringGet(" + feature + ")", report)) {
    return;
  }
  if (*as_string == *value) {
    report.pass("FeatureEnumAsStringGet(" + feature + ")", std::to_string(*as_int) + " = " + *as_string);
  } else {
    report.fail("FeatureEnumAsStringGet(" + feature + ")",
                std::to_string(*as_int) + " came back as " + *as_string + ", expected " + *value);
  }
}

void check_command_feature(CameraGateway& camera, const std::string& feature, ProbeReport& report)
{
  if (feature.empty()) {
    report.skip("FeatureCommandIsDone", "the camera reports no command feature");
    return;
  }
  const auto done = camera.feature_command_is_done(feature, FeatureModule::kRemoteDevice);
  if (succeeded(done, "FeatureCommandIsDone(" + feature + ")", report)) {
    report.pass("FeatureCommandIsDone(" + feature + ")", "is_done=" + describe(*done));
  }
}

void check_raw_feature(CameraGateway& camera, const std::string& feature, ProbeReport& report)
{
  if (feature.empty()) {
    report.skip("FeatureRawGet", "the camera reports no raw feature");
    return;
  }
  if (!readable_now(camera, feature, "FeatureRawGet(" + feature + ")", report)) {
    return;
  }

  const auto max_length = camera.feature_raw_info_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(max_length, "FeatureRawInfoGet(" + feature + ")", report)) {
    report.pass("FeatureRawInfoGet(" + feature + ")", "max_length=" + std::to_string(*max_length));
  }

  const auto value = camera.feature_raw_get(feature, FeatureModule::kRemoteDevice);
  if (succeeded(value, "FeatureRawGet(" + feature + ")", report)) {
    report.pass("FeatureRawGet(" + feature + ")", std::to_string(value->bytes.size()) + " bytes");
  }
}

void run_read_only_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  FeatureInfoList feature_info;
  const auto first_of = [&](const std::string& configured_name, FeatureDataType data_type) {
    return resolve_feature(configured_name, data_type, feature_info);
  };

  const std::array<std::function<void()>, 14> checks{{
      [&] { check_connection_status(camera, report); },
      [&] { check_camera_status(camera, report); },
      [&] { check_feature_list(camera, options, report); },
      [&] { check_other_modules(camera, report); },
      [&] { check_driver_error_passthrough(camera, options, report); },
      [&] { feature_info = check_feature_info(camera, options, report); },
      [&] { check_access_mode(camera, options, feature_info, report); },
      [&] { check_int_feature(camera, options, report); },
      [&] { check_float_feature(camera, options, report); },
      [&] { check_string_feature(camera, options, report); },
      [&] { check_bool_feature(camera, first_of(options.bool_feature, FeatureDataType::kBool), report); },
      [&] { check_enum_feature(camera, options, report); },
      [&] { check_command_feature(camera, first_of(options.command_feature, FeatureDataType::kCommand), report); },
      [&] { check_raw_feature(camera, first_of(options.raw_feature, FeatureDataType::kRaw), report); },
  }};

  for (const auto& check : checks) {
    if (!rclcpp::ok()) {
      return;
    }
    check();
  }
}

// A target in [min, max], aligned to inc if available, other than original.
double choose_float_target(const FeatureFloatInfo& info, double original)
{
  double target = info.min + ((info.max - info.min) / 2.0);
  if (info.inc_available && info.inc > 0.0) {
    target = info.min + std::round((target - info.min) / info.inc) * info.inc;
  }
  target = std::clamp(target, info.min, info.max);

  if (target == original) {
    const double step = (info.inc_available && info.inc > 0.0)
                            ? info.inc
                            : (info.max - info.min) / 4.0;
    target = (target + step <= info.max) ? target + step : target - step;
    target = std::clamp(target, info.min, info.max);
  }
  return target;
}

bool float_values_match(double expected, double actual, const FeatureFloatInfo& info)
{
  // The camera may quantize writes.
  const double tolerance = (info.inc_available && info.inc > 0.0)
                               ? info.inc / 2.0
                               : (std::abs(expected) * 1e-6) + 1e-9;
  return std::abs(actual - expected) <= tolerance;
}

void run_float_write_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.float_feature;
  const std::string check = "FloatWrite(" + feature + ")";

  const auto access = camera.feature_access_mode_get(feature, FeatureModule::kRemoteDevice);
  if (!access) {
    report.fail(check, "access mode: " + describe(access.error()));
    return;
  }
  if (!access->readable || !access->writable) {
    report.skip(check, "feature is not currently both readable and writable");
    return;
  }

  const auto info = camera.feature_float_info_get(feature, FeatureModule::kRemoteDevice);
  if (!info) {
    report.fail(check, "metadata: " + describe(info.error()));
    return;
  }

  const auto original = camera.feature_float_get(feature, FeatureModule::kRemoteDevice);
  if (!original) {
    report.fail(check, "original read: " + describe(original.error()));
    return;
  }

  if (!std::isfinite(info->min) || !std::isfinite(info->max) ||
      info->min > info->max ||
      (info->inc_available && !std::isfinite(info->inc)) ||
      !std::isfinite(*original)) {
    report.skip(check, "driver metadata or current value unusable: min=" + std::to_string(info->min) + " max=" + std::to_string(info->max) + " current=" + std::to_string(*original));
    return;
  }

  const double target = choose_float_target(*info, *original);
  if (target == *original) {
    report.skip(check, "could not choose a target different from " + std::to_string(*original));
    return;
  }

  if (auto set = camera.feature_float_set(feature, target, FeatureModule::kRemoteDevice); !set) {
    report.fail(check, "set to " + std::to_string(target) + ": " + describe(set.error()));
    return;
  }

  if (auto readback = camera.feature_float_get(feature, FeatureModule::kRemoteDevice);
      readback && float_values_match(target, *readback, *info)) {
    report.pass(check, "wrote " + std::to_string(target) + ", read back " + std::to_string(*readback));
  } else if (readback) {
    report.fail(check, "wrote " + std::to_string(target) + " but read back " + std::to_string(*readback));
  } else {
    report.fail(check, "readback: " + describe(readback.error()));
  }

  // Restore even if verification failed.
  if (auto restore = camera.feature_float_set(feature, *original, FeatureModule::kRemoteDevice); !restore) {
    report.fail(check + "/restore", "RESTORATION FAILED, camera left at " + std::to_string(target) + ": " + describe(restore.error()));
    return;
  }
  if (auto verify = camera.feature_float_get(feature, FeatureModule::kRemoteDevice);
      verify && float_values_match(*original, *verify, *info)) {
    report.pass(check + "/restore", "restored to " + std::to_string(*verify));
  } else if (verify) {
    report.fail(check + "/restore", "RESTORATION MISMATCH: expected " + std::to_string(*original) + ", read back " + std::to_string(*verify));
  } else {
    report.fail(check + "/restore",
                "restoration readback: " + describe(verify.error()));
  }
}

void run_enum_write_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.write_enum_feature;
  const std::string check = "EnumWrite(" + feature + ")";

  const auto access = camera.feature_access_mode_get(feature, FeatureModule::kRemoteDevice);
  if (!access) {
    report.fail(check, "access mode: " + describe(access.error()));
    return;
  }
  if (!access->readable || !access->writable) {
    report.skip(check, "feature is not currently both readable and writable");
    return;
  }

  const auto info = camera.feature_enum_info_get(feature, FeatureModule::kRemoteDevice);
  if (!info) {
    report.fail(check, "metadata: " + describe(info.error()));
    return;
  }

  const auto original = camera.feature_enum_get(feature, FeatureModule::kRemoteDevice);
  if (!original) {
    report.fail(check, "original read: " + describe(original.error()));
    return;
  }

  const auto target = std::find_if(
      info->available_values.begin(), info->available_values.end(), [&](const std::string& candidate) { return candidate != *original; });
  if (target == info->available_values.end()) {
    report.skip(check, "no available value other than " + *original);
    return;
  }

  if (auto set = camera.feature_enum_set(feature, *target, FeatureModule::kRemoteDevice); !set) {
    report.fail(check, "set to " + *target + ": " + describe(set.error()));
    return;
  }

  if (auto readback = camera.feature_enum_get(feature, FeatureModule::kRemoteDevice);
      readback && *readback == *target) {
    report.pass(check, "wrote " + *target + ", read back " + *readback);
  } else if (readback) {
    report.fail(check,
                "wrote " + *target + " but read back " + *readback);
  } else {
    report.fail(check, "readback: " + describe(readback.error()));
  }

  // Restore even if verification failed.
  if (auto restore = camera.feature_enum_set(feature, *original, FeatureModule::kRemoteDevice); !restore) {
    report.fail(check + "/restore", "RESTORATION FAILED, camera left at " + *target + ": " + describe(restore.error()));
    return;
  }
  if (auto verify = camera.feature_enum_get(feature, FeatureModule::kRemoteDevice);
      verify && *verify == *original) {
    report.pass(check + "/restore", "restored to " + *verify);
  } else if (verify) {
    report.fail(check + "/restore", "RESTORATION MISMATCH: expected " + *original + ", read back " + *verify);
  } else {
    report.fail(check + "/restore",
                "restoration readback: " + describe(verify.error()));
  }
}

bool writable_now(CameraGateway& camera, const std::string& feature, const std::string& check, ProbeReport& report)
{
  const auto access = camera.feature_access_mode_get(feature, FeatureModule::kRemoteDevice);
  if (!access) {
    report.fail(check, "access mode: " + describe(access.error()));
    return false;
  }
  if (!access->readable || !access->writable) {
    report.skip(check, "feature is not currently both readable and writable");
    return false;
  }
  return true;
}

template <typename T, typename Get, typename Set, typename Show>
void write_and_restore(const std::string& check,
                       const T& original,
                       const T& target,
                       Get get,
                       Set set,
                       Show show,
                       ProbeReport& report)
{
  if (auto written = set(target); !written) {
    report.fail(check, "set to " + show(target) + ": " + describe(written.error()));
    return;
  }

  if (auto readback = get(); readback && *readback == target) {
    report.pass(check, "wrote " + show(target) + ", read back " + show(*readback));
  } else if (readback) {
    report.fail(check, "wrote " + show(target) + " but read back " + show(*readback));
  } else {
    report.fail(check, "readback: " + describe(readback.error()));
  }

  // Restore even if verification failed.
  if (auto restored = set(original); !restored) {
    report.fail(check + "/restore", "RESTORATION FAILED, camera left at " + show(target) + ": " + describe(restored.error()));
    return;
  }
  if (auto verify = get(); verify && *verify == original) {
    report.pass(check + "/restore", "restored to " + show(*verify));
  } else if (verify) {
    report.fail(check + "/restore", "RESTORATION MISMATCH: expected " + show(original) + ", read back " + show(*verify));
  } else {
    report.fail(check + "/restore", "restoration readback: " + describe(verify.error()));
  }
}

void run_int_write_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.write_int_feature;
  const std::string check = "IntWrite(" + feature + ")";
  if (!writable_now(camera, feature, check, report)) {
    return;
  }

  const auto info = camera.feature_int_info_get(feature, FeatureModule::kRemoteDevice);
  if (!info) {
    report.fail(check, "metadata: " + describe(info.error()));
    return;
  }
  const auto original = camera.feature_int_get(feature, FeatureModule::kRemoteDevice);
  if (!original) {
    report.fail(check, "original read: " + describe(original.error()));
    return;
  }

  const std::int64_t step = std::max<std::int64_t>(info->inc, 1);
  const bool room_above = *original <= info->max - step;
  const bool room_below = *original >= info->min + step;
  if (!room_above && !room_below) {
    report.skip(check, "no value one increment away from " + std::to_string(*original) + " within [" + std::to_string(info->min) + ", " + std::to_string(info->max) + "]");
    return;
  }
  const std::int64_t target = room_above ? *original + step : *original - step;

  write_and_restore(
      check,
      *original,
      target,
      [&] { return camera.feature_int_get(feature, FeatureModule::kRemoteDevice); },
      [&](std::int64_t value) { return camera.feature_int_set(feature, value, FeatureModule::kRemoteDevice); },
      [](std::int64_t value) { return std::to_string(value); },
      report);
}

void run_string_write_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.write_string_feature;
  const std::string check = "StringWrite(" + feature + ")";
  if (!writable_now(camera, feature, check, report)) {
    return;
  }

  const auto max_length = camera.feature_string_info_get(feature, FeatureModule::kRemoteDevice);
  if (!max_length) {
    report.fail(check, "metadata: " + describe(max_length.error()));
    return;
  }
  const auto original = camera.feature_string_get(feature, FeatureModule::kRemoteDevice);
  if (!original) {
    report.fail(check, "original read: " + describe(original.error()));
    return;
  }

  const std::string& target = options.write_string_value;
  if (target == *original || std::cmp_greater(target.size(), *max_length)) {
    report.skip(check, "write_string_value \"" + target + "\" equals the current value or exceeds max_length " + std::to_string(*max_length));
    return;
  }

  write_and_restore(
      check,
      *original,
      target,
      [&] { return camera.feature_string_get(feature, FeatureModule::kRemoteDevice); },
      [&](const std::string& value) { return camera.feature_string_set(feature, value, FeatureModule::kRemoteDevice); },
      [](const std::string& value) { return "\"" + value + "\""; },
      report);
}

void run_bool_write_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.write_bool_feature;
  const std::string check = "BoolWrite(" + feature + ")";
  if (!writable_now(camera, feature, check, report)) {
    return;
  }

  const auto original = camera.feature_bool_get(feature, FeatureModule::kRemoteDevice);
  if (!original) {
    report.fail(check, "original read: " + describe(original.error()));
    return;
  }

  write_and_restore(
      check,
      *original,
      !*original,
      [&] { return camera.feature_bool_get(feature, FeatureModule::kRemoteDevice); },
      [&](bool value) { return camera.feature_bool_set(feature, value, FeatureModule::kRemoteDevice); },
      [](bool value) { return describe(value); },
      report);
}

// Writes back the bytes just read: exercises set without changing anything.
void run_raw_write_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.write_raw_feature;
  const std::string check = "RawWrite(" + feature + ")";
  if (!writable_now(camera, feature, check, report)) {
    return;
  }

  const auto original = camera.feature_raw_get(feature, FeatureModule::kRemoteDevice);
  if (!original) {
    report.fail(check, "original read: " + describe(original.error()));
    return;
  }
  const auto& original_bytes = original->bytes;
  if (auto written = camera.feature_raw_set(feature, *original, FeatureModule::kRemoteDevice); !written) {
    report.fail(check, "set: " + describe(written.error()));
    return;
  }

  if (auto readback = camera.feature_raw_get(feature, FeatureModule::kRemoteDevice);
      readback && readback->bytes == original_bytes) {
    report.pass(check, "wrote back " + std::to_string(original_bytes.size()) + " unchanged bytes");
  } else if (readback) {
    report.fail(check, "readback differs from the " + std::to_string(original_bytes.size()) + " bytes written");
  } else {
    report.fail(check, "readback: " + describe(readback.error()));
  }
}

void run_command_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::string& feature = options.run_command_feature;
  const std::string check = "CommandRun(" + feature + ")";

  if (auto run = camera.feature_command_run(feature, FeatureModule::kRemoteDevice); !run) {
    report.fail(check, describe(run.error()));
    return;
  }
  const auto done = camera.feature_command_is_done(feature, FeatureModule::kRemoteDevice);
  if (succeeded(done, check, report)) {
    report.pass(check, "ran, is_done=" + describe(*done));
  }
}

void run_settings_sequence(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  if (!options.settings_save_file.empty()) {
    const auto saved = camera.settings_save(options.settings_save_file);
    if (succeeded(saved, "SettingsSave", report)) {
      report.pass("SettingsSave", "driver wrote " + options.settings_save_file);
    }
  }
  if (!options.settings_load_file.empty() && rclcpp::ok()) {
    const auto loaded = camera.settings_load(options.settings_load_file);
    if (succeeded(loaded, "SettingsLoad", report)) {
      report.pass("SettingsLoad", "driver loaded " + options.settings_load_file);
    }
  }
}

void run_stream_sequence(CameraGateway& camera, ProbeReport& report)
{
  const auto before = camera.camera_status();
  if (!before) {
    report.fail("Stream", "initial status: " + describe(before.error()));
    return;
  }

  const auto switch_to = [&](bool streaming, const std::string& check) {
    if (auto switched = streaming ? camera.stream_start() : camera.stream_stop(); !switched) {
      report.fail(check, describe(switched.error()));
      return;
    }
    if (auto status = camera.camera_status(); status && status->streaming == streaming) {
      report.pass(check, "status reports streaming=" + describe(status->streaming));
    } else if (status) {
      report.fail(check, "status still reports streaming=" + describe(status->streaming));
    } else {
      report.fail(check, "status: " + describe(status.error()));
    }
  };

  switch_to(!before->streaming, before->streaming ? "StreamStop" : "StreamStart");
  switch_to(before->streaming, before->streaming ? "StreamStart/restore" : "StreamStop/restore");
}

void run_write_sequences(CameraGateway& camera, const ProbeOptions& options, ProbeReport& report)
{
  const std::array<std::function<void()>, 9> sequences{{
      [&] { run_float_write_sequence(camera, options, report); },
      [&] { run_enum_write_sequence(camera, options, report); },
      [&] {
        if (!options.write_int_feature.empty()) {
          run_int_write_sequence(camera, options, report);
        }
      },
      [&] {
        if (!options.write_string_feature.empty()) {
          run_string_write_sequence(camera, options, report);
        }
      },
      [&] {
        if (!options.write_bool_feature.empty()) {
          run_bool_write_sequence(camera, options, report);
        }
      },
      [&] {
        if (!options.write_raw_feature.empty()) {
          run_raw_write_sequence(camera, options, report);
        }
      },
      [&] {
        if (!options.run_command_feature.empty()) {
          run_command_sequence(camera, options, report);
        }
      },
      [&] { run_settings_sequence(camera, options, report); },
      [&] {
        if (options.exercise_stream) {
          run_stream_sequence(camera, report);
        }
      },
  }};

  for (const auto& sequence : sequences) {
    if (!rclcpp::ok()) {
      return;
    }
    sequence();
  }
}

int run_probe()
{
  auto node = rclcpp::Node::make_shared("camera_gateway_probe");
  const ProbeOptions options = declare_options(*node);

  RCLCPP_INFO(node->get_logger(),
              "probing camera namespace %s with a %lld ms timeout",
              options.camera_namespace.c_str(),
              static_cast<long long>(options.timeout.count()));

  // Spin elsewhere: this thread is the gateway worker and blocks in calls.
  rclcpp::executors::SingleThreadedExecutor executor;
  executor.add_node(node);
  std::thread executor_thread{[&executor] { executor.spin(); }};

  int exit_code = EXIT_FAILURE;
  try {
    // Scoped so the gateway is destroyed before the executor stops.
    auto created = VimbaXCameraGateway::create(*node, options.camera_namespace, options.timeout);
    if (!created) {
      RCLCPP_FATAL(node->get_logger(), "%s", describe(created.error()).c_str());
    } else if (auto bound = (*created)->bind_to_current_thread(); !bound) {
      RCLCPP_FATAL(node->get_logger(), "%s", describe(bound.error()).c_str());
    } else {
      auto gateway = std::move(*created);

      CameraGateway& camera = *gateway;

      ProbeReport report{node->get_logger()};
      run_read_only_sequence(camera, options, report);

      if (!options.enable_writes) {
        RCLCPP_INFO(node->get_logger(),
                    "write sequences disabled (enable_writes:=true to run)");
      } else {
        run_write_sequences(camera, options, report);
      }

      if (!rclcpp::ok()) {
        // An interrupted run proves nothing and must not read as success.
        RCLCPP_WARN(node->get_logger(),
                    "probe interrupted by shutdown before completing");
      } else if (report.all_passed()) {
        RCLCPP_INFO(node->get_logger(),
                    "probe complete: all checks passed (%d skipped)",
                    report.skip_count());
        exit_code = EXIT_SUCCESS;
      } else {
        RCLCPP_ERROR(node->get_logger(),
                     "probe complete: %d check(s) failed, %d skipped",
                     report.failure_count(),
                     report.skip_count());
      }
    }
  } catch (const std::exception& e) {
    // Unwinding past the joinable executor_thread would call std::terminate.
    RCLCPP_FATAL(node->get_logger(), "probe aborted by exception: %s", e.what());
  } catch (...) {
    RCLCPP_FATAL(node->get_logger(), "probe aborted by unknown exception");
  }

  // Not executor.cancel(): a cancel issued before spin() starts is lost and
  // join() hangs. spin() always exits once the context is shut down.
  rclcpp::shutdown();
  executor_thread.join();
  return exit_code;
}

}  // namespace

int main(int argc, char** argv)
{
  rclcpp::init(argc, argv);
  int exit_code = EXIT_FAILURE;
  try {
    exit_code = run_probe();
  } catch (const std::exception& e) {
    std::fprintf(stderr, "camera_gateway_probe: unhandled exception: %s\n", e.what());
  } catch (...) {
    std::fprintf(stderr, "camera_gateway_probe: unhandled unknown exception\n");
  }
  rclcpp::shutdown();
  return exit_code;
}
