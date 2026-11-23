## Source tree for the Claude sections

This list covers the files that the control-plane, error-vocabulary, bring-up, testing, and implementation-sequence sections add or change. The data-plane files are in `codex/source-tree.md`. All files stay in the two existing packages (d1).

`[F]` `venimapping_camera` installs each header under `include/` and no header under `src/` (`src/venimapping_camera/CMakeLists.txt:58-63`). Private headers for the controller therefore go under `src/acquisition_support/`, like the existing `src/gateway_support/`.

`[F]` The package installs and exports only the targets that an `install(TARGETS ... EXPORT export_${PROJECT_NAME})` call names (`src/venimapping_camera/CMakeLists.txt:65-74`). Each new library block therefore has its own install call. The implementation sequence gives the CMake layout.

### `src/venimapping_camera`

| File | Change | Step | Purpose |
|---|---|---|---|
| `include/venimapping_camera/types/error.hpp` | Change | 2 | Add `ErrorDomain::kAcquisition = 2` and `Error::from_acquisition` |
| `include/venimapping_camera/types/acquisition_error.hpp` | New | 2 | `AcquisitionCode` 1 to 11, `acquisition_error`, `is_acquisition`, and `to_string` |
| `include/venimapping_camera/acquisition_controller.hpp` | New | 5, 6 | `AcquisitionProfile`, `ControllerOptions`, `FeedOptions` with `deadline`, `GetImageOptions`, `StreamState` with `kFaulted`, `ControllerStatus` with `last_reconciliation`, `Feed`, and `AcquisitionController` |
| `src/acquisition_controller.cpp` | New | 5, 6, 7 | The lifecycle value and the join rule, the worker queue, the request state with a check before each gateway call, the lease set, the `Feed` move rules, the start sequence, get image with the acceptance check, d19 recovery, the wedge confirmation stop, the state rules for new requests, silence and outage handling, `start`, and `shutdown` |
| `src/acquisition_support/lease_link.hpp` | New | 5 | Private. `LeaseLink`: the mutex, the non-owning subscription pointer, the `released` flag, and the shared request queue. The request state with its outcome and deadline |
| `src/acquisition_support/profile_readback.hpp` | New | 5 | Private. Declares the readback, the comparison, and the corrective writes, each with a check callback before each call |
| `src/acquisition_support/profile_readback.cpp` | New | 5 | The eight readback calls and the five write groups in the d18 order, each with `FeatureModule::kRemoteDevice` |
| `src/acquisition_support/stream_formats.hpp` | New | 5 | Private. The driver gate formats that this camera offers, `Mono8` and `Mono12`, and their `significant_bits` |
| `src/camera_feed_probe.cpp` | New | 8 | Temporary. The phase 1 composition root and the rig check modes, also `wedge` |
| `test/fakes/test_clock.hpp` | New | 3 | `TestClock`: real steady time, manual realtime, and a hold point in `steady_now()` |
| `test/fakes/test_clock.cpp` | New | 3 | The hold and release logic |
| `test/fakes/fake_frame_source.hpp` | New | 5 | `FakeFrameSource` over `FrameFanout`, with `inject`, `set_matched_publishers`, `subscriptions_opened`, `subscription_stats`, the take hooks, and `on_open_admission` |
| `test/fakes/fake_frame_source.cpp` | New | 5 | Mono8 test frames for `inject`, and the subscription decorator that keeps stats, counts and holds `take` calls, and records the taken sequences |
| `test/fakes/fake_camera_gateway.hpp` | New | 5 | `FakeCameraGateway`, a scripted `CameraGateway` with a call log |
| `test/fakes/fake_camera_gateway.cpp` | New | 5 | The feature map, per-selector `TriggerMode`, the four stream states, the module check, and locks during a stream |
| `test/acquisition_error_test.cpp` | New | 2 | Fixed code numbers and the factory |
| `test/image_frame_test.cpp` | New | 3 | Layout checks, shared ownership, and lifetime |
| `test/frame_fanout_test.cpp` | New | 3 | Sequence, admission, epoch, queue, close, hold, duration, and thread rules |
| `test/acquisition_controller_test.cpp` | New | 5, 6, 7 | Controller cases against both fakes. The testing section gives the step of each case |
| `test/vimbax_frame_source_test.cpp` | New | 4 | Adapter over a RELIABLE test publisher, with no driver. One intra-process case for the pixel address |
| `test/installed_consumer/CMakeLists.txt` | New | 5 | A separate project that finds the installed package and links `venimapping_camera::venimapping_camera_acquisition` |
| `test/installed_consumer/main.cpp` | New | 5 | Calls `AcquisitionController::create` with stubs, so the link needs the library |
| `CMakeLists.txt` | Change | 2, 5, 8 | The `BUILD_TESTING` lines and test targets, the `venimapping_camera_acquisition` block with its own install and export call, and the `camera_feed_probe` executable |

### `src/venimapping_bringup`

| File | Change | Step | Purpose |
|---|---|---|---|
| `config/camera.yaml` | Change | 1 | Add `buffer_count`, `use_ros_time`, `use_sim_time`, and `image_raw.enable_pub_plugins` |
| `config/camera_settings.xml` | New | 1 | The phase 1 camera profile, saved on the rig with no-LUT persistence for the remote device, local device, and stream modules. The driver loads it on each open |
| `config/acquisition_profile.yaml` | New | 1 | The values that the controller reads back, as parameters of the application node |
| `launch/camera.launch.py` | Change | 1 | Add the `use_ros_time` and `settings_file` launch arguments and pass them after `params_file` |
| `CMakeLists.txt` | Change | 1 | Add the pytest test under `BUILD_TESTING` |
| `package.xml` | Change | 1 | Add `test_depend` on `ament_cmake_pytest` and `python3-yaml` |
| `test/test_camera_config.py` | New | 1 | Checks the parameter values and the launch arguments with no camera |

### Files that do not change

| File | Reason |
|---|---|
| `include/venimapping_camera/camera_gateway.hpp` | The gateway already has the stream and feature calls (d2) |
| `include/venimapping_camera/vimbax_camera_gateway.hpp`, `src/vimbax_camera_gateway.cpp` | Same reason. `bind_to_current_thread` reaches the worker through `WorkerInit` |
| `src/gateway_support/gateway_errors.hpp` | Gateway diagnostics stay private (d6) |
| `src/camera_gateway_probe.cpp` | Stays as the gateway probe |
| `scripts/env.sh` | No project Cyclone DDS file in phase 1 (ic6 item 4) |
