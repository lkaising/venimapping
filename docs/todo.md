# TODO

Ideas parked for later. None of these are blocking.

## Camera gateway

- [x] **Add dedicated types for collection results.**
  Give each collection its own type and header. Decide the names and
  representations when revisiting the API.
  - `features_list_get()` returns feature names (`std::vector<std::string>`).
  - `feature_info_query()` returns feature metadata (`std::vector<FeatureInfo>`).
  - `feature_raw_get()` returns raw feature bytes (`std::vector<std::uint8_t>`).

- [x] **Review gateway method names.**
  Use shorter names for the status queries and make the feature-info list result
  explicit. Consider these renames.
  - `connection_status_get()` → `connection_status()`
  - `camera_status_get()` → `camera_status()`
  - `feature_info_query()` → `feature_info_list_get()`
  - Also consider `features_list_get()` → `feature_list_get()` to match the
    naming pattern for list results.

- [x] **Shorten the response converter signatures.**
  Reduce the repeated `vimbax_camera_msgs::srv::` qualification in
  `vimbax_response_conversion.hpp` and `.cpp`. Compare a namespace alias with
  aliases for individual response types, and keep any alias narrowly scoped.

- [x] **Consider moving the file-local gateway helpers.**
  Explore moving the client creation, request construction, and wait helpers
  from the unnamed namespace in `vimbax_camera_gateway.cpp` into one new private
  `.hpp`/`.cpp` pair under `src/gateway_support/`.

- [x] **Audit all direct C++ includes bottom-up.**
  Report which can be removed together, verify that headers still compile
  independently, and confirm the combined result with a clean full-project build.

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

- [x] **Revisit the names of `call_checked()` and `call()`.**
  Rename `call_checked()` to `call_checking_driver_error()` so the name shows
  that it also inspects the driver's error field. Keep the name `call()`.

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
works around. Driver fork tag `v1.0.1-beta1-venimapping.1`, which the project now
builds, fixes both. Revisit each one if upstream fixes it.

- [x] **Add `FeatureFlags` to `FeatureInfo` once upstream reports them correctly.**
  `types/feature_info_list.hpp` leaves out the `flags` field of
  `vimbax_camera_msgs/msg/FeatureInfo` because its values are wrong.
  `VimbaXCamera::feature_info_query_list` in `vimbax_camera/src/vimbax_camera.cpp`
  (lines 1241 to 1249) derives every flag from `vmb_info.featureDataType` instead of
  `vmb_info.featureFlags`, so the booleans reflect the data type's bit pattern rather
  than the feature's access flags.
  - Until then, current access state comes from `feature_access_mode_get`.

- [x] **Remove `without_terminator` once upstream stops sending the C terminator.**
  `VmbCAPI::feature_string_get` in `vimbax_camera/src/loader/vmbc_api.cpp` (line 323)
  builds its result from `size_filled` bytes, a count that includes the terminating
  NUL, so every string feature value reaches a C++ client one character too long. The
  gateway strips that NUL in `feature_string_get` and in the four `CameraStatus` fields
  the driver reads the same way (`device_firmware_version`, `device_user_id`,
  `interface_id`, `transport_layer_id`).
  - `ros2 service call` does not show the NUL; a C++ client does.
