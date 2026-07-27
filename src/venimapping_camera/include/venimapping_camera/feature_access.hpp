// -----------------------------------------------------------------------------
//  Filename: feature_access.hpp
//
//  Purpose:  Declares the ROS-independent camera feature-access contract and
//            the result types it returns.
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
//
// Field names follow the driver wire field names they are populated from,
// except where noted per field. The full mapping tables live in Section 9.2 of
// the Stage 1 specification and at the conversion sites in the gateway.
//
// Evolution: these are aggregates, so later fields shall be appended, never
// inserted or reordered, and tests and fakes should construct them with
// designated initializers (whose designator order must follow declaration
// order).

// Float feature metadata.
struct FloatInfo {
  double min;
  double max;
  double inc;          // meaningful only when inc_available is true
  bool inc_available;  // from wire inc_available
};

// Current access state of a feature. Readability and writability may change
// with streaming and other feature values; this layer reports them and does
// not interpret them.
struct AccessMode {
  bool readable;  // from wire is_readable
  bool writable;  // from wire is_writeable -- note the driver spelling
};

// Enum feature metadata.
struct EnumInfo {
  std::vector<std::string> possible_values;   // all options the feature defines
  std::vector<std::string> available_values;  // subset selectable right now
};

// The consumed subset of the driver's camera status (Section 8.4).
struct CameraStatus {
  std::string model_name;
  std::string device_serial_number;
  std::string pixel_format;
  double frame_rate;
  std::uint32_t width;   // wire type retained
  std::uint32_t height;  // wire type retained
  bool streaming;
};

// --- Interface ---------------------------------------------------------------

// The feature operations available to VeniMapping layers, plus the minimal
// connection and status context needed to use features safely. Acquisition,
// streaming, and trigger operations are deliberately outside this contract
// (Sections 6.2, 6.8).
//
// Implementations return metadata and current access information; they do not
// decide how the application responds to it. Clamping, fallback selection,
// retry, and configuration ordering belong to future layers (Section 6.6).
//
// Methods are intentionally non-const: they perform I/O against external
// mutable state, and concrete implementations mutate internal client state.
class FeatureAccess {
 public:
  virtual ~FeatureAccess() = default;

  // Returns the current value of a float feature.
  virtual Expected<double> GetFloat(const std::string& name) = 0;

  // Requests a float value; reports only success or failure, with no
  // automatic readback.
  virtual Expected<void> SetFloat(const std::string& name, double value) = 0;

  // Returns float feature metadata. The layer never clamps, rejects, or
  // substitutes values based on it.
  virtual Expected<FloatInfo> GetFloatInfo(const std::string& name) = 0;

  // Returns the current access state of a feature.
  virtual Expected<AccessMode> GetAccessMode(const std::string& name) = 0;

  // Answers existence as a value: true and false are both affirmative answers
  // about a camera known present at the time of the query. Inability to
  // determine existence is an error, never false.
  virtual Expected<bool> FeatureExists(const std::string& name) = 0;

  // Returns the current option of an enum feature.
  virtual Expected<std::string> GetEnum(const std::string& name) = 0;

  // Requests an enum option; reports only success or failure, with no
  // automatic readback and no local validation against EnumInfo.
  virtual Expected<void> SetEnum(const std::string& name, const std::string& option) = 0;

  // Returns enum feature metadata. The layer never selects a fallback option
  // based on it.
  virtual Expected<EnumInfo> GetEnumInfo(const std::string& name) = 0;

  // Returns the CameraStatus subset.
  virtual Expected<CameraStatus> GetStatus() = 0;

  // Answers connectivity as a value: false is a successful negative answer.
  virtual Expected<bool> Connected() = 0;
};

}  // namespace venimapping::camera
