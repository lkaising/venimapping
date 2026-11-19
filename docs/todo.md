# TODO

Ideas parked for later. None of these are blocking.

## Camera gateway

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

## Upstream driver

Defects in `vimbax_ros2_driver` at `v1.0.1-beta1` (`296bdf6`) that the camera gateway
works around. Driver fork tag `v1.0.1-beta1-venimapping.1`, which the project now
builds, fixes both. Revisit each one if upstream fixes it.

- [x] **Add `FeatureFlags` to `FeatureInfo` once upstream reports them correctly.**
  `types/feature_info.hpp` leaves out the `flags` field of
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

1. Add types for:
   Expected<std::vector<std::string>> features_list_get();
   std::vector<std::string>

   Expected<std::vector<FeatureInfo>> feature_info_query();
   std::vector<FeatureInfo>

   Expected<std::vector<std::uint8_t>> feature_raw_get();
   std::vector<std::uint8_t>

2. Rename function for:
   Expected<bool> connection_status_get() -> Expected<bool> connection_status()
   Expected<CameraStatus> camera_status_get() -> Expected<CameraStatus> camera_status()
   Expected<std::vector<FeatureInfo>> feature_info_query() -> Expected<std::vector<FeatureInfo>> feature_info_list_get()

   Any others?

3. For `vimbax_response_conversion.hpp/cpp` tighten/shorten the namespacing of the arguments for the exposed functions. Function containing `vimbax_camera_msgs::srv::`
   `vimbax_camera_msgs::srv::` -> `something::` not sure on the name yet. Done via `namespace something = vimbax_camera_msgs::srv` or via alias. Not sure the correct choice here.
   Want to be careful about polluting the `venimapping::camera::gateway_support` namespace though.

4. Consider moving the nameless namespace inside of `vimbax_camera_gateway.cpp` to its own file/s inside of `/gateway_support`

5. Figure out a way to remove the extra or redunant C++ Standard Library headers inside of all of the files.
   Do this is a systematic way. Somehow. Where if you think of the project and the files includes connection tree, standard includes are only added when needed to compile,
   and at the furthest child "node" out in the include dependancy tree. Maybe write a script that can do this sort of recursive check for me automatically.

Stretch Goals

6. Maybe find a better name for `call_checked()`. Not the most clear. Maybe `call()` too?

7. Break up or organize the VimbaxCameraGateway into having helper objects. Where there might be a `ServiceCalls` helper object that handles `call` and `call_checked` and maybe
   threading too? And on top of that, there also being a set (number of helpers not sure yet) operation helpers that share `ServiceCalls` and these operation helpers would hold the
   method implementations grouped accordingly. And vimbax_camera_gateway.cpp contains construction and the public methods that forward to the helpers.

8. Come up with a more rebust CameraGateway object initilization "method". I.E. how currerntly, to use and create the class you must.
     - Spin up a thread.
     - Call `VimbaXCameraGateway::create()` scope outside the executor thread.
     - Run a bind / bind check via `bind_to_current_thread()`
     - Move the created object to a unique pointer `gateway`
     - Assign a `CameraGateway` address to the object on the heap.
   To me, while it makes sense, there seems to be a lot of friction here.
   Furthermore, the threading limitations comes off as primitive and restrictive. It would be nice for all of the threading logic and things of that nature to be handle automatically.
   Where creation of a CameraGateway/VimbaxCameraGateway object handles the threading for you, you do not need to care about other threadings going on, since CameraGateway is in its
   own thread land. And there is really only one object that owns one thread (shared reseource) since you do not want to create to different objects trying to talk to one camera. Or
   additional objects created simply point to the true first object, or something like that. Also is there are two threads, one address in each trying to call the camera, some sort of queing so that multithreads stay happy.
