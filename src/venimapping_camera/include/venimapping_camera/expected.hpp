// -----------------------------------------------------------------------------
//  Filename: expected.hpp
//
//  Purpose:  Defines the shared success/error vocabulary returned by the camera
//            gateway layers.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <version>

#if !defined(__cpp_lib_expected) || __cpp_lib_expected < 202211L
#error "venimapping_camera requires std::expected with monadic operations (__cpp_lib_expected >= 202211L)"
#endif

#include <cassert>
#include <cstdint>
#include <expected>
#include <string>

namespace venimapping::camera {

// Which layer defines and reports the meaning of a failure.
enum class ErrorDomain : std::uint8_t {
  kDriver,   // vimbax_ros2_driver reported it; code and text are its verbatim wire values
  kGateway,  // the gateway defined it; code is an implementation diagnostic
};

class Error {
 public:
  // Wraps a driver response error pair verbatim; nothing is translated or
  // classified.
  //
  // Precondition (debug-asserted): code != 0. A zero code means success, not
  // an Error.
  static Error FromDriver(std::int32_t code, std::string text)
  {
    assert(code != 0);
    return Error{ErrorDomain::kDriver, code, std::move(text)};
  }

  // Records a failure the gateway itself defines.
  //
  // Precondition (debug-asserted): diagnostic != 0.
  static Error FromGateway(std::int32_t diagnostic, std::string text)
  {
    assert(diagnostic != 0);
    return Error{ErrorDomain::kGateway, diagnostic, std::move(text)};
  }

  [[nodiscard]] ErrorDomain domain() const noexcept { return domain_; }  // NOLINT(readability-identifier-naming)

  // kDriver: the driver's VmbC code, verbatim.
  // kGateway: a non-contractual diagnostic identifier -- do not branch on it.
  [[nodiscard]] std::int32_t code() const noexcept { return code_; }  // NOLINT(readability-identifier-naming)

  // Diagnostic context. Format is not contractual.
  [[nodiscard]] const std::string& text() const noexcept { return text_; }  // NOLINT(readability-identifier-naming)

 private:
  Error(ErrorDomain domain, std::int32_t code, std::string text)
      : domain_{domain}, code_{code}, text_{std::move(text)} {}

  ErrorDomain domain_;
  std::int32_t code_;
  std::string text_;
};

template <typename T>
using Expected = std::expected<T, Error>;

}  // namespace venimapping::camera
