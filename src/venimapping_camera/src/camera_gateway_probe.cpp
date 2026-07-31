// -----------------------------------------------------------------------------
//  Filename: camera_gateway_probe.cpp
//
//  Purpose:  TEMPORARY integration probe exercising VimbaXCameraGateway
//            against a running vimbax_ros2_driver and camera. Disposable by
//            design: no other target depends on it, and it accumulates no
//            configuration policy. It will be replaced by production
//            camera-node work in a later stage.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
#include <thread>
#include <utility>

#include "rclcpp/rclcpp.hpp"

#include "venimapping_camera/camera_gateway.hpp"
#include "venimapping_camera/expected.hpp"
#include "venimapping_camera/vimbax_camera_gateway.hpp"

namespace {

using venimapping::camera::CameraGateway;
using venimapping::camera::Error;
using venimapping::camera::ErrorDomain;
using venimapping::camera::FloatInfo;
using venimapping::camera::VimbaXCameraGateway;

std::string Describe(const Error& error)
{
  const char* const domain =
      error.domain() == ErrorDomain::driver ? "driver" : "gateway";
  return std::string{"["} + domain + " error " + std::to_string(error.code()) +
         "] " + error.text();
}

class ProbeReport {
 public:
  explicit ProbeReport(rclcpp::Logger logger) : logger_{std::move(logger)} {}

  void Pass(const std::string& check, const std::string& detail) {
    RCLCPP_INFO(logger_, "PASS %s: %s", check.c_str(), detail.c_str());
  }

  void Fail(const std::string& check, const std::string& detail) {
    failure_count_ += 1;
    RCLCPP_ERROR(logger_, "FAIL %s: %s", check.c_str(), detail.c_str());
  }

  void Skip(const std::string& check, const std::string& detail) {
    skip_count_ += 1;
    RCLCPP_WARN(logger_, "SKIP %s: %s", check.c_str(), detail.c_str());
  }

  [[nodiscard]] bool AllPassed() const noexcept { return failure_count_ == 0; }

  [[nodiscard]] int FailureCount() const noexcept { return failure_count_; }

  [[nodiscard]] int SkipCount() const noexcept { return skip_count_; }

 private:
  rclcpp::Logger logger_;
  int failure_count_ = 0;
  int skip_count_ = 0;
};

// Parameters the probe reads at startup. The camera namespace is a parameter
// because the driver's default namespace is pid-dependent; bring-up should
// prefer a stable namespace remap on the driver side.
struct ProbeOptions {
  std::string camera_namespace;
  std::chrono::milliseconds timeout;
  std::string float_feature;
  std::string enum_feature;
  std::string absent_feature;
  bool enable_writes;
  std::string write_enum_feature;
};

ProbeOptions DeclareOptions(rclcpp::Node& node)
{
  ProbeOptions options;
  options.camera_namespace =
      node.declare_parameter<std::string>("camera_namespace", "/vimbax_camera");
  options.timeout =
      std::chrono::milliseconds{node.declare_parameter<int>("timeout_ms", 2000)};
  options.float_feature =
      node.declare_parameter<std::string>("float_feature", "ExposureTime");
  options.enum_feature =
      node.declare_parameter<std::string>("enum_feature", "PixelFormat");
  options.absent_feature = node.declare_parameter<std::string>(
      "absent_feature", "VeniMappingDeliberatelyAbsentFeature");
  options.enable_writes = node.declare_parameter<bool>("enable_writes", false);
  options.write_enum_feature =
      node.declare_parameter<std::string>("write_enum_feature", "LineSelector");
  return options;
}

void CheckFeaturesList(CameraGateway& camera, const ProbeOptions& options,
                       ProbeReport& report)
{
  const auto features = camera.FeaturesListGet();
  if (!features) {
    report.Fail("FeaturesListGet", Describe(features.error()));
    return;
  }
  report.Pass("FeaturesListGet", std::to_string(features->size()) + " features");

  const bool known_name_present =
      std::find(features->begin(), features->end(), options.float_feature) !=
      features->end();
  if (known_name_present) {
    report.Pass("FeaturesListGet/known-name",
                options.float_feature + " is present");
  } else {
    report.Fail("FeaturesListGet/known-name",
                options.float_feature + " is absent from the feature list");
  }

  const bool absent_name_present =
      std::find(features->begin(), features->end(), options.absent_feature) !=
      features->end();
  if (absent_name_present) {
    report.Fail("FeaturesListGet/absent-name",
                options.absent_feature + " unexpectedly present");
  } else {
    report.Pass("FeaturesListGet/absent-name",
                options.absent_feature + " is absent as expected");
  }
}

void RunReadOnlySequence(CameraGateway& camera, const ProbeOptions& options,
                         ProbeReport& report)
{
  // Each block re-checks rclcpp::ok() so the sequence stops starting new
  // requests once shutdown begins; a call already in flight completes with a
  // bounded failure instead.
  if (!rclcpp::ok()) {
    return;
  }
  if (auto connected = camera.ConnectionStatusGet(); connected) {
    // false is a successful negative answer; it is reported, not failed on.
    report.Pass("ConnectionStatusGet",
                *connected ? "connected" : "not connected");
  } else {
    report.Fail("ConnectionStatusGet", Describe(connected.error()));
  }

  if (!rclcpp::ok()) {
    return;
  }
  if (auto status = camera.CameraStatusGet(); status) {
    report.Pass("CameraStatusGet",
                "model=" + status->model_name +
                    " serial=" + status->device_serial_number +
                    " pixel_format=" + status->pixel_format +
                    " frame_rate=" + std::to_string(status->frame_rate) +
                    " size=" + std::to_string(status->width) + "x" +
                    std::to_string(status->height) +
                    " streaming=" + (status->streaming ? "true" : "false"));
  } else {
    report.Fail("CameraStatusGet", Describe(status.error()));
  }

  if (!rclcpp::ok()) {
    return;
  }
  CheckFeaturesList(camera, options, report);

  if (!rclcpp::ok()) {
    return;
  }
  if (auto access = camera.FeatureAccessModeGet(options.float_feature); access) {
    report.Pass("FeatureAccessModeGet(" + options.float_feature + ")",
                std::string{"readable="} + (access->readable ? "true" : "false") +
                    " writable=" + (access->writable ? "true" : "false"));
  } else {
    report.Fail("FeatureAccessModeGet(" + options.float_feature + ")",
                Describe(access.error()));
  }

  if (!rclcpp::ok()) {
    return;
  }
  if (auto value = camera.FeatureFloatGet(options.float_feature); value) {
    report.Pass("FeatureFloatGet(" + options.float_feature + ")",
                std::to_string(*value));
  } else {
    report.Fail("FeatureFloatGet(" + options.float_feature + ")",
                Describe(value.error()));
  }

  if (!rclcpp::ok()) {
    return;
  }
  if (auto info = camera.FeatureFloatInfoGet(options.float_feature); info) {
    report.Pass("FeatureFloatInfoGet(" + options.float_feature + ")",
                "min=" + std::to_string(info->min) +
                    " max=" + std::to_string(info->max) +
                    " inc=" +
                    (info->inc_available ? std::to_string(info->inc)
                                         : std::string{"(unavailable)"}));
  } else {
    report.Fail("FeatureFloatInfoGet(" + options.float_feature + ")",
                Describe(info.error()));
  }

  if (!rclcpp::ok()) {
    return;
  }
  if (auto value = camera.FeatureEnumGet(options.enum_feature); value) {
    report.Pass("FeatureEnumGet(" + options.enum_feature + ")", *value);
  } else {
    report.Fail("FeatureEnumGet(" + options.enum_feature + ")",
                Describe(value.error()));
  }

  if (!rclcpp::ok()) {
    return;
  }
  if (auto info = camera.FeatureEnumInfoGet(options.enum_feature); info) {
    report.Pass("FeatureEnumInfoGet(" + options.enum_feature + ")",
                std::to_string(info->possible_values.size()) + " possible, " +
                    std::to_string(info->available_values.size()) +
                    " available");
  } else {
    report.Fail("FeatureEnumInfoGet(" + options.enum_feature + ")",
                Describe(info.error()));
  }
}

// Picks a write target inside [min, max], aligned to the increment when one is
// available, and different from the current value. Probe-local test logic, not
// gateway policy.
double ChooseFloatTarget(const FloatInfo& info, double original)
{
  double target = info.min + (info.max - info.min) / 2.0;
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

bool FloatValuesMatch(double expected, double actual, const FloatInfo& info)
{
  // The camera may quantize the written value, so readback is compared within
  // half an increment when one exists, and a small relative tolerance
  // otherwise.
  const double tolerance = (info.inc_available && info.inc > 0.0)
                               ? info.inc / 2.0
                               : std::abs(expected) * 1e-6 + 1e-9;
  return std::abs(actual - expected) <= tolerance;
}

void RunFloatWriteSequence(CameraGateway& camera, const ProbeOptions& options,
                           ProbeReport& report)
{
  const std::string& feature = options.float_feature;
  const std::string check = "FloatWrite(" + feature + ")";

  const auto access = camera.FeatureAccessModeGet(feature);
  if (!access) {
    report.Fail(check, "access mode: " + Describe(access.error()));
    return;
  }
  if (!access->readable || !access->writable) {
    report.Skip(check, "feature is not currently both readable and writable");
    return;
  }

  const auto info = camera.FeatureFloatInfoGet(feature);
  if (!info) {
    report.Fail(check, "metadata: " + Describe(info.error()));
    return;
  }

  const auto original = camera.FeatureFloatGet(feature);
  if (!original) {
    report.Fail(check, "original read: " + Describe(original.error()));
    return;
  }

  // Target selection and std::clamp assume ordered, finite metadata; a driver
  // reporting otherwise makes a safe write impossible, not a gateway failure.
  if (!std::isfinite(info->min) || !std::isfinite(info->max) ||
      info->min > info->max ||
      (info->inc_available && !std::isfinite(info->inc)) ||
      !std::isfinite(*original)) {
    report.Skip(check, "driver metadata or current value unusable: min=" +
                           std::to_string(info->min) +
                           " max=" + std::to_string(info->max) +
                           " current=" + std::to_string(*original));
    return;
  }

  const double target = ChooseFloatTarget(*info, *original);
  if (target == *original) {
    report.Skip(check, "could not choose a target different from " +
                           std::to_string(*original));
    return;
  }

  if (auto set = camera.FeatureFloatSet(feature, target); !set) {
    report.Fail(check, "set to " + std::to_string(target) + ": " +
                           Describe(set.error()));
    return;
  }

  if (auto readback = camera.FeatureFloatGet(feature);
      readback && FloatValuesMatch(target, *readback, *info)) {
    report.Pass(check, "wrote " + std::to_string(target) + ", read back " +
                           std::to_string(*readback));
  } else if (readback) {
    report.Fail(check, "wrote " + std::to_string(target) + " but read back " +
                           std::to_string(*readback));
  } else {
    report.Fail(check, "readback: " + Describe(readback.error()));
  }

  // Restoration runs regardless of the verification outcome above; leaving
  // the camera modified is the one result the write path must not produce.
  if (auto restore = camera.FeatureFloatSet(feature, *original); !restore) {
    report.Fail(check + "/restore", "RESTORATION FAILED, camera left at " +
                                        std::to_string(target) + ": " +
                                        Describe(restore.error()));
    return;
  }
  if (auto verify = camera.FeatureFloatGet(feature);
      verify && FloatValuesMatch(*original, *verify, *info)) {
    report.Pass(check + "/restore", "restored to " + std::to_string(*verify));
  } else if (verify) {
    report.Fail(check + "/restore", "RESTORATION MISMATCH: expected " +
                                        std::to_string(*original) +
                                        ", read back " +
                                        std::to_string(*verify));
  } else {
    report.Fail(check + "/restore",
                "restoration readback: " + Describe(verify.error()));
  }
}

void RunEnumWriteSequence(CameraGateway& camera, const ProbeOptions& options,
                          ProbeReport& report)
{
  const std::string& feature = options.write_enum_feature;
  const std::string check = "EnumWrite(" + feature + ")";

  const auto access = camera.FeatureAccessModeGet(feature);
  if (!access) {
    report.Fail(check, "access mode: " + Describe(access.error()));
    return;
  }
  if (!access->readable || !access->writable) {
    report.Skip(check, "feature is not currently both readable and writable");
    return;
  }

  const auto info = camera.FeatureEnumInfoGet(feature);
  if (!info) {
    report.Fail(check, "metadata: " + Describe(info.error()));
    return;
  }

  const auto original = camera.FeatureEnumGet(feature);
  if (!original) {
    report.Fail(check, "original read: " + Describe(original.error()));
    return;
  }

  const auto target = std::find_if(
      info->available_values.begin(), info->available_values.end(),
      [&](const std::string& candidate) { return candidate != *original; });
  if (target == info->available_values.end()) {
    report.Skip(check, "no available value other than " + *original);
    return;
  }

  if (auto set = camera.FeatureEnumSet(feature, *target); !set) {
    report.Fail(check, "set to " + *target + ": " + Describe(set.error()));
    return;
  }

  if (auto readback = camera.FeatureEnumGet(feature);
      readback && *readback == *target) {
    report.Pass(check, "wrote " + *target + ", read back " + *readback);
  } else if (readback) {
    report.Fail(check,
                "wrote " + *target + " but read back " + *readback);
  } else {
    report.Fail(check, "readback: " + Describe(readback.error()));
  }

  // Restoration runs regardless of the verification outcome above; leaving
  // the camera modified is the one result the write path must not produce.
  if (auto restore = camera.FeatureEnumSet(feature, *original); !restore) {
    report.Fail(check + "/restore", "RESTORATION FAILED, camera left at " +
                                        *target + ": " +
                                        Describe(restore.error()));
    return;
  }
  if (auto verify = camera.FeatureEnumGet(feature);
      verify && *verify == *original) {
    report.Pass(check + "/restore", "restored to " + *verify);
  } else if (verify) {
    report.Fail(check + "/restore", "RESTORATION MISMATCH: expected " +
                                        *original + ", read back " + *verify);
  } else {
    report.Fail(check + "/restore",
                "restoration readback: " + Describe(verify.error()));
  }
}

int RunProbe()
{
  auto node = rclcpp::Node::make_shared("camera_gateway_probe");
  const ProbeOptions options = DeclareOptions(*node);

  RCLCPP_INFO(node->get_logger(),
              "probing camera namespace %s with a %lld ms timeout",
              options.camera_namespace.c_str(),
              static_cast<long long>(options.timeout.count()));

  // The executor spins on its own thread so service responses complete while
  // this thread -- the designated gateway worker -- blocks inside calls.
  rclcpp::executors::SingleThreadedExecutor executor;
  executor.add_node(node);
  std::thread executor_thread{[&executor] { executor.spin(); }};

  int exit_code = EXIT_FAILURE;
  try {
    // Scope: the gateway and its service clients are destroyed before the
    // executor stops and the node is torn down.
    auto created = VimbaXCameraGateway::Create(*node, options.camera_namespace,
                                               options.timeout);
    if (!created) {
      RCLCPP_FATAL(node->get_logger(), "%s",
                   Describe(created.error()).c_str());
    } else if (auto bound = (*created)->BindToCurrentThread(); !bound) {
      RCLCPP_FATAL(node->get_logger(), "%s", Describe(bound.error()).c_str());
    } else {
      auto gateway = std::move(*created);

      // Everything past construction and binding needs only the contract.
      CameraGateway& camera = *gateway;

      ProbeReport report{node->get_logger()};
      RunReadOnlySequence(camera, options, report);

      if (!options.enable_writes) {
        RCLCPP_INFO(node->get_logger(),
                    "write sequences disabled (enable_writes:=true to run)");
      } else {
        if (rclcpp::ok()) {
          RunFloatWriteSequence(camera, options, report);
        }
        if (rclcpp::ok()) {
          RunEnumWriteSequence(camera, options, report);
        }
      }

      if (!rclcpp::ok()) {
        // An interrupted run proves nothing; zero executed checks must not
        // read as success.
        RCLCPP_WARN(node->get_logger(),
                    "probe interrupted by shutdown before completing");
      } else if (report.AllPassed()) {
        RCLCPP_INFO(node->get_logger(),
                    "probe complete: all checks passed (%d skipped)",
                    report.SkipCount());
        exit_code = EXIT_SUCCESS;
      } else {
        RCLCPP_ERROR(node->get_logger(),
                     "probe complete: %d check(s) failed, %d skipped",
                     report.FailureCount(), report.SkipCount());
      }
    }
  } catch (const std::exception& e) {
    // Catching here keeps the stack from unwinding past the joinable
    // executor thread below, which would call std::terminate.
    RCLCPP_FATAL(node->get_logger(), "probe aborted by exception: %s",
                 e.what());
  } catch (...) {
    RCLCPP_FATAL(node->get_logger(), "probe aborted by unknown exception");
  }

  // Shutting the context down, rather than executor.cancel(), closes the
  // startup race in which a cancel issued before spin() begins is lost and
  // join() blocks forever; spin() also exits once the context is down.
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
    exit_code = RunProbe();
  } catch (const std::exception& e) {
    // A throw before RunProbe()'s own handling exists -- e.g. a mistyped
    // parameter in DeclareOptions() -- still gets a message and an orderly
    // shutdown.
    std::fprintf(stderr, "camera_gateway_probe: unhandled exception: %s\n",
                 e.what());
  } catch (...) {
    std::fprintf(stderr, "camera_gateway_probe: unhandled unknown exception\n");
  }
  rclcpp::shutdown();
  return exit_code;
}
