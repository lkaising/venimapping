# TODO

Ideas parked for later. None of these are blocking.

## Camera gateway

- [ ] **Explore introducing an `Unexpected` type.**
  Add `using Unexpected = std::unexpected<Error>;` to `types/expected.hpp` and have
  `detail::gateway_error` and `detail::driver_error` return it, so call sites can
  write `return detail::gateway_error(...);` without wrapping it in `std::unexpected(...)`.
  - Mark both helpers `[[nodiscard]]`. `std::unexpected<Error>` does not
    inherit `Error`'s `[[nodiscard]]`.
  - Delete the commented-out `make_driver_error` / `make_gateway_error` block in
    `types/expected.hpp` instead of moving it. It takes raw `int32_t` codes, which would
    lose the typed `GatewayDiagnostic`.
  - Watch out for lambda return types in `and_then` / `or_else` / `transform_error`.

- [ ] **Consider removing the asserts in `types/error.hpp`.**
  `Error::from_driver` and `Error::from_gateway` assert that `code != 0`. The
  internal callers already guarantee this, but the factories are public, so test
  fakes and future layers could still pass 0. If they are removed, also drop
  `#include <cassert>`.

## Upstream driver

Defects in `vimbax_ros2_driver` at `v1.0.1-beta1` (`296bdf6`) that the camera gateway
works around. Revisit each one if upstream fixes it.

- [ ] **Add `FeatureFlags` to `FeatureInfo` once upstream reports them correctly.**
  `types/feature_info.hpp` leaves out the `flags` field of
  `vimbax_camera_msgs/msg/FeatureInfo` because its values are wrong.
  `VimbaXCamera::feature_info_query_list` in `vimbax_camera/src/vimbax_camera.cpp`
  (lines 1241 to 1249) derives every flag from `vmb_info.featureDataType` instead of
  `vmb_info.featureFlags`, so the booleans reflect the data type's bit pattern rather
  than the feature's access flags.
  - Until then, current access state comes from `feature_access_mode_get`.
