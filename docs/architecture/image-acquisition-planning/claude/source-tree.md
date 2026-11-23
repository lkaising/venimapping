## Source tree for the Claude sections

This list covers the files that the control-plane, error-vocabulary, bring-up, testing, and implementation-sequence sections add or change. The data-plane files are in `codex/source-tree.md`. All files stay in the two existing packages (d1).

`[F]` `venimapping_camera` installs each header under `include/` and no header under `src/` (`src/venimapping_camera/CMakeLists.txt:58-63`). Private headers for the controller therefore go under `src/acquisition_support/`, like the existing `src/gateway_support/`.

### `src/venimapping_camera`

| File | Change | Step | Purpose |
|---|---|---|---|
| `include/venimapping_camera/types/error.hpp` | Change | 2 | Add `ErrorDomain::kAcquisition = 2` and `Error::from_acquisition` |
| `include/venimapping_camera/types/acquisition_error.hpp` | New | 2 | `AcquisitionCode` 1 to 11, `acquisition_error`, `is_acquisition`, and `to_string` |
| `include/venimapping_camera/acquisition_controller.hpp` | New | 5, 6 | `AcquisitionProfile`, `ControllerOptions`, `FeedOptions`, `GetImageOptions`, `StreamState`, `ControllerStatus`, `Feed`, and `AcquisitionController` |
| `src/acquisition_controller.cpp` | New | 5, 6, 7 | The worker queue, leases, start sequence, get image, d19 recovery, silence and outage handling, and shutdown |
| `src/acquisition_support/profile_readback.hpp` | New | 5 | Private. Declares the readback, the comparison, and the corrective writes |
| `src/acquisition_support/profile_readback.cpp` | New | 5 | The eight readback calls and the five write groups in the d18 order |
| `src/acquisition_support/stream_formats.hpp` | New | 5 | Private. The driver gate formats that this camera offers, `Mono8` and `Mono12`, and their `significant_bits` |
| `src/camera_feed_probe.cpp` | New | 8 | Temporary. The phase 1 composition root and the rig check modes |
| `test/fakes/fake_frame_source.hpp` | New | 5 | `FakeFrameSource` over `FrameFanout`, with `inject` and `set_matched_publishers` |
| `test/fakes/fake_frame_source.cpp` | New | 5 | Mono8 test frames for `inject` |
| `test/fakes/fake_camera_gateway.hpp` | New | 5 | `FakeCameraGateway`, a scripted `CameraGateway` with a call log |
| `test/fakes/fake_camera_gateway.cpp` | New | 5 | The feature map, per-selector `TriggerMode`, stream state, and locks during a stream |
| `test/acquisition_error_test.cpp` | New | 2 | Fixed code numbers and the factory |
| `test/image_frame_test.cpp` | New | 3 | Layout checks, shared ownership, and lifetime |
| `test/frame_fanout_test.cpp` | New | 3 | Sequence, admission, epoch, queue, close, and thread rules |
| `test/acquisition_controller_test.cpp` | New | 5, 6, 7 | Controller cases against both fakes |
| `test/vimbax_frame_source_test.cpp` | New | 4 | Adapter over a RELIABLE test publisher, with no driver |
| `CMakeLists.txt` | Change | 2, 5, 8 | The `BUILD_TESTING` block and test targets, the `venimapping_camera_acquisition` library, and the `camera_feed_probe` executable |

### `src/venimapping_bringup`

| File | Change | Step | Purpose |
|---|---|---|---|
| `config/camera.yaml` | Change | 1 | Add `buffer_count`, `use_ros_time`, `use_sim_time`, and `image_raw.enable_pub_plugins` |
| `config/camera_settings.xml` | New | 1 | The phase 1 camera profile, saved on the rig, loaded by the driver on each open |
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
