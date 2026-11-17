// -----------------------------------------------------------------------------
//  Filename: error.hpp
//
//  Purpose:  Defines the error type returned by the camera layers.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <cassert>
#include <cstdint>
#include <string>
#include <utility>

namespace venimapping::camera {

enum class ErrorDomain : std::uint8_t {
  kDriver = 0,
  kGateway = 1,
};

class [[nodiscard]] Error final {
 public:
  [[nodiscard]] static constexpr Error from_driver(std::int32_t code, std::string text) noexcept
  {
    assert(code != 0 && "a driver error code must be nonzero");
    return Error{ErrorDomain::kDriver, code, std::move(text)};
  }

  [[nodiscard]] static constexpr Error from_gateway(std::int32_t code, std::string text) noexcept
  {
    assert(code != 0 && "a gateway error code must be nonzero");
    return Error{ErrorDomain::kGateway, code, std::move(text)};
  }

  [[nodiscard]] constexpr ErrorDomain domain() const noexcept { return domain_; }
  [[nodiscard]] constexpr std::int32_t code() const noexcept { return code_; }
  [[nodiscard]] constexpr const std::string& text() const noexcept { return text_; }

 private:
  constexpr Error(ErrorDomain domain, std::int32_t code, std::string text) noexcept
      : domain_{domain}, code_{code}, text_{std::move(text)}
  {
  }

  ErrorDomain domain_;
  std::int32_t code_;
  std::string text_;
};

}  // namespace venimapping::camera
