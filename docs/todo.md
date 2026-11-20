# TODO

Ideas parked for later. None of these are blocking.

## Camera gateway

- [ ] **Remove comments and clean up formatting in the camera gateway.**
  The long-term goal is a codebase with no comments. Start with these files.
  - Review the comments in `types/feature_enum_info.hpp`,
    `types/feature_info_list.hpp`, `types/feature_module.hpp`, and
    `src/gateway_support/gateway_errors.hpp`.
  - Review the comments and the formatting in `camera_gateway.hpp` and
    `vimbax_camera_gateway.hpp`.

- [ ] **Explore introducing an `Unexpected` type.**
  Add `using Unexpected = std::unexpected<Error>;` to `types/expected.hpp` and have
  `detail::gateway_error` and `detail::driver_error` return it, so call sites can
  write `return detail::gateway_error(...);` without wrapping it in `std::unexpected(...)`.
  - Mark both helpers `[[nodiscard]]`. `std::unexpected<Error>` does not
    inherit `Error`'s `[[nodiscard]]`.
  - Don't revive the old `make_driver_error` / `make_gateway_error` helpers (removed from
    `types/expected.hpp`; see git history). They took raw `int32_t` codes, which would
    lose the typed `GatewayDiagnostic`.
  - Watch out for lambda return types in `and_then` / `or_else` / `transform_error`.

- [ ] **Consider removing the asserts in `types/error.hpp`.**
  `Error::from_driver` and `Error::from_gateway` assert that `code != 0`. The
  internal callers already guarantee this, but the factories are public, so test
  fakes and future layers could still pass 0. If they are removed, also drop
  `#include <cassert>`.

### Stretch goals

- [ ] **Explore gateway helper objects.**
  Consider a shared `ServiceCalls` helper for `call()` and
  `call_checking_driver_error()`, with separate helpers for groups of camera
  operations. The concrete gateway would construct the helpers and forward its
  public methods to them. The operation groups and where threading belongs are
  open questions.

- [ ] **Explore simpler gateway startup and thread ownership.**
  The probe starts the ROS executor on a separate thread, creates the gateway,
  and calls `bind_to_current_thread()` before using it through `CameraGateway&`.
  Explore reducing that setup by having one owner per camera manage threading
  and coordinate access. Shared handles and a queue to serialize requests from
  multiple threads are possibilities. This is the largest stretch goal.

## Upstream driver

Defects in `vimbax_ros2_driver` at `v1.0.1-beta1` (`296bdf6`) that the camera gateway
worked around. Driver fork tag `v1.0.1-beta1-venimapping.1`, which the project now
builds, fixes both. Revisit each one if upstream fixes it.

- [x] **Add `FeatureFlags` to `FeatureInfo` once upstream reports them correctly.**
  `types/feature_info_list.hpp` left out the `flags` field of
  `vimbax_camera_msgs/msg/FeatureInfo` because its values are wrong.
  `VimbaXCamera::feature_info_query_list` in `vimbax_camera/src/vimbax_camera.cpp`
  (lines 1241 to 1249) derives every flag from `vmb_info.featureDataType` instead of
  `vmb_info.featureFlags`, so the booleans reflect the data type's bit pattern rather
  than the feature's access flags.

- [x] **Remove `without_terminator` once upstream stops sending the C terminator.**
  `VmbCAPI::feature_string_get` in `vimbax_camera/src/loader/vmbc_api.cpp` (line 323)
  builds its result from `size_filled` bytes, a count that includes the terminating
  NUL, so every string feature value reaches a C++ client one character too long. The
  gateway stripped that NUL in `feature_string_get` and in the four `CameraStatus` fields
  the driver reads the same way (`device_firmware_version`, `device_user_id`,
  `interface_id`, `transport_layer_id`).
  - `ros2 service call` does not show the NUL; a C++ client does.
