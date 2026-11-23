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
2. Step 4 and steps 5 to 7 can run in parallel after step 3. Both step 4 and step 5 edit `CMakeLists.txt`. "CMake layout" gives the rule that joins them.
3. `[F]` The gateway already has every call that the controller needs (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:35-110`). No step changes the gateway (d2).
4. Each controller test runs first in the step that the testing section names in its step column. A test that calls `get_image` is never in the step 5 list, because step 6 adds `get_image`.

### CMake layout

`[F]` Today, one `install(TARGETS ...)` call installs and exports both libraries into `export_${PROJECT_NAME}`, and `ament_export_targets` exports that set (`src/venimapping_camera/CMakeLists.txt:65-74`). A target that no `install(TARGETS ... EXPORT ...)` call names is not in the installed package.

Rules for steps 2 to 8:

1. Each step adds one labeled block, like the existing `# --- venimapping_camera_vimbax_gateway ---` block (`src/venimapping_camera/CMakeLists.txt:32-48`).
2. A library block has its own `install(TARGETS <target> EXPORT export_${PROJECT_NAME} ARCHIVE DESTINATION lib LIBRARY DESTINATION lib RUNTIME DESTINATION bin)` call. CMake accepts several calls with one export set.
3. A block adds its test targets inside its own `if(BUILD_TESTING)` lines. Step 2 adds `find_package(ament_cmake_gtest REQUIRED)` one time.
4. The shared `install(TARGETS ...)` call and the `ament_export_targets` line do not change.
5. Only step 4 edits `ament_export_dependencies`, to add `sensor_msgs`.
6. Steps 4 and 5 can merge in either order. The step that merges second rebases on the first. With rules 1 to 5, the only conflict is the insertion point of the two blocks.

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

Exit check. The feed probe comes in step 8, so this check uses the CLI. It does the bring-up part A and the CLI form of part B.

1. `colcon build --packages-select venimapping_bringup` succeeds.
2. `colcon test --packages-select venimapping_bringup` passes.
3. On the rig, do part A of the bring-up rig check, steps 1 to 16. Each init wait ends with status 0 before the `grep` or the CLI step that follows it. After its init wait, the control launch log has the failed-load line. The part A readback before the reopen shows 10000.0 and 20.0. After the init wait on `driver_b.log`, `grep -F 'Loading settings from file' driver_a.log driver_b.log` prints nothing.
4. `ros2 param get /vimbax_camera/vimbax_camera use_ros_time` prints `True`.
5. `ros2 param get /vimbax_camera/vimbax_camera settings_file` prints the installed path of `camera_settings.xml`. The file exists at that path.
6. `ros2 param get /vimbax_camera/vimbax_camera image_raw.enable_pub_plugins` prints only `image_transport/raw`.
7. `ros2 topic info /vimbax_camera/image_raw` prints `Publisher count: 1`.
8. `ros2 topic list` shows no topic that starts with `/vimbax_camera/image_raw/`.
9. CLI reads of the seven profile values match `acquisition_profile.yaml`. Write `TriggerSelector` `FrameStart` before the `TriggerMode` read. After part A, a match proves that the file set `ExposureTime` and `AcquisitionFrameRate`.
10. `camera_gateway_probe` passes as before.

Exit checks 4 to 10 run on the driver from part A step 13, after its init wait.

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

This step is first among the C++ steps, because each later target returns these codes (ic8 rule 1). The headers belong to the existing INTERFACE target, which the shared install call already exports.

### Step 3. Frame API

Files, owned by the data-plane section:

- `include/venimapping_camera/image_frame.hpp`, new
- `include/venimapping_camera/frame_source.hpp`, new
- `src/image_frame.cpp`, new
- `src/frame_support/frame_fanout.hpp`, `src/frame_support/frame_fanout.cpp`, new
- `CMakeLists.txt`: the block for `venimapping_camera_frame_api`, with its install and export call, and the targets `test_image_frame` and `test_frame_fanout`
- `test/fakes/test_clock.hpp`, `.cpp`, new
- `test/image_frame_test.cpp`, `test/frame_fanout_test.cpp`, new

Exit check:

1. The build succeeds without `sensor_msgs` in `package.xml` (ic8 rule 2).
2. `test_image_frame` and `test_frame_fanout` pass. The testing section lists their cases.
3. `git grep -n -E 'rclcpp|sensor_msgs' -- src/venimapping_camera/include/venimapping_camera/image_frame.hpp src/venimapping_camera/include/venimapping_camera/frame_source.hpp src/venimapping_camera/src/image_frame.cpp src/venimapping_camera/src/frame_support` prints nothing.
4. `test_frame_fanout` passes under ThreadSanitizer, with `-fsanitize=thread`.

`TestClock` lands here, because `test_frame_fanout` needs it. Step 5 uses it again.

### Step 4. VimbaX frame source

Files, owned by the data-plane section:

- `include/venimapping_camera/vimbax_frame_source.hpp`, new
- `src/vimbax_frame_source.cpp`, new
- `package.xml`: `<depend>sensor_msgs</depend>`
- `CMakeLists.txt`: `find_package(sensor_msgs REQUIRED)`, the block for `venimapping_camera_vimbax_frame_source` with its install and export call, `sensor_msgs` in `ament_export_dependencies`, and the target `test_vimbax_frame_source`
- `test/vimbax_frame_source_test.cpp`, new

Exit check:

1. `colcon test` passes on a host with no camera and no driver. The adapter test uses its own publisher (ic7 item 7).
2. `ros2 pkg xml venimapping_camera` lists `sensor_msgs`.

### Step 5. Controller core and fakes

Files:

- `include/venimapping_camera/acquisition_controller.hpp`, new: `AcquisitionProfile`, `ControllerOptions`, `FeedOptions` with `deadline`, `StreamState`, `ControllerStatus`, `Feed`, and `AcquisitionController`
- `src/acquisition_controller.cpp`, new: the lifecycle value with its transition table, the join owner and its `kStopped` transition, the stop wait, the stop request in the queue, the worker queue, the request state and its check points before each gateway call, the lease set, `feed_open`, `Feed` with its move rules, the start sequence, the readback and corrective writes, the d19 recovery, `start`, and `shutdown`
- `src/acquisition_support/lease_link.hpp`, new
- `src/acquisition_support/profile_readback.hpp`, `.cpp`, new
- `src/acquisition_support/stream_formats.hpp`, new
- `test/fakes/fake_frame_source.hpp`, `.cpp`, new, with the take hooks and `on_open_admission`
- `test/fakes/fake_camera_gateway.hpp`, `.cpp`, new, with a call log entry at the start of each call
- `test/acquisition_controller_test.cpp`, new, with `WorkerExitMark`
- `test/installed_consumer/CMakeLists.txt`, `main.cpp`, new
- `CMakeLists.txt`: the block for `venimapping_camera_acquisition`, which links only `venimapping_camera_gateway_api` and `venimapping_camera_frame_api`. The block has its own `install(TARGETS venimapping_camera_acquisition EXPORT export_${PROJECT_NAME} ...)` call and the target `test_acquisition_controller`

In this step, the header has no `get_image` and no `GetImageOptions`. Step 6 adds them. The worker tick does nothing until step 7. Later steps add declarations and change no existing signature.

`test/installed_consumer/` is a separate CMake project. It is not part of the package build. Its `CMakeLists.txt` calls `find_package(venimapping_camera REQUIRED)` and links `venimapping_camera::venimapping_camera_acquisition`. Its `main.cpp` calls `AcquisitionController::create` with a stub gateway and a stub source, so the link needs the library symbols.

Exit check:

1. `test_acquisition_controller` passes these cases, each with `feed_open` only:
   1. Start sequence: `ColdFeedOrder`, `SelectorBeforeMode`, `RemoteDeviceModule`, `KeepsFramesBeforeReply`, `MatchTimeout`, `FormatRefusal`, `FormatCorrectionBits`, `WriteNeedsConfirmedStop`, `CorrectiveWriteOrder`, `WriteErrorReadbackDecides`, `ProfileMismatch`, and `FloatTolerance`.
   2. Leases and deadlines: `Busy` for feeds, `FeedOpenDeadline`, `ExpiredDuringReadback`, and `ExpiredBeforeStart`.
   3. Failure recovery: `StartFailReconciled`, `FirstErrorMinus15`, `WedgeOnStartTimeout`, and `WedgeOnStopFailure`.
   4. Lifecycle and ownership: `QueuedBeforeStart`, `InitFailure`, `ShutdownFromInit`, `ShutdownBeforeStart`, `StartShutdownOverlap`, `InitFailureWithShutdown`, `ShutdownFromInitWithWaiter`, `Shutdown`, `DestroyWithPendingRequest`, `FeedOutlivesController`, `FeedDestroyDuringShutdown`, and `FeedMoveAssignIntoLive`.
2. The acquisition target builds with no ROS include path. A configure-time check reads the `LINK_LIBRARIES` property of `venimapping_camera_acquisition` and fails on `rclcpp`.
3. The suite passes under ThreadSanitizer and AddressSanitizer.
4. After `colcon build`, source `install/setup.bash`. Then configure and build `test/installed_consumer` into a temporary build directory. The build links with no undefined symbol.

Old behavior for check 4: no `install(TARGETS ...)` call names the acquisition target, so `find_package` gives no imported target, and the configure step fails.

### Step 6. Get image

Files:

- `include/venimapping_camera/acquisition_controller.hpp`: `GetImageOptions` and `get_image`
- `src/acquisition_controller.cpp`: `get_image`, the caller-side take loop with the deadline check before each `take` and at frame acceptance, the skip of frames with `receive_seq <= R`, and the worker release of an undelivered `Feed`
- `test/acquisition_controller_test.cpp`: new cases

Exit check:

1. These cases pass: `LeaseCount`, `Busy` for get image, `WarmFreshness`, `InFlightFrameSkipped`, `FrameAfterDeadlineRejected`, `DeadlinePassed`, `ExpiredInQueue`, `ExpiredDuringMatch`, `StopOutsideDeadline`, `ShutdownWakesGetImage`, and `FeedCloseThenDestroy`.
2. All step 5 cases still pass.

### Step 7. Silence, outage, and wedge recovery

Files:

- `src/acquisition_controller.cpp`: the 100 ms tick, the silence threshold, `kOutage`, `kConnectionUnknown`, `kStalled`, `kFaulted`, the state rules for new requests, the reconnect path, the wedge poll and the one confirmation stop for each change signal, the stop of a stream with no user, and linger
- `test/acquisition_controller_test.cpp`: new cases

Exit check:

1. These cases pass: `StartFailClearsQueue`, `ConsumerDuringFailingStart`, `NoUserStopFails`, `WedgeCleared`, `WedgePollErrorKeepsWedge`, `WedgeConfirmMinus3`, `SilenceToOutage`, `ConnectionUnknown`, `RequestDuringOutage`, `ReconnectNewEpoch`, `ReconnectProfileChanged`, `ReconnectNoRestart`, `Stall`, `FaultedRetry`, `NoUserStreamStopped`, and `Linger`.
2. All earlier cases still pass.
3. The full controller suite runs in less than 30 s.

### Step 8. Feed probe and rig checks

Files:

- `src/camera_feed_probe.cpp`, new: the phase 1 composition root, in the ic4 start and stop order, with the modes `bringup`, `feed`, `load`, `rtt`, `get_image`, `stamps`, and `wedge`
- `CMakeLists.txt`: the executable `camera_feed_probe`, marked temporary, and its install line, like `camera_gateway_probe` (`src/venimapping_camera/CMakeLists.txt:71-72`)

Exit check, on the rig, with the driver on the default launch arguments:

1. Do part A of the bring-up rig check, with each init wait. Then `mode:=bringup` passes all nine steps of part B.
2. `mode:=feed` gives 29 to 31 Hz with the counters in the testing section.
3. `mode:=load` gives 69 to 70.5 Hz.
4. `mode:=get_image` passes the cold and warm limits.
5. `mode:=rtt` gives two medians. The v2 document records them with the callback time and the match time (T12).

### Step 9. Hardware checks and the device stamp run

Files: none. The v2 document gets a results table.

Work, in this order:

1. Run the unplug check and the settings load check, with host stamps. The settings load check runs the init wait before its `grep`.
2. Relaunch the driver with `use_ros_time:=false`, with the console output in a file. Run the outside reader and `mode:=stamps` together, at 30 Hz and at 69.7 Hz.
3. Relaunch the driver with the default arguments. Make sure that `use_ros_time` reads `True`.
4. Run the wedge check last, with `mode:=wedge`.

Exit check:

1. The unplug, settings load, and wedge checks pass their conditions. If the rig cannot restore `Mono8` while wedged, the report says so, and the tier 1 wedge tests are the evidence.
2. The stamp results, with the gap rules, and the outside reader results are in the v2 document as input to L1 and L7. An inconclusive or ambiguous result is recorded as inconclusive, with the item that caused it.

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
