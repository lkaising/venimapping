# Reconciled facts for image acquisition

This file joins `claude/trace.md` and `codex/trace.md` into one set of facts. The positions tasks use it as their common base.

## How to read this file

1. Both traces cite project checkpoint `6247955`. The task checkpoint is `67dd41e`. Between the two commits, only four planning files changed (`git diff --stat 6247955 67dd41e852`). All project citations are therefore valid at `67dd41e`.
2. Citation forms:
   - `path:line` is a path from the project worktree root.
   - `driver:path:line` is a path from the driver root `vimbax_ros2_driver/`.
   - `ros:path:line` is a path from the ROS 2 Jazzy source root `ros2-jazzy/src/`. The Claude trace calls this prefix `ros:` and the Codex trace calls it `jazzy:`.
3. Labels:
   - `[F]` is a fact with a citation.
   - `[A]` is a working assumption. It is cheap to reverse.
   - `[Q]` is an open question.
4. Trace tags: `C` is the Claude trace. `X` is the Codex trace. `K` is a coordinator check of the source.
5. Section 2 settles each disagreement. A fact in section 1 that a settled conflict changed cites the conflict id, for example `X3`.

## 1. Agreed facts

### 1.1 Project side

1. `[F]` No project code receives pixels. No file under `src/` contains `image_raw` or `sensor_msgs` (K, grep at `67dd41e`). `venimapping_camera` does not depend on `sensor_msgs` (`src/venimapping_camera/package.xml:15-16`). C, X.
2. `[F]` `camera.launch.py` starts one process, `vimbax_camera/vimbax_camera_node`, with node name `vimbax_camera`. The namespace comes from `camera_namespace`, default `/vimbax_camera` (`src/venimapping_bringup/launch/camera.launch.py:19-41`). C, X.
3. `[F]` The node resolves as `/vimbax_camera/vimbax_camera`. Topics and services resolve under `/vimbax_camera` (X9). C, X.
4. `[F]` `camera.yaml` sets only `camera_id: "0GPF3"` and `autostream: 0` under the key `/**/vimbax_camera` (`src/venimapping_bringup/config/camera.yaml:9-12`). Bringup installs `config/` and `launch/` (`src/venimapping_bringup/CMakeLists.txt:14`). C, X.
5. `[F]` All other driver parameters keep their defaults. `buffer_count` is 7 (range 3 to 1000), `use_ros_time` is false, `command_feature_timeout` is 0, `settings_file` and `camera_info_url` are empty (`driver:vimbax_camera/src/vimbax_camera_node.cpp:276-305`, `:415-418`). C, X.
6. `[F]` `camera_id`, `settings_file`, `camera_frame_id`, and `camera_info_url` are read-only. `buffer_count`, `autostream`, `use_ros_time`, and `command_feature_timeout` can change at run time (`driver:vimbax_camera/src/vimbax_camera_node.cpp:278-305`, `:409-418`). C, X.
7. `[F]` The project README pins the driver fork tag `v1.0.1-beta1-venimapping.1` (`README.md:13-15`). `scripts/env.sh` names no driver version (`scripts/env.sh:26-31`). C, X.
8. `[F]` `env.sh` sets `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` only if the variable is unset and the package is installed (`scripts/env.sh:127-134`). C, X.
9. `[F]` `CameraGateway` is a ROS-free C++23 abstract class with 30 pure virtual methods. They cover connection, status, stream start and stop, settings, feature list and info, and each feature type (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:35-138`). C, X, K.
10. `[F]` The gateway contract states "no clamping, fallback, retry, readback, or validation" (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:24-26`). C, X.
11. `[F]` `VimbaXCameraGateway::create` takes a caller-owned `rclcpp::Node&`, a namespace, and one timeout for all calls. It returns `Expected` (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:55-61`). C, X.
12. `[F]` The gateway makes one service client for each driver service. Each name is the namespace plus a leaf (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:49-145`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:36-46`). C, X.
13. `[F]` Each call checks the bound thread, waits for the service, and waits for the reply against one steady-clock deadline (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:147-211`). C, X.
14. `[F]` On a deadline, the gateway removes the pending request and returns `kResponseTimeout`. A setter that times out can still have been applied (`src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:79-94`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-52`). C, X.
15. `[F]` A nonzero driver `error.code` becomes a driver-domain `Error` with code and text unchanged. Gateway diagnostics 1 to 5 are for logs and tests only (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:213-229`, `src/venimapping_camera/src/gateway_support/gateway_errors.hpp:15-22`). C, X.
16. `[F]` `Error` is in `types/error.hpp` and `Expected` is in `types/expected.hpp` (`src/venimapping_camera/include/venimapping_camera/types/error.hpp:17-49`, `src/venimapping_camera/include/venimapping_camera/types/expected.hpp:11-18`). C, X.
17. `[F]` The thread check detects misuse. It does not synchronize. If the bound thread also spins the node, each call times out (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-47`). C, X.
18. `[F]` `camera_gateway_probe` is the only executable and is marked temporary. Its main thread is the gateway worker. A second thread spins a `SingleThreadedExecutor` (`src/venimapping_camera/CMakeLists.txt:50-56`, `src/venimapping_camera/src/camera_gateway_probe.cpp:1011-1037`, `:1062-1065`). C, X.
19. `[F]` The probe defaults to `/vimbax_camera` and 2000 ms. With writes enabled, it saves, changes, reads back, and restores features and the stream state (`src/venimapping_camera/src/camera_gateway_probe.cpp:132-167`, `:632-653`, `:735-769`, `:929-953`). C, X.
20. `[F]` The probe returns early if a setter fails, so it does not guarantee that it restores the camera (`src/venimapping_camera/src/camera_gateway_probe.cpp:744-768`). X.
21. `[F]` `package.xml` declares `ament_cmake_gtest`. The build defines no test target (`src/venimapping_camera/package.xml:18`, `src/venimapping_camera/CMakeLists.txt:18-77`). C, X.
22. `[F]` Private headers under `src/gateway_support/` are not installed. Headers under `include/` are installed (`src/venimapping_camera/CMakeLists.txt:37-48`, `:58-63`). C, X.

### 1.2 Driver threads

1. `[F]` The driver runs a `MultiThreadedExecutor` (`driver:vimbax_camera/CMakeLists.txt:44-48`). C, X.
2. `[F]` Feature and status services are in Reentrant groups. Stream services share one MutuallyExclusive group. Settings services have their own MutuallyExclusive group (`driver:vimbax_camera/src/vimbax_camera_node.cpp:630-658`). C, X.
3. `[F]` A graph thread wakes on a graph change or every 50 ms. It runs autostream and the restart after a reconnect (`driver:vimbax_camera/src/vimbax_camera_node.cpp:579-628`). C, X.
4. `[F]` The SDK frame callback pushes only complete frames to a queue. One frame thread per stream pops each frame, transforms it, and calls the publish callback (`driver:vimbax_camera/src/vimbax_camera.cpp:458-482`, `:1724-1757`). C, X.
5. `[F]` A detached thread reopens the camera after a reconnect (`driver:vimbax_camera/src/vimbax_camera_node.cpp:556-568`). C, X.

### 1.3 Image publishing

1. `[F]` One `image_transport::CameraPublisher` publishes `image_raw` and `camera_info` as two messages with one header (`driver:vimbax_camera/src/vimbax_camera_node.cpp:350-364`, `:1620-1631`, `ros:ros-perception/image_common/image_transport/src/camera_publisher.cpp:123-137`). C, X.
2. `[F]` Publisher QoS is `rmw_qos_profile_default` with depth 10: RELIABLE, KEEP_LAST 10, VOLATILE. No parameter changes it (`driver:vimbax_camera/src/vimbax_camera_node.cpp:354-357`, `ros:ros2/rmw/rmw/include/rmw/qos_profiles.h:51-62`). C, X.
3. `[F]` A RELIABLE publisher matches RELIABLE and BEST_EFFORT subscribers (`ros:ros2/rmw_dds_common/rmw_dds_common/src/qos.cpp:114-124`). C, X.
4. `[F]` `image_transport` advertises one subtopic for each installed plugin, filtered by `image_raw.enable_pub_plugins`. Bringup does not set the filter (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:112-155`). C, X.
5. `[F]` The driver has no snapshot service. Pixels leave the driver only on `image_raw` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:660-1579`). C, X.
6. `[F]` The start gate allows Mono8, Mono12, Mono16, Bayer GR, RG, GB, BG at 8, 10, 12, and 16 bits, Rgb8, Bgr8, Yuv422_8, YCbCr422_8, and YCbCr422_8_CbYCrY (`driver:vimbax_camera/src/vimbax_camera.cpp:1621-1651`). C, X, K.
7. `[F]` The transform shifts Bayer 10-bit data left by 6 and Mono12 and Bayer 12-bit data left by 4 into a 16-bit encoding. The message does not record the shift (`driver:vimbax_camera/src/vimbax_camera.cpp:1781-1806`). C, X, K.
8. `[F]` Mono10 and Mono14 have shift branches, but the gate rejects both formats at start (`driver:vimbax_camera/src/vimbax_camera.cpp:1784-1800`, `:1621-1651`). C, X, K.
9. `[F]` At stream start, the driver reads `PayloadSize`, checks the gate, allocates `buffer_count` frames, and computes `step` once (`driver:vimbax_camera/src/vimbax_camera.cpp:416-456`, `:1712`). C, X.
10. `[F]` For each frame, the frame thread sets `encoding`, `width`, `height`, and `is_bigendian` from the SDK frame (`driver:vimbax_camera/src/vimbax_camera.cpp:1745-1757`). C, X.
11. `[F]` If the payload fits the alignment, the SDK writes into the message vector. If not, the frame thread copies or shifts the pixels (`driver:vimbax_camera/src/vimbax_camera.cpp:1695-1712`, `:1781-1806`). X, K.
12. `[F]` The callback logs a frame ID gap, sets the header, publishes, and then requeues the buffer (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1638`). C, X.
13. `[F]` CycloneDDS loans only self-contained types. `sensor_msgs/Image` has unbounded fields, so each subscriber gets a deserialized heap copy (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:2479`, `:2984`). C, X.
14. `[A]` A RELIABLE writer can block in `publish` on a slow reader. The buffer then returns late to the SDK, and the SDK drops frames. `buffer_count` and subscriber QoS depend on this. Open question T9. C only.

### 1.4 Stream start and stop

| Call | State before | Result | Evidence |
|---|---|---|---|
| `stream_start` | `kStopped` | Start, then `kActive`, or an error | `driver:vimbax_camera/src/vimbax_camera.cpp:414-515` |
| `stream_start` | `kActive` | Success, no effect | `driver:vimbax_camera/src/vimbax_camera.cpp:516-517` |
| `stream_start` | `kStarting` or `kStopping` | `VmbErrorInvalidCall` (-15) | `driver:vimbax_camera/src/vimbax_camera.cpp:518-519` |
| `stream_stop` | `kActive` | Stop, then `kStopped`, or an error | `driver:vimbax_camera/src/vimbax_camera.cpp:525-581` |
| `stream_stop` | `kStopped` | Success, no effect | `driver:vimbax_camera/src/vimbax_camera.cpp:582-583` |
| `stream_stop` | `kStarting` or `kStopping` | -15 | `driver:vimbax_camera/src/vimbax_camera.cpp:584-585` |
| either | camera unavailable | `VmbErrorNotFound` (-3) | `driver:vimbax_camera/src/vimbax_camera_node.cpp:1551-1553`, `:1571-1573` |

1. `[F]` Each error return in `start_streaming` leaves the state at `kStarting`. Examples are a `PayloadSize` failure, a gate failure (-18), and a `CaptureStart` failure (`driver:vimbax_camera/src/vimbax_camera.cpp:416-510`). C, X.
2. `[F]` Each error return in `stop_streaming` leaves the state at `kStopping` (`driver:vimbax_camera/src/vimbax_camera.cpp:527-575`). X, K.
3. `[F]` After such a failure, `stream_start` and `stream_stop` both return -15 and `status.streaming` reports true (`driver:vimbax_camera/src/vimbax_camera.cpp:1508-1513`). C, K.
4. `[F]` No service resets the state. A new `VimbaXCamera` object from a reopen has a new state (`driver:vimbax_camera/src/vimbax_camera_node.cpp:371`). C, K.
5. `[F]` A start failure after line 458 leaves the frame thread running and the frames announced (`driver:vimbax_camera/src/vimbax_camera.cpp:458-510`). K.
6. `[F]` Start runs `AcquisitionStart` and stop runs `AcquisitionStop` through the command poll. Each successful call takes at least 100 ms (`driver:vimbax_camera/src/vimbax_camera.cpp:503`, `:529`, `:682`). C, X.
7. `[F]` `stream_stop` joins the frame thread and drops frames still in its queue (`driver:vimbax_camera/src/vimbax_camera.cpp:547-559`). C, X.
8. `[F]` Start and stop serialize. The services share one MutuallyExclusive group, and the node functions lock `stream_state_mutex_` (X1). C, X.
9. `[F]` With `autostream: 1`, the graph thread starts the stream when the subscriber count rises and stops it when the count reaches 0. It ignores both results (`driver:vimbax_camera/src/vimbax_camera_node.cpp:597-619`). C, X.
10. `[F]` The condition at `driver:vimbax_camera/src/vimbax_camera_node.cpp:604` is always true in its branch. A count rise undoes an explicit `stream_stop` (X2). C, X.
11. `[F]` The count is the larger of the image subscriber sum over all transports and the `camera_info` count (`ros:ros-perception/image_common/image_transport/src/camera_publisher.cpp:97-105`, `ros:ros-perception/image_common/image_transport/src/publisher.cpp:63-69`). C, X.
12. `[F]` With `autostream: 0`, only the `stream_start` service and the reconnect restart start the stream (`driver:vimbax_camera/src/vimbax_camera_node.cpp:588-593`, `:1538-1554`). C, X.
13. `[F]` The driver refuses a `buffer_count` change while `is_streaming()` is true. That includes a wedged `kStarting` state (`driver:vimbax_camera/src/vimbax_camera_node.cpp:307-321`). C, X.

### 1.5 Commands, triggers, and status

1. `[F]` `features/command_run` runs any command feature, for example `TriggerSoftware`. The reply has an error field and no frame identity (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1039-1067`, `driver:vimbax_camera_msgs/srv/FeatureCommandRun.srv:1-4`). C, X.
2. `[F]` The command poll checks `IsDone`, sleeps 100 ms, then checks the timeout, and repeats until done. A successful call takes at least 100 ms (`driver:vimbax_camera/src/vimbax_camera.cpp:674-688`). C, X.
3. `[F]` A timeout of 100 ms or less always returns `VmbErrorTimeout` (-12), even when the command is done. A timeout of 0 selects 1 s (`driver:vimbax_camera/src/vimbax_camera.cpp:657`, `:665-688`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1047-1054`). C, X.
4. `[F]` An SDK error from the run or the first `IsDone` returns before the sleep (`driver:vimbax_camera/src/vimbax_camera.cpp:659-680`). X, K.
5. `[F]` The feature group is Reentrant, so two callers can run commands in parallel. One serial caller gets at most about 10 commands per second (`driver:vimbax_camera/src/vimbax_camera_node.cpp:632`). C, X.
6. `[F]` The driver has no single-frame mode. `AcquisitionMode`, `TriggerMode`, `TriggerSource`, and `TriggerSelector` are plain features. C, X.
7. `[F]` `status` writes each available `TriggerSelector` value to read trigger mode and source. It leaves the selector at the last value (`driver:vimbax_camera/src/vimbax_camera.cpp:1452-1473`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:69-71`). C, X.
8. `[F]` A `status` call between a selector write and a mode write changes the target of the mode write. C, X.

### 1.6 Timestamps and frame identity

1. `[F]` With `use_ros_time: false`, `header.stamp` is the SDK frame timestamp scaled by `DeviceTimestampFrequency` from the local device module, with integer arithmetic (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1610-1618`, `driver:vimbax_camera/src/vimbax_camera.cpp:308-316`, `:1760-1778`). C, X.
2. `[F]` Without that feature, the driver uses raw ticks as nanoseconds (`driver:vimbax_camera/src/vimbax_camera.cpp:1777`). C, X.
3. `[F]` With `use_ros_time: true`, `header.stamp` is `node->now()` in the frame thread, after the transform and before publish (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1608-1609`). C, X.
4. `[F]` The driver reads `use_ros_time` on each frame. A change during a stream changes the time basis between two frames (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1608`). C, X.
5. `[F]` Each frame has one stamp. The driver never publishes the device stamp and a host stamp together. C, X.
6. `[F]` `header.frame_id` is the `camera_frame_id` parameter, default `vimbax_camera_<DeviceID>`. It names a TF frame, not a frame instance (`driver:vimbax_camera/src/vimbax_camera_node.cpp:409-412`, `:1605`). C, X.
7. `[F]` The SDK `frameID` feeds only the gap log. The message carries no counter (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1596-1603`, `ros:ros2/common_interfaces/sensor_msgs/msg/Image.msg:4-26`). C, X.
8. `[F]` `last_frame_id_` resets at each stop. The disconnect path does not reset it (`driver:vimbax_camera/src/vimbax_camera_node.cpp:545-555`, `:1659`). C, X.
9. `[F]` The CycloneDDS RMW does not fill the two message sequence fields in the message info (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3274-3285`). X.
10. `[Q]` The epoch, tick rate, and exposure event of the G1-130 VSWIR timestamp are not in code. Open question T4.

### 1.7 Frame loss visibility

| Where a frame is lost | What shows it | Evidence |
|---|---|---|
| SDK receives an incomplete frame | WARN log with the receive status. The buffer is requeued, not published. | `driver:vimbax_camera/src/vimbax_camera.cpp:1739-1742` |
| SDK has no free buffer | WARN log "N frames missing" at the next published frame | `driver:vimbax_camera/src/vimbax_camera_node.cpp:1596-1601` |
| Requeue fails | ERROR log | `driver:vimbax_camera/src/vimbax_camera_node.cpp:1633-1638` |
| DDS sample rejected at the reader | `message_lost` event, from `DDS_SAMPLE_LOST_STATUS` | `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3943-3955`, `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:1643-1647` |
| Reader KEEP_LAST history replaces an unread sample | Nothing (X8) | `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875` |
| Consumer queue evicts a frame | Only a counter that the project writes | No code yet |

`[F]` No loss signal reaches the image message. C, X.

### 1.8 Calibration

1. `[F]` `CameraInfoManager` uses the camera `device_id` as its name and the read-only `camera_info_url`. An empty URL selects `file://${ROS_HOME}/camera_info/${NAME}.yaml` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:421-423`, `ros:ros-perception/image_common/camera_info_manager/src/camera_info_manager.cpp:67-69`, `:230-242`). C, X.
2. `[F]` If the loaded width or height differs from the frame, the driver publishes a `CameraInfo` with only width and height set (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1620-1628`). C, X.
3. `[F]` `K[0] == 0.0` means uncalibrated (`ros:ros2/common_interfaces/sensor_msgs/msg/CameraInfo.msg:20-23`). C, X.
4. `[F]` A size match does not prove that the calibration fits the current ROI or binning. X.

### 1.9 Events and connection

1. `[F]` An event topic exists only after a call to its subscribe service. A 500 ms timer removes each event publisher with zero subscribers, so a late subscriber can miss it (`driver:vimbax_camera_events/src/event_publisher_base.cpp:43-91`). C, X.
2. `[F]` No ROS event exists for frames, stream state, or connection. C, X.
3. `[F]` `connected` returns `camera_ != nullptr` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1520-1527`). C, X.
4. `[F]` On a "Missing" event, the driver saves `is_streaming()`, marks the camera unavailable, and releases it (`driver:vimbax_camera/src/vimbax_camera_node.cpp:545-555`). C, X.
5. `[F]` While unavailable, each camera service returns -3 (`driver:vimbax_camera/src/vimbax_camera_node.cpp:721-723`, `:1551-1553`). C, X.
6. `[F]` On a "Detected" event for the same camera, a detached thread reopens the camera and loads `settings_file` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:556-568`, `:390-400`). C, X.
7. `[F]` After a reopen, the graph thread restarts the stream if it was active or starting at the disconnect. `autostream` does not affect this, and the result is ignored (X3). C, X.
8. `[F]` The driver logs disconnect and reconnect. It publishes no message for them (`driver:vimbax_camera/src/vimbax_camera_node.cpp:547-549`, `:558-559`). C, X.
9. `[F]` If the first open fails, the driver calls `rclcpp::shutdown()` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:375-382`). C, X.
10. `[A]` A power cycle resets features that the project wrote through services. Only `settings_file` values return after a reopen. Configuration ownership (D18) depends on this. Open question R16. C.

### 1.10 Coordinator additions

These facts came up while the coordinator settled the conflicts. Neither trace states them.

1. `[F]` The `buffer_count` parameter callback calls `camera_->is_streaming()` without a null check (`driver:vimbax_camera/src/vimbax_camera_node.cpp:311-312`). The disconnect path sets `camera_` to null (`:554`). K.
2. `[A]` A `buffer_count` change during a disconnect therefore crashes the driver. Bringup should set `buffer_count` only in the parameter file. D10 and D21 depend on this.
3. `[F]` The `stream_start` and `stream_stop` handlers take a shared lock on `camera_mutex_`. The functions they call take a second shared lock on the same `std::shared_mutex` in the same thread (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1544`, `:1564`, `:1590-1591`, `:1654-1655`, `driver:vimbax_camera/include/vimbax_camera/vimbax_camera_node.hpp:114`). K.
4. `[A]` C++ does not define a recursive shared lock. The risk is a hang if a disconnect asks for the unique lock between the two locks. D21 lists it as a patch candidate.
5. `[F]` A wedged `kStarting` stream at disconnect sets the restart flag, so a reconnect starts a stream on the new camera object (`driver:vimbax_camera/src/vimbax_camera_node.cpp:551`, `:590-593`). A reconnect is therefore one recovery path from the wedge. K.

## 2. Settled conflicts

| Id | Topic | Claude trace | Codex trace | Source evidence | Correct trace |
|---|---|---|---|---|---|
| X1 | v1 §3.2: start or stop that races a transition returns -15 | Confirmed | Wrong | Both stream services are in one MutuallyExclusive group (`driver:vimbax_camera/src/vimbax_camera_node.cpp:650-651`, `:1554`, `:1574`). `start_streaming` and `stop_streaming` lock `stream_state_mutex_` (`:1589-1591`, `:1653-1655`). The graph thread calls the same functions (`:591`, `:606`, `:613`). Two calls wait for each other. -15 comes only from a state that an earlier failure left at `kStarting` or `kStopping` (`driver:vimbax_camera/src/vimbax_camera.cpp:416-519`, `:527-586`). | Codex |
| X2 | v1 §3.2: any new subscriber undoes an explicit stop | Confirmed | Wrong | Both agree that the guard at `:604` is always true. The branch runs only if the count rises (`driver:vimbax_camera/src/vimbax_camera_node.cpp:598-601`). The count is a maximum of two counts (`ros:ros-perception/image_common/image_transport/src/camera_publisher.cpp:100-102`). An image subscriber added while the `camera_info` count is higher does not raise it. | Codex on scope. Both are correct about the guard. |
| X3 | Which stream state the reconnect restarts | "if the stream was active" | "active or starting" | `stream_restart_required = camera_->is_streaming()` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:551`). `is_streaming()` is true for `kActive` and `kStarting` (`driver:vimbax_camera/src/vimbax_camera.cpp:1508-1513`). | Codex |
| X4 | v1 §3: Allied Vision tested the driver with CycloneDDS | Confirmed | Wrong | The driver README states "Tested ROS 2 RMW implementation: rmw_cyclone_dds" (`driver:README.md:7`). v1 does not claim a test of the VeniMapping fork. | Claude |
| X5 | v1 §3: the driver is v1.0.1, "the version targeted by `scripts/env.sh`" | Wrong | Stale | The package version is 1.0.1 (`driver:vimbax_camera/package.xml:5`). `git log -G '1\.0\.1' -- scripts/env.sh README.md` finds only `2211fe9`, which changed only `README.md`. `env.sh` never named a version, so the claim was never true. | Claude |
| X6 | v1 §3.4: 10, 12, and 14-bit formats are published MSB-aligned | Confirmed, with a note that Mono10 and Mono14 fail the gate | Wrong | The gate admits Bayer 10, Mono12, and Bayer 12 only (`driver:vimbax_camera/src/vimbax_camera.cpp:1621-1651`). No 14-bit format and no Mono10 format can be published. The shift exists for the admitted formats (`:1784-1797`). | Codex on the verdict. Both traces state the same code facts. |
| X7 | v1 §3.6, §8.4: polling `connected` is the only disconnect signal | Confirmed | Wrong | No ROS event exists (both agree). While unavailable, each camera service returns -3 (`driver:vimbax_camera/src/vimbax_camera_node.cpp:721-723`, `:1551-1553`), so any gateway call shows the outage. The driver also logs it (`:547-549`). | Codex |
| X8 | Does a reader KEEP_LAST overwrite raise `message_lost` in CycloneDDS? | `[A]`, open as U18 | Fact: no | The overwrite branch in `add_sample` sets no status (`ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`). The only `DDS_SAMPLE_LOST_STATUS_ID` raise in `ddsc/src` is the rejected-sample branch (`:1643-1647`). U18 is closed. | Codex |
| X9 | Does the launch override the driver node name and namespace? | `[A]` | Fact | `launch_ros` passes `__node:=` and `__ns:=` for `name` and `namespace` (`ros:ros2/launch_ros/launch_ros/launch_ros/actions/node.py:492-494`). `rcl_node_init` applies both rules over the name in code (`ros:ros2/rcl/rcl/src/rcl/node.c:204-229`). | Codex |

Each trace was correct in some conflicts. The Claude trace was correct in X4 and X5. The Codex trace was correct in X1, X2, X3, X6, X7, X8, and X9. In X1, X2, X6, and X7, the Claude trace marked a v1 claim Confirmed that the code does not fully support. The coordinator runs on Claude and checked these four against the source with no preference.

The Codex trace had no claim about the `kStarting` wedge recovery beyond "does not guarantee that a repeat call can recover it". The Claude trace said both services return -15 until a reopen. The code supports the Claude statement (section 1.4, items 3 and 4). This is a difference in detail, not a conflict.

## 3. Audit of v1

Verdicts:

- Confirmed: the code supports the claim at `67dd41e`.
- Stale: the claim was true at an earlier commit, or it uses an old name.
- Wrong: the code contradicts the claim.
- Partly wrong: one part of the claim holds and one part does not.
- No evidence: the code neither supports nor contradicts the claim. A camera check or Logan must answer it.

| # | v1 claim | v1 § | Verdict | Evidence | Trace |
|---|---|---|---|---|---|
| A1 | The project has no image acquisition or image storage layer | 1, 2 | Confirmed | Section 1.1, item 1 | C, X |
| A2 | `CameraGateway` is ROS-free and covers float, enum, access mode, feature list, status, and connection | 2 | Confirmed, but incomplete (A3) | `src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:11-138` | C, X |
| A3 | The gateway lacks stream start and stop, command run, int, bool, string, raw, and settings | 2, 5, 7, 13, 15.3 | Stale | The 30 methods include all of them (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:35-138`). Added in `f578840` | C, X |
| A4 | `VimbaXCameraGateway` hides service names, timeouts, and rclcpp exceptions behind blocking calls on one bound worker | 2, 5, 7 | Confirmed | `src/venimapping_camera/src/vimbax_camera_gateway.cpp:147-211` | C, X |
| A5 | Gateway timeouts are seconds-scale | 2, 5 | Confirmed | One caller timeout. Probe default 2000 ms (`src/venimapping_camera/src/camera_gateway_probe.cpp:132-138`) | C, X |
| A6 | `Expected` and `Error` live in `include/venimapping_camera/expected.hpp` | 2, 15.5 | Stale | `types/expected.hpp` and `types/error.hpp` | C, X |
| A7 | Driver errors pass unchanged. Gateway diagnostics are not contractual | 2, 4, 9 | Confirmed | `src/venimapping_camera/src/vimbax_camera_gateway.cpp:213-229`, `src/venimapping_camera/src/gateway_support/gateway_errors.hpp:15-22` | C, X |
| A8 | Diagnostics are `detail::GatewayDiagnostic` in `src/detail/gateway_util.*` | 9, 15.5 | Stale | `gateway_support::GatewayDiagnostic` in `src/venimapping_camera/src/gateway_support/gateway_errors.hpp:13-26` | C, X |
| A9 | The gateway header defers clamping, fallback, retry, and ordering to "future layers" | 2, 4, 8 | Confirmed in behavior, stale in wording | The header now says "no clamping, fallback, retry, readback, or validation" and names no future layers (`camera_gateway.hpp:24-26`, changed in `ce0aa1e`) | C, X |
| A10 | `camera_gateway_probe` is temporary and exercises a live driver | 2, 12 | Confirmed | `src/venimapping_camera/CMakeLists.txt:50-56` | C, X |
| A11 | The probe saves, changes, reads back, and restores camera state | 8.2, 12 | Confirmed | `src/venimapping_camera/src/camera_gateway_probe.cpp:632-653`, `:735-769`, `:929-953` | X |
| A12 | The probe guarantees that it leaves the camera unchanged | 8.2 | Wrong | Early return on a failed setter (`src/venimapping_camera/src/camera_gateway_probe.cpp:744-768`) | X |
| A13 | Bringup launches the driver under `/vimbax_camera` with `autostream` 0 | 2, 3.2, 10 | Confirmed | Section 1.1, items 2 to 4 | C, X |
| A14 | Bringup `config/` is new, and parameters go in `camera.launch.py` | 10, 15.5 | Stale | `config/camera.yaml` exists and is installed. Parameters come through `params_file` | C, X |
| A15 | The driver is v1.0.1, the version that `scripts/env.sh` targets | 3 | Wrong | X5 | C, X |
| A16 | Allied Vision tested the driver with CycloneDDS, and the environment selects it | 3, 10 | Confirmed | X4. `env.sh` selects it only if `RMW_IMPLEMENTATION` is unset and the package exists (`scripts/env.sh:127-134`) | C, X |
| A17 | `image_raw` and `camera_info` come from a `CameraPublisher` with one shared header | 3.1 | Confirmed | Section 1.3, item 1 | C, X |
| A18 | Publisher QoS is fixed at RELIABLE, KEEP_LAST 10, VOLATILE. Both subscriber reliabilities match | 3.1, 6.4 | Confirmed | Section 1.3, items 2 and 3 | C, X |
| A19 | No snapshot service exists. Pixels leave only on the topic | 3.1 | Confirmed | Section 1.3, item 5 | C, X |
| A20 | `StreamStartStop` has an empty request and an `Error` reply. Start while active and stop while stopped succeed with no effect | 3.2, 7 | Confirmed | `driver:vimbax_camera_msgs/srv/StreamStartStop.srv:1-2`, section 1.4 table | C, X |
| A21 | Start or stop that races a transition returns -15 | 3.2 | Wrong | X1 | C, X |
| A22 | An unavailable camera returns -3. A bad `PixelFormat` fails start with -18 | 3.2, 7, 9 | Confirmed. v1 misses that the state then stays at `kStarting` | Section 1.4, items 1 to 4 | C, X |
| A23 | `autostream` defaults to 1. A poll thread starts on a count rise and stops at zero | 3.2 | Confirmed | `driver:vimbax_camera/src/vimbax_camera_node.cpp:296`, `:579-628` | C, X |
| A24 | The always-true guard at `:604` means any new subscriber undoes `stream_stop` | 3.2 | Partly wrong | X2 | C, X |
| A25 | `camera_info` and debug subscribers count toward autostream | 3.2 | Confirmed | Section 1.4, item 11 | C, X |
| A26 | Under autostream the driver ignores a start failure | 7, 11 | Confirmed | `driver:vimbax_camera/src/vimbax_camera_node.cpp:606`. Logged at `driver:vimbax_camera/src/vimbax_camera.cpp:430` | C, X |
| A27 | With `autostream` 0, subscriptions do not drive streaming | 3.2, 6.3 | Confirmed | `driver:vimbax_camera/src/vimbax_camera_node.cpp:588-618` | X |
| A28 | The driver reopens on reconnect but does not restart the stream. With `autostream` 0, only the gateway restarts it | 3.2, 8.4, 14 | Wrong | X3. Any service client can also call `stream_start` | C, X |
| A29 | `features/command_run` can run `TriggerSoftware` | 3.3 | Confirmed | Section 1.5, item 1 | C, X |
| A30 | The driver sleeps 100 ms before the first completion check | 3.3 | Wrong | The first `IsDone` check comes before the sleep. The 100 ms floor per successful call holds (`driver:vimbax_camera/src/vimbax_camera.cpp:676-688`) | C, X |
| A31 | A software-trigger path is capped below 10 Hz | 3.3, 8.2 | Confirmed for one serial caller | Parallel callers can overlap (section 1.5, item 5) | C |
| A32 | `command_feature_timeout` 0 means 1 s. A value of 100 ms or less reports timeout on success | 3.3, 7 | Confirmed | Section 1.5, item 3 | C, X |
| A33 | A useful nonzero command timeout must exceed 200 ms | 3.3 | Wrong | A command done at the first check returns after one sleep. A 150 ms timeout then succeeds (`driver:vimbax_camera/src/vimbax_camera.cpp:665-688`) | X, K |
| A34 | The default stamp comes from the camera clock. `use_ros_time: true` samples the node clock in the frame thread after the transform | 3.4 | Confirmed | Section 1.6, items 1 and 3 | C, X |
| A35 | The camera clock has a power-on epoch and gives exposure time | 3.4, 11, 14 | No evidence | Neither trace finds the epoch or the event in code. The Claude trace lists it as unknown and the Codex trace marks it Wrong. T4 | C, X |
| A36 | `use_ros_time: true` gives comparable stamps, so `now - stamp` measures end-to-end latency | 3.4, 8.2, 10 | Wrong | The stamp is taken after capture, transfer, queue wait, and transform. The subtraction measures time after the driver stamp only | X |
| A37 | `header.frame_id` comes from read-only `camera_frame_id` | 3.4 | Confirmed | Section 1.6, item 6 | C, X |
| A38 | No frame counter reaches the wire. `frameID` feeds only a log line | 3.4 | Confirmed | Section 1.6, item 7 | C, X |
| A39 | Incomplete frames are requeued silently | 3.4, 14 | Wrong | WARN log with the status (`driver:vimbax_camera/src/vimbax_camera.cpp:1740`). Not published | C, X |
| A40 | The `message_lost` event shows consumer-side transport loss | 3.4, 6.4 | Confirmed for rejected samples only | Section 1.7 | C, X |
| A41 | RELIABLE delivery moves overflow into the project queue, so `receive_seq` and `message_lost` count consumer loss | 6.4, 14 | Wrong | X8. A history overwrite is not counted. A receive sequence counts only received samples | X |
| A42 | 10, 12, and 14-bit formats are published MSB-aligned with no marker | 3.4, 6.2 | Partly wrong | X6 | C, X |
| A43 | The gate list is Mono8, 12, 16, Bayer 8, 10, 12, 16, Rgb8, Bgr8, and YUV422 variants | 3.4, 10 | Confirmed | Section 1.3, item 6 | C, X |
| A44 | `camera_info` comes from `camera_info_manager` and read-only `camera_info_url`. A size mismatch gives zero `K`. `K[0] == 0` means uncalibrated | 3.5 | Confirmed. Width and height are still set | Section 1.8 | C, X |
| A45 | Polling `connected` is the only disconnect signal | 3.6, 8.4 | Partly wrong | X7 | C, X |
| A46 | GenICam events use a subscribe service, a per-event topic, and a 500 ms reaper with a race | 3.6, 14 | Confirmed | Section 1.9, item 1 | C, X |
| A47 | Factories return `Expected`. Ports are not copyable or movable. C++23 | 4, 15.5 | Confirmed | `src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:29-32`, `src/venimapping_camera/CMakeLists.txt:27` | C, X |
| A48 | `ConnectionStatusGet` returns false as a successful negative | 3.6, 4 | Confirmed in behavior, stale in name | `connection_status()` (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:231-238`) | C, X |
| A49 | Names `Call`, `CallChecked`, `BindToCurrentThread`, and PascalCase `<Noun><Verb>` | 4, 5, 6.3, 15 | Stale | `call`, `call_checking_driver_error`, `bind_to_current_thread`, snake_case (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:63-64`, `:183-196`) | C, X |
| A50 | A gateway call from executor code deadlocks | 6.3, 11 | Confirmed. The effect is a timeout, not a hang | Section 1.1, item 17 | C, X |
| A51 | The probe spins a `SingleThreadedExecutor` on its own thread | 6.5 | Confirmed | Section 1.1, item 18 | C, X |
| A52 | The driver computes `step` once at start. Width, height, and encoding come from each frame | 6.1, 8.3, 14 | Confirmed | Section 1.3, items 9 and 10 | C, X |
| A53 | A received image is heap memory, not a DDS loan. Holding the message avoids a copy in the adapter | 6.1, 11 | Confirmed | Section 1.3, item 13. `ros:ros2/rclcpp/rclcpp/src/rclcpp/executor.cpp:554-606` | C, X |
| A54 | CycloneDDS has no loaned-message support | 11 | Wrong | It loans self-contained types. `Image` gets no loan, so the v1 conclusion holds | C, X |
| A55 | No Jazzy RMW can avoid serialization for images | 11 | No evidence | The source shows the CycloneDDS path only | X |
| A56 | `rmw_zenoh` gives shared memory with no changes | 14 | No evidence | No Zenoh configuration or measurement in the project | X |
| A57 | Queue capacity bounds pinned memory. Frames are 2 to 15 MB | 6.1 | Partly wrong | The formula bounds only project-held frames. Driver buffers and DDS history are separate. The checkpoint sets no format or size, so 2 to 15 MB has no source. T2 | C, X |
| A58 | The thread check detects misuse and does not synchronize | 6.3 | Confirmed | Section 1.1, item 17 | C |
| A59 | Private headers are never installed | 15.5 | Confirmed | Section 1.1, item 22 | C |
| A60 | `ament_cmake_gtest` is a test dependency, and a two-tier test pattern with fakes exists | 4, 12, 15.5 | Partly wrong | The dependency exists. No test target or fake exists (section 1.1, item 21) | C, X |
| A61 | Targets `venimapping_camera_gateway_api` and `venimapping_camera_vimbax_gateway` exist | 15.5 | Confirmed | `src/venimapping_camera/CMakeLists.txt:22-48` | C, X |
| A62 | Adapters take `rclcpp::Node&` without ownership | 6.5, 14 | Confirmed | Section 1.1, item 11 | C, X |
| A63 | `buffer_count` defaults to 7 and changes only while stopped. `settings_file` loads on open | 10 | Confirmed | Section 1.4, item 13. Section 1.9, item 6 | C, X |
| A64 | The driver README asks for DDS tuning, about 8 MiB receive buffers | 10, 14 | Confirmed | `driver:README.md:35-36`, `:819`, `ros:ros2/rmw_cyclonedds/README.md:27-32` | C, X |
| A65 | `status.streaming` means active or starting | 7 | Confirmed | `driver:vimbax_camera/src/vimbax_camera.cpp:1508-1513` | C, X |
| A66 | A subscription made before `stream_start` cannot lose startup frames | 8.1, 8.2 | Wrong | The publisher is VOLATILE. `stream_start` does not wait for a matched reader. Creation can come before matching | X |
| A67 | A warm get image answers in milliseconds | 8.2 | No evidence | No consumer exists. The answer depends on the frame rate | X |
| A68 | A frame received after the request can have been exposed before it | 8.2 | Confirmed | The driver publishes after receipt, queue wait, and transform (`driver:vimbax_camera/src/vimbax_camera.cpp:458-482`) | X |
| A69 | rclcpp treats temporary one-message subscriptions as only for isolated use | 8.2 | Wrong | `wait_for_message` states no frequency rule (`ros:ros2/rclcpp/rclcpp/include/rclcpp/wait_for_message.hpp:31-48`, `:80-103`) | X |
| A70 | `FrameStart`, `On`, `Software` gives exactly one exposure and identifies its frame. `SingleFrame` tears down the stream | 8.2, 14, 15.4 | Partly wrong | The command reply and the image share no identifier, so frame association is wrong. The one-exposure behavior has no evidence. Check `camera-c2` | X |
| A71 | The bound worker can query whether features are readable and writable | 8.2, 8.3 | Confirmed | `src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:55-57` | X |
| A72 | `TLParamsLocked` locks shape features during acquisition. Trigger features stay writable | 8.1, 8.3 | No evidence | The driver passes each write to VmbC. Check `camera-c1` reads the access modes while streaming | X |
| A73 | `AcquisitionFrameRate` paces free run only. Alvium needs `AcquisitionFrameRateEnable=true` | 7, 8.3 | No evidence | The driver enforces neither. Check `camera-c1` reads whether the feature exists | C, X |
| A74 | The in-process mapping consumer wants raw frames. Compressed topics are available | 11 | Wrong | No mapping consumer exists. A compressed topic needs an installed and enabled plugin | X |
| A75 | A direct SDK adapter could read `frameID` and device timestamps | 11, 14 | Confirmed | `driver:vmbc_interface/include/VmbC/VmbCTypeDefinitions.h:376-383`, `:441-443` | X |

## 4. Requirements and working assumptions

### 4.1 Requirements from Logan

The column "Logan changes design" is Yes when a different answer changes an interface, an owner, or a package. It is Partly when only a number or a default changes.

| Id | Unknown requirement | Working assumption | What depends on it | Logan changes design |
|---|---|---|---|---|
| R1 | Which components consume frames, and in which process or host | One C++ consumer in the same process as the acquisition code, on the driver host. No other node needs frames from the project | D1, D2, D7, D13, D29 | Yes |
| R2 | Resolution, ROI, and binning | Full sensor, no binning. Interfaces carry width, height, and `step` from each frame, so no interface fixes a size | D4, D10, R5 | Partly |
| R3 | Pixel format and bit depth | Mono8 for the first phase. Mono12 only if `camera-c1` shows it on the gate and a consumer needs more than 8 bits | D14, D18, D10 | Yes |
| R4 | Feed frame rate | Free run at 30 Hz or less | D9, D10, DDS tuning in bring-up | Partly |
| R5 | Memory budget for frames that the project holds | Each feed holds at most its queue capacity plus the frames the consumer holds. No fixed byte budget until `camera-c1` gives `PayloadSize` | D4, D10 | Partly |
| R6 | Freshness for get image | "Received after the request" is enough. Exposure after the request is not required | D23, D24, D27, D20 | Yes |
| R7 | Maximum wait for get image | A cold get image can take up to 2 s. A warm get image waits at most two frame periods | D25, D26 | Yes |
| R8 | How often get image runs, and whether it overlaps a feed | Less than once per second. It can run while a feed runs and must not stop that feed | D16, D17, D25, D28 | Yes |
| R9 | Loss tolerance of the feed | The feed can drop frames under load. It counts each drop that the project can see. Newer frames have priority | D9, D10, D12, D21 | Yes |
| R10 | Time basis and stamp accuracy | Consumers need a stamp on the host clock, comparable with `now()`. No PTP or hardware sync | D3, D20, D24 | Yes |
| R11 | Intrinsics with each frame | Not needed in the first phase. The frame carries no `CameraInfo` | D3, D15 | Yes |
| R12 | Deployment topology and middleware | The driver and all consumers run on one host with CycloneDDS | D8, D9, D4 | Yes |
| R13 | Whether a patch to the driver fork is acceptable | The design works without a patch. Patches are listed as options only | D11, D12, D19, D21 | Yes |
| R14 | Outage behavior | A disconnect does not close the feed. The feed reports the outage and marks the first frame after it as a new stream epoch | D11, D17, D22 | Yes |
| R15 | Other clients of the driver, for example `rqt` or the CLI | While the project acquires, only the project writes features or calls stream services. No tool calls `status` during a trigger setup | D16, D27 | Yes |
| R16 | Whether camera features survive a power cycle, and who owns configuration | Service writes are lost on a power cycle. The project applies its configuration again after each reopen | D18, D22 | Yes |

### 4.2 Technical unknowns

| Id | Unknown | Working assumption | What depends on it | Who answers |
|---|---|---|---|---|
| T1 | Which `PixelFormat` values the camera offers and which pass the gate | At least Mono8 passes | R3, D14, D18 | Check `camera-c1` |
| T2 | `WidthMax`, `HeightMax`, and `PayloadSize` at the chosen format | Use the measured value. Until then, use symbolic sizes | R5, D10 | Check `camera-c1` |
| T3 | Delivered frame rate at the chosen format | 30 Hz or more is possible | R4, D10 | Check `camera-c1` |
| T4 | `DeviceTimestampFrequency` presence, epoch, and the relation of device stamps to the host clock | Device stamps are not comparable with the host clock | D20, D24 | Check `camera-c1` |
| T5 | Time from `stream_start` to the first `image_raw` header | More than 100 ms because of the command poll | D25, D26 | Check `camera-c1` |
| T6 | Whether `FrameStart`, `Software`, and `TriggerSoftware` exist, and whether one command gives one frame | Unverified. The trigger option stays open | D23, D27 | Check `camera-c2` |
| T7 | Which features are writable while the stream is active | Shape features are not writable. Exposure and rate are writable | D18 | Check `camera-c1` |
| T8 | Whether `AcquisitionFrameRateEnable` exists on this model | Unknown | D18 | Check `camera-c1` |
| T9 | Whether a RELIABLE publish in the driver blocks on a slow reader | It can block. Section 1.3, item 14 | D9, D10 | Bench test under load. Not in this round |
| T10 | Which `image_transport` plugins are installed on the host | Only `raw` | D8 | Host check by Logan |
| T11 | Whether host socket buffers are tuned per the driver README | Not tuned | D9, bring-up | Host check by Logan |
| T12 | Time from subscription creation to a matched reader | Tens of milliseconds on one host | D17, D25 | Bench test without the camera |

U18 from the Claude trace is closed by X8.

## 5. Design choices

"Crosses the split" is Yes when the codex `data-plane` section and at least one claude section depend on the answer. The claude sections are control-plane, error-vocabulary, bring-up, testing, and implementation-sequence. "Source" maps the choice to the trace ids.

### Structure

**D1. Package layout**
- Question: Do the new parts go in `venimapping_camera`, or in a new package?
- Options: (a) Add them to `venimapping_camera` next to the gateway. (b) Add a ROS-free package for ports and policy, and keep adapters in `venimapping_camera`. (c) Add one new acquisition package for ports, adapters, and policy.
- Crosses the split: Yes. The source tree, data-plane, testing, and implementation-sequence all use it.
- Inputs: R1, R12. Source: C S1.

**D2. Port shape**
- Question: Does acquisition extend `CameraGateway`, or use a separate data-plane port?
- Options: (a) A separate ROS-free frame port, as v1 proposed. (b) Add frame methods to `CameraGateway`. (c) No port. Consumers subscribe to the driver topic.
- Crosses the split: Yes. Data-plane defines the port. Control-plane composes it.
- Inputs: R1. Source: C S2.

**D3. Frame type and metadata**
- Question: Which fields does the project frame carry, and does it hide all ROS types?
- Options: Fields to choose from: width, height, `step`, encoding, device stamp, host receipt stamp, `frame_id`, receive sequence, stream epoch, source bit depth, and optional `CameraInfo`. Either hide all ROS types, or expose `sensor_msgs::msg::Image`.
- Crosses the split: Yes. Control-plane, error-vocabulary, and testing use the frame.
- Inputs: R10, R11. Source: C S3, X Output, X Metadata.

**D4. Memory model**
- Question: Does the frame keep the received message alive, or own a copy of the pixels?
- Options: (a) Keep the message alive through a type-erased shared pointer, as v1 proposed. (b) Copy into a project buffer. (c) Copy into a pool of preallocated buffers.
- Crosses the split: No. Data-plane only.
- Inputs: R2, R5, R12. Source: C S4, X Buffer ownership.

**D5. Thread and executor model**
- Question: Which thread runs the image subscription callback, and does it share a node and executor with the gateway?
- Options: (a) One node and one executor thread for gateway replies and image callbacks. (b) One node with a separate callback group for images on a `MultiThreadedExecutor`. (c) A separate node and executor thread for images.
- Crosses the split: Yes. Control-plane owns the gateway thread rules. Data-plane owns the callback.
- Inputs: R1, R4. Source: C S10.

**D6. Error vocabulary**
- Question: Which new failures need codes, and in which domain?
- Options: (a) No new domain. Add non-contractual gateway diagnostics, as v1 proposed. (b) A new acquisition domain with contractual codes for feed closed, stream wedged, and deadline passed. (c) Use driver codes only and report other failures as empty results.
- Crosses the split: Yes. Data-plane produces errors. Error-vocabulary defines them.
- Inputs: R6, R7. Source: C S11.

### Data plane

**D7. Consumer API**
- Question: Do consumers pull frames with a timeout, get a callback, or subscribe to the driver topic?
- Options: (a) Pull with a timeout, as v1 proposed. (b) A callback on a project thread. (c) A callback on the executor thread. (d) The ROS topic is the contract.
- Crosses the split: Yes. Control-plane builds get image on it.
- Inputs: R1, R4. Source: C F1, X Consumer API.

**D8. Transport mechanism**
- Question: Does the feed use an rclcpp subscription, an `image_transport` subscriber, or VmbC without the driver?
- Options: (a) Plain rclcpp subscription on `image_raw`. (b) `image_transport` subscriber. (c) A direct VmbC adapter, which replaces the driver data path.
- Crosses the split: Yes. Option (c) changes bring-up and the driver ownership of the camera, because the driver opens it in exclusive mode (`driver:vimbax_camera/src/vimbax_camera.cpp:164-185`).
- Inputs: R1, R12, T10. Source: C F2, X Transport.

**D9. Subscriber QoS and history depth**
- Question: Does the subscriber use RELIABLE or BEST_EFFORT, and which history depth?
- Options: (a) RELIABLE with a small depth, as v1 proposed. (b) BEST_EFFORT with depth 1 to 3. (c) Configurable, with one default.
- Crosses the split: No. Data-plane only. Bring-up DDS tuning is independent.
- Inputs: R4, R9, R12, T9, T11. Source: C F5, X Transport.

**D10. Queue bound, overflow rule, and `buffer_count`**
- Question: What caps the frames the project holds, which frame drops at capacity, and which `buffer_count` does the driver use?
- Options: Queue capacity 1, 2 to 4, or caller-set. Drop the oldest or the newest. `buffer_count` at the default 7 or a measured value set in `camera.yaml`.
- Crosses the split: Yes. Data-plane owns the queue. Bring-up owns `buffer_count`.
- Inputs: R2, R4, R5, R9, T2, T3. Source: C F3, C F4, X Buffer limit.

**D11. Frame identity and sequence scope**
- Question: How does the project identify a frame, and does the sequence survive a stream restart or a reconnect?
- Options: (a) Receive sequence per subscription. (b) Receive sequence plus a stream epoch that increments on each start and reconnect. (c) Device stamp as identity. (d) SDK `frameID` from a driver patch.
- Crosses the split: Yes. Control-plane knows the stream starts. Data-plane assigns numbers.
- Inputs: R13, R14. Source: C F6.

**D12. Loss reporting**
- Question: Which loss counters does the feed offer, and how does it state what it cannot see?
- Options: Counters for queue evictions, `message_lost`, sequence gaps in a patched `frameID`, and stall time. The contract either lists the invisible losses (section 1.7) or not.
- Crosses the split: Yes. Error-vocabulary and testing depend on it.
- Inputs: R9, R13. Source: C F7, X Loss reporting.

**D13. Several consumers**
- Question: Can two feeds be open at the same time, and do they share one subscription?
- Options: (a) One feed only. (b) Several feeds, one subscription, one queue each. (c) Several feeds, one subscription each.
- Crosses the split: Yes. Control-plane stream ownership depends on it.
- Inputs: R1, R8. Source: C F9, X Delivery scope.

**D14. Pixel interpretation**
- Question: Does the project pass the encoding unchanged, or undo or record the MSB shift?
- Options: (a) Pass unchanged, as v1 proposed. (b) Add the source bit depth to the frame. (c) Undo the shift in the adapter.
- Crosses the split: Yes. Bring-up pins the format. Data-plane carries it.
- Inputs: R3, T1. Source: C S13.

**D15. Calibration pairing**
- Question: Does a frame come with its `CameraInfo`, and how is a zero `K` reported?
- Options: (a) No `CameraInfo` in the first phase. (b) Pair by header in the adapter. (c) Load calibration in the project and skip `camera_info`.
- Crosses the split: Yes. Bring-up owns `camera_info_url`. Data-plane owns the pairing.
- Inputs: R11. Source: C S14, X Metadata.

### Stream control and configuration

**D16. Stream ownership**
- Question: Which one component may call `stream_start` and `stream_stop`?
- Options: (a) One acquisition controller owns both, with a count of users. (b) Each feed starts and stops the stream. (c) Bringup or an operator starts the stream, and the project only reads it.
- Crosses the split: Yes. Data-plane feed open and close depend on it.
- Inputs: R8, R15. Source: C S5, X Start and close.

**D17. Feed start, readiness, and close**
- Question: Does opening a feed start the stream, what marks the feed ready, and what does close do if another user still needs frames?
- Options: Open starts the stream or only arms delivery. Ready means subscription created, reader matched, or first frame received. Close stops the stream always, never, or when the last user closes.
- Crosses the split: Yes. A66 shows that subscription order alone does not prevent lost startup frames.
- Inputs: R8, R14, T12. Source: C F8, X Start and close.

**D18. Configuration ownership and order**
- Question: Do pixel format, size, rate, and trigger mode come from `settings_file`, a camera `UserSet`, or service writes, and when can they change?
- Options: (a) `settings_file` on each open and reopen. (b) A camera `UserSet` loaded at power on. (c) Service writes by the controller before each start. (d) A mix, with shape features fixed and rate and exposure writable at run time.
- Crosses the split: No. Control-plane and bring-up. Data-plane takes the encoding from D14.
- Inputs: R3, R16, T1, T7, T8. Source: C S7, X Configuration.

**D19. Start and stop failure recovery**
- Question: How does the project detect and recover from a state left at `kStarting` or `kStopping`?
- Options: (a) Prevent it by checking `PixelFormat` against the gate before each start. (b) Detect it as -15 with `status.streaming` true, then restart the driver process. (c) Patch the driver to reset the state on failure. (d) Report it to the operator only.
- Crosses the split: No. Control-plane, error-vocabulary, and bring-up.
- Inputs: R13. Source: C S6.

**D20. Timestamp source**
- Question: Does bringup keep `use_ros_time: false`, or set it to true, and does the project add a host receipt stamp?
- Options: (a) Keep false and add a host receipt stamp in the adapter. (b) Set true, as v1 proposed. (c) Keep false and map device time to host time with a measured offset. (d) Patch the driver to publish both stamps.
- Crosses the split: Yes. Bring-up sets the parameter. Data-plane defines the frame fields.
- Inputs: R10, T4. Source: C S8, X Metadata.

**D21. Driver changes**
- Question: Does the design work around driver defects, or patch the fork?
- Candidates for a patch: the `kStarting` wedge, the `:604` guard, `frameID` in the message, a second stamp, the `buffer_count` null check, and the double shared lock.
- Options: (a) Work around all. (b) Patch the fork for a listed subset. (c) Replace the data path with VmbC (D8 option c).
- Crosses the split: Yes. Data-plane identity and loss and control-plane recovery depend on it.
- Inputs: R13. Source: C S9.

**D22. Disconnect, silence, and outage**
- Question: How long without a frame before the project checks the connection, and what does it report and do after a reconnect?
- Options: Silence threshold as a fixed time or a multiple of the frame period. On reconnect: let the driver restart the stream and mark a new epoch, stop and restart under project control, or close the feed with an error.
- Crosses the split: Yes. Data-plane sees the silence. Control-plane checks `connected` and restarts.
- Inputs: R14, R16. Source: C S12, C F10, X Outage.

### Get image

**D23. Frame source for get image**
- Question: Does get image take a frame from a running stream, start and stop a stream for one frame, or use a software trigger?
- Options: (a) Sample a running stream. (b) Start and stop per call. (c) Software trigger with `FrameStart`, `On`, `Software`. (d) Choose per call, as v1 proposed.
- Crosses the split: Yes. Data-plane supplies frames. Control-plane runs the stream and trigger.
- Inputs: R6, R7, R8, T5, T6. Source: C G1, X Acquisition method.

**D24. Freshness rule**
- Question: Which frame counts as the answer?
- Options: (a) The next frame received after the request. (b) The first frame with a host stamp after the request. (c) The first frame exposed after the request, which needs a trigger or a device-to-host time map.
- Crosses the split: Yes. Data-plane supplies the stamp and sequence. Control-plane applies the rule.
- Inputs: R6, R10, T4. Source: C G2, X Freshness.

**D25. Idle behavior and subscription lifetime**
- Question: If no stream runs, does get image start one, keep one running, or fail? Does an idle project keep a matched subscription?
- Options: (a) Start and stop a stream and a subscription per call. (b) Keep a matched subscription and start the stream per call. (c) Keep the stream and the subscription running. (d) Fail if no stream runs.
- Crosses the split: Yes.
- Inputs: R7, R8, T5, T12. Source: C G3, X Subscription lifetime.

**D26. Deadline and timeout result**
- Question: Which steps count against the get image deadline, and what does a timeout return?
- Options: One deadline for start, first frame, and stop, or one for each step. A timeout returns an empty result or an error.
- Crosses the split: Yes. Data-plane pull timeout semantics and error-vocabulary depend on it.
- Inputs: R7, T5. Source: C G4, C G5, X Deadline.

**D27. Trigger association and restore**
- Question: If a trigger is used, how does get image find its frame, handle an uncertain command result, and restore the trigger features?
- Options: Association by the first frame after the command, by device stamp, or by a quiet interval. Restore by saving and writing back all trigger features under each selector, also on failure.
- Crosses the split: No. Control-plane only.
- Inputs: R6, R15, T6. Source: C G6, X Trigger association.

**D28. Get image during an open feed**
- Question: What happens if get image runs while a feed is open?
- Options: (a) Share the feed stream and take a frame from it. (b) Stop the feed, take a frame, and restore the feed. (c) Fail with an error.
- Crosses the split: Yes. Data-plane fan-out (D13) and control-plane ownership (D16) depend on it.
- Inputs: R8. Source: C G7, X Feed interaction.

**D29. Get image caller interface**
- Question: Is get image a C++ call only, or also a ROS service for other nodes?
- Options: (a) C++ only. (b) C++ plus a thin ROS service node. (c) ROS service only.
- Crosses the split: No. Control-plane and bring-up.
- Inputs: R1. Source: C G8.

## 6. Camera requests

One request exists: `claude/camera-requests/trace-claude.json`. The Codex trace has no request. The coordinator accepts the request and splits it into two short checks. Both checks go to claude and block both positions tasks.

| Check | Question | Decisions it changes | Features it writes |
|---|---|---|---|
| `camera-c1` | Formats, sizes, rate, timestamp, start latency, and writable features while streaming | D10, D14, D18, D20, D23, D25. T1 to T5, T7, T8 | `PixelFormat` |
| `camera-c2` | Does one `TriggerSoftware` give one frame, and how long does it take? | D23, D27. T6 | `TriggerSelector`, `TriggerMode`, `TriggerSource` |

Changes to the request:

1. The coordinator removed the writes to `AcquisitionFrameRateEnable` and `AcquisitionFrameRate`. The runner reads each listed feature before the check, and it stops the run if a feature does not exist. T8 asks if `AcquisitionFrameRateEnable` exists, so `camera-c1` reads it without a write.
2. The coordinator added read-only access-mode queries during the stream. They answer T7 and A72 from the Codex unknowns.
3. A start with a format outside the gate leaves the driver at `kStarting`. The runner then cannot stop the stream, and its cleanup fails. `camera-c1` must make sure the format is on the gate before each `stream_start`.
4. The runner restores the listed features in reverse order, after a `status` call that moves `TriggerSelector` (section 1.5, item 7). It therefore cannot restore `TriggerMode` under `FrameStart`. `camera-c2` must write back the `FrameStart` mode and source itself.
5. `[A]` The runner reads the trigger features before `camera-c2`. If the camera does not have them, the run stops. Alvium cameras normally have them.
