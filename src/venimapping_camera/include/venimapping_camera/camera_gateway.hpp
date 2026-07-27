// -----------------------------------------------------------------------------
//  Filename: camera_gateway.hpp
//
//  Purpose:  Declares the ROS-independent camera gateway contract and the
//            result types it returns.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "venimapping_camera/expected.hpp"

namespace venimapping::camera {

// --- Domain types ------------------------------------------------------------

// Float feature metadata.
struct FloatInfo {
  double min;
  double max;
  double inc;  // meaningful only when inc_available is true
  bool inc_available;
};

// Current access state of a feature. It changes with streaming and with other
// feature values, so a result describes the moment it was queried.
struct AccessMode {
  bool readable;
  bool writable;
};

// Enum feature metadata.
struct EnumInfo {
  std::vector<std::string> possible_values;   // every option the feature defines
  std::vector<std::string> available_values;  // the subset selectable right now
};

// The consumed subset of the driver's camera status.
struct CameraStatus {
  std::string model_name;
  std::string device_serial_number;
  std::string pixel_format;
  double frame_rate;
  std::uint32_t width;
  std::uint32_t height;
  bool streaming;
};

// --- Interface ---------------------------------------------------------------

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
  virtual ~CameraGateway() = default;

  [[nodiscard]] virtual Expected<double> FeatureFloatGet(const std::string& name) = 0;

  // Setters request a value and report only success or failure: no automatic
  // readback, and no local validation against feature metadata.
  [[nodiscard]] virtual Expected<void> FeatureFloatSet(const std::string& name, double value) = 0;

  [[nodiscard]] virtual Expected<FloatInfo> FeatureFloatInfoGet(const std::string& name) = 0;

  [[nodiscard]] virtual Expected<std::string> FeatureEnumGet(const std::string& name) = 0;
  [[nodiscard]] virtual Expected<void> FeatureEnumSet(const std::string& name,
                                                      const std::string& value) = 0;
  [[nodiscard]] virtual Expected<EnumInfo> FeatureEnumInfoGet(const std::string& name) = 0;

  [[nodiscard]] virtual Expected<AccessMode> FeatureAccessModeGet(const std::string& name) = 0;

  // Returns the names of the features the camera defines. This is not an
  // availability check: a listed name may be currently unreadable or
  // unwritable, and current access state comes from FeatureAccessModeGet().
  // An empty list on success is a valid answer, not an error.
  [[nodiscard]] virtual Expected<std::vector<std::string>> FeaturesListGet() = 0;

  [[nodiscard]] virtual Expected<CameraStatus> CameraStatusGet() = 0;

  // Answers connectivity as a value: false is a successful negative answer. It
  // reports the driver's connection state and is not a precondition for any
  // other call.
  [[nodiscard]] virtual Expected<bool> ConnectionStatusGet() = 0;
};

}  // namespace venimapping::camera
