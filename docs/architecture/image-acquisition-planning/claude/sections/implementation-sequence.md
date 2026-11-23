## Implementation sequence

The work lands in nine steps and one conditional step. Each step builds alone, passes its own exit check, and leaves no code that a later step must repair. The order follows the build rules in ic8.

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption. `[Q]` is an open question.

Paths are relative to `src/venimapping_camera/` unless the row names `src/venimapping_bringup/`.

### Order and dependencies

| Step | Name | Owner section | Needs step | Needs the rig |
|---|---|---|---|---|
| 1 | Bring-up parameters and files | bring-up | none | Yes, for the settings file and the exit check |
| 2 | Acquisition error domain | error-vocabulary | none | No |
| 3 | Frame API | data-plane | 2 | No |
| 4 | VimbaX frame source | data-plane | 3 | No |
| 5 | Controller core and fakes | control-plane, testing | 3 | No |
| 6 | Get image | control-plane | 5 | No |
| 7 | Silence, outage, and wedge recovery | control-plane | 6 | No |
| 8 | Feed probe and rig checks | testing | 1, 4, 7 | Yes |
| 9 | Hardware checks and the device stamp run | testing | 8 | Yes |
| 9a | Conditional executor split | data-plane, testing | 8 | Yes |

1. Steps 1 and 2 can land in either order.
2. Step 4 and steps 5 to 7 can run in parallel after step 3. They touch different files.
3. `[F]` The gateway already has every call that the controller needs (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:35-110`). No step changes the gateway (d2).

### Step 1. Bring-up parameters and files

Files:

- `src/venimapping_bringup/config/camera.yaml`
- `src/venimapping_bringup/config/camera_settings.xml`, new
- `src/venimapping_bringup/config/acquisition_profile.yaml`, new
- `src/venimapping_bringup/launch/camera.launch.py`
- `src/venimapping_bringup/CMakeLists.txt`
- `src/venimapping_bringup/package.xml`
- `src/venimapping_bringup/test/test_camera_config.py`, new

Work:

1. Make `camera_settings.xml` on the rig with the steps in the bring-up section.
2. Add the parameters, the launch arguments, and the profile file.
3. Add the pytest test.

Exit check:

1. `colcon build --packages-select venimapping_bringup` succeeds.
2. `colcon test --packages-select venimapping_bringup` passes.
3. On the rig, launch the driver. `ros2 param get /vimbax_camera/vimbax_camera use_ros_time` prints `True`.
4. `ros2 topic list` shows no topic that starts with `/vimbax_camera/image_raw/`.
5. CLI reads of the seven profile values match `acquisition_profile.yaml`.
6. `camera_gateway_probe` passes as before.

`[F]` No project code reads image stamps today (facts 1.1.1), so `use_ros_time: true` breaks nothing.

### Step 2. Acquisition error domain

Files:

- `include/venimapping_camera/types/error.hpp`
- `include/venimapping_camera/types/acquisition_error.hpp`, new
- `CMakeLists.txt`: an `if(BUILD_TESTING)` block with `find_package(ament_cmake_gtest REQUIRED)` and the target `test_acquisition_error`
- `test/acquisition_error_test.cpp`, new

Exit check:

1. `colcon build --packages-select venimapping_camera` succeeds with no new warning under `-Wall -Wextra -Wpedantic` (`src/venimapping_camera/CMakeLists.txt:14-16`).
2. `colcon test --packages-select venimapping_camera` runs `test_acquisition_error`, and it passes.
3. `camera_gateway_probe` builds with no source change.

This step is first among the C++ steps, because each later target returns these codes (ic8 rule 1).

### Step 3. Frame API

Files, owned by the data-plane section:

- `include/venimapping_camera/image_frame.hpp`, new
- `include/venimapping_camera/frame_source.hpp`, new
- `src/image_frame.cpp`, new
- `src/frame_support/frame_fanout.hpp`, `src/frame_support/frame_fanout.cpp`, new
- `CMakeLists.txt`: the library `venimapping_camera_frame_api`, its install and export lines, and the targets `test_image_frame` and `test_frame_fanout`
- `test/image_frame_test.cpp`, `test/frame_fanout_test.cpp`, new

Exit check:

1. The build succeeds without `sensor_msgs` in `package.xml` (ic8 rule 2).
2. `test_image_frame` and `test_frame_fanout` pass. The testing section lists their cases.
3. `git grep -n -E 'rclcpp|sensor_msgs' -- src/venimapping_camera/include/venimapping_camera/image_frame.hpp src/venimapping_camera/include/venimapping_camera/frame_source.hpp src/venimapping_camera/src/image_frame.cpp src/venimapping_camera/src/frame_support` prints nothing.
4. `test_frame_fanout` passes under ThreadSanitizer, with `-fsanitize=thread`.

### Step 4. VimbaX frame source

Files, owned by the data-plane section:

- `include/venimapping_camera/vimbax_frame_source.hpp`, new
- `src/vimbax_frame_source.cpp`, new
- `package.xml`: `<depend>sensor_msgs</depend>`
- `CMakeLists.txt`: `find_package(sensor_msgs REQUIRED)`, the library `venimapping_camera_vimbax_frame_source`, its export, `ament_export_dependencies(sensor_msgs)`, and the target `test_vimbax_frame_source`
- `test/vimbax_frame_source_test.cpp`, new

Exit check:

1. `colcon test` passes on a host with no camera and no driver. The adapter test uses its own publisher (ic7 item 7).
2. `ros2 pkg xml venimapping_camera` lists `sensor_msgs`.

### Step 5. Controller core and fakes

Files:

- `include/venimapping_camera/acquisition_controller.hpp`, new: `AcquisitionProfile`, `ControllerOptions`, `FeedOptions`, `StreamState`, `ControllerStatus`, `Feed`, and `AcquisitionController`
- `src/acquisition_controller.cpp`, new: the worker queue, leases, `feed_open`, `Feed`, the start sequence, the readback and corrective writes, the d19 recovery, and `shutdown`
- `src/acquisition_support/profile_readback.hpp`, `.cpp`, new
- `src/acquisition_support/stream_formats.hpp`, new
- `test/fakes/fake_frame_source.hpp`, `.cpp`, new
- `test/fakes/fake_camera_gateway.hpp`, `.cpp`, new
- `test/acquisition_controller_test.cpp`, new
- `CMakeLists.txt`: the library `venimapping_camera_acquisition`, which links only `venimapping_camera_gateway_api` and `venimapping_camera_frame_api`, and the target `test_acquisition_controller`

In this step, the header has no `get_image` and no `GetImageOptions`. Step 6 adds them. The worker tick does nothing until step 7. Later steps add declarations and change no existing signature.

Exit check:

1. `test_acquisition_controller` passes these cases: `ColdFeedOrder`, `SelectorBeforeMode`, `KeepsFramesBeforeReply`, `MatchTimeout`, `FormatRefusal`, `CorrectiveWriteOrder`, `ProfileMismatch`, `FloatTolerance`, `Busy` for feeds, `StartFailReconciled`, `WedgeOnStartTimeout`, `WedgeOnStopFailure`, `Shutdown`, and `FeedOutlivesController`.
2. The acquisition target builds with no ROS include path. A configure-time check reads the `LINK_LIBRARIES` property of `venimapping_camera_acquisition` and fails on `rclcpp`.
3. The suite passes under ThreadSanitizer and AddressSanitizer.

### Step 6. Get image

Files:

- `include/venimapping_camera/acquisition_controller.hpp`: `GetImageOptions` and `get_image`
- `src/acquisition_controller.cpp`: `get_image`, the caller-side deadline, the skip of frames with `receive_seq <= R`, and the worker release after a caller leaves
- `test/acquisition_controller_test.cpp`: new cases

Exit check:

1. These cases pass: `LeaseCount`, `Busy` for get image, `WarmFreshness`, `InFlightFrameSkipped`, `DeadlinePassed`, and `StopOutsideDeadline`.
2. All step 5 cases still pass.

### Step 7. Silence, outage, and wedge recovery

Files:

- `src/acquisition_controller.cpp`: the 100 ms tick, the silence threshold, `kOutage`, `kConnectionUnknown`, `kStalled`, the reconnect path, the wedge poll, the stop of a stream with no user, and linger
- `test/acquisition_controller_test.cpp`: new cases

Exit check:

1. These cases pass: `SilenceToOutage`, `ConnectionUnknown`, `ReconnectNewEpoch`, `ReconnectProfileChanged`, `ReconnectNoRestart`, `Stall`, `NoUserStreamStopped`, `WedgeCleared`, and `Linger`.
2. All earlier cases still pass.
3. The full controller suite runs in less than 30 s.

### Step 8. Feed probe and rig checks

Files:

- `src/camera_feed_probe.cpp`, new: the phase 1 composition root, in the ic4 start and stop order, with the modes `bringup`, `feed`, `load`, `rtt`, `get_image`, and `stamps`
- `CMakeLists.txt`: the executable `camera_feed_probe`, marked temporary, and its install line

Exit check, on the rig:

1. `mode:=bringup` passes all five steps.
2. `mode:=feed` gives 29 to 31 Hz with the counters in the testing section.
3. `mode:=load` gives 69 to 70.5 Hz.
4. `mode:=get_image` passes the cold and warm limits.
5. `mode:=rtt` gives two medians. The v2 document records them with the callback time and the match time (T12).

### Step 9. Hardware checks and the device stamp run

Files: none. The v2 document gets a results table.

Work:

1. Run the unplug, settings load, and outside reader checks.
2. Launch the driver with `use_ros_time:=false`. Run `mode:=stamps` at 30 Hz and at 69.7 Hz.
3. Run the wedge check last.

Exit check:

1. The unplug, wedge, and settings load checks pass their conditions.
2. The stamp results and the outside reader results are in the v2 document as input to L1 and L7.

### Step 9a. Conditional executor split

Run this step only if the `rtt` streaming median is more than 5 ms above the stopped median (d5 item 5).

Files:

- `src/camera_feed_probe.cpp`: a second node and a second `SingleThreadedExecutor` thread. The probe passes the second node to `VimbaXFrameSource::create`.

Exit check:

1. `mode:=rtt` gives a streaming median within 5 ms of the stopped median.
2. Steps 8 and 9 checks pass again.

`[F]` The adapter takes the node as an argument and uses its default callback group (ic2 adapter item 5). The split therefore changes only the composition root.

### What is not in phase 1

| Item | Entry | Trigger to start it |
|---|---|---|
| Software trigger get image, `kTriggerNoFrame` | d23, d27 | Logan answers L4 with yes |
| `CameraInfo` pairing | d15 | A consumer needs intrinsics (R11) |
| `stamp_gap_frames` and `device_stamp_ns` | d12, d20 | L1, and the step 9 stamp run meets both d20 conditions |
| A ROS service for get image | d29 | Logan answers L2 with another process |
| Driver fork patches | d21 | Logan answers L3 |
