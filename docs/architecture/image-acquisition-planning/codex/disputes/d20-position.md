# D20 timestamp source

## Recommendation

Adopt option (b).

[F] The earlier Codex position and v1 both select `use_ros_time: true`. (`docs/architecture/image-acquisition-planning/codex/positions.md:168-174`, `docs/architecture/image-acquisition-design-v1.md:120-129`)

[A] R1, R6, R9, R10, and R12 apply. Phase 1 uses one live host and accepts receipt order for get image. Consumers need host time and accept visible loss counts. Epoch admission assumes the host wall clock does not step while acquisition runs. (`docs/architecture/image-acquisition-planning/register.md:594-605`)

1. Set `use_ros_time: true` and `use_sim_time: false` in the driver parameters in `camera.yaml`.
2. Set `use_sim_time: false` on the application node. Keep these parameters fixed while acquisition runs.
3. In d3 and d8, convert `header.stamp` to the single signed 64-bit `ImageFrame::host_stamp_ns` field. Use nanoseconds since the Unix epoch. Use the image callback without `rclcpp::MessageInfo` for this conversion.
4. In d11 and d22, let the controller open each epoch. Set the boundary from system time under the admission lock before sending `stream_start`. If using the driver restart, verify the profile before reopening admission. Set the new boundary from system time under the admission lock as admission reopens. Admit valid frames with `host_stamp_ns` strictly greater than the boundary. Keep `receive_seq` increasing across epochs.
5. In d12, keep the observed counters. Omit the provisional `stamp_gap_frames`. Measure frame age, silence, and deadlines on the steady clock.
6. In d24, return the first eligible frame that the fan-out gives to the get image subscription after it opens.

## Evidence

- [F] The current parameter file leaves the driver default of `use_ros_time: false` in effect. With true, the frame worker samples `node->now()` after the transform and before it prepares `CameraInfo` and calls publish. Both message headers carry that stamp. (`src/venimapping_bringup/config/camera.yaml:9-12`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:303-305`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1605-1631`, `driver:vimbax_camera/src/vimbax_camera.cpp:1745-1757`)
- [F] With simulation time off, the ROS clock uses system time. CycloneDDS samples system time for the DDS source stamp just before the DDS write. CycloneDDS RMW fills the receipt stamp at take. These are three different events. (`ros:ros2/rclcpp/rclcpp/src/rclcpp/time_source.cpp:251-268`, `ros:ros2/rcl/rcl/src/rcl/time.c:42-48`, `ros:ros2/rcl/rcl/src/rcl/time.c:62-72`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:1965-1970`, `ros:eclipse-cyclonedds/cyclonedds/src/ddsrt/src/time/posix/time.c:21-26`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3280-3283`)
- [F] The header check rejects a frame stamped before the boundary even if DDS writes it after the boundary, given a continuous clock. Both host stamps can follow an earlier exposure because the driver queues and transforms frames before it stamps them. (`driver:vimbax_camera/src/vimbax_camera.cpp:458-482`, `driver:vimbax_camera/src/vimbax_camera.cpp:1745-1757`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1608-1631`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:1965-1970`)
- [F] In c1, the first frame reached the matched reader before the start reply by about 79 ms at Mono8. A boundary at the reply would exclude those early frames. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:149-161`)

## The other side

[F] Option (a) keeps the device stamp in the header and gives the adapter two host stamps through `rclcpp::MessageInfo`. The DDS source stamp meets R10 on the same host. In c1, it preceded the RMW take stamp by 1.85 to 2.09 ms at Mono8. That interval quantifies source to take. The header to DDS source interval remains unmeasured. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1608-1618`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:1965-1970`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3280-3283`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:123-143`)

[A] The device stamp could reveal missing periods from camera-side loss or a reader history overwrite. A device clock reset could also mark a short outage that the controller misses. R1 gives no required raw-topic reader outside the adapter, so the clock in the raw header has limited weight. (`docs/architecture/image-acquisition-planning/claude/positions.md:250-285`, `docs/architecture/image-acquisition-planning/register.md:594`)

[F] The SDK defines the device stamp as a time set by the camera. Checks c1 and c3 report reader intervals. (`driver:vmbc_interface/include/VmbC/VmbCTypeDefinitions.h:441-445`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:111-119`, `docs/architecture/image-acquisition-planning/codex/camera/c3.md:61-65`)

[Q] The spread of consecutive device stamp deltas, the device clock reset behavior, and the exposure event remain open. (`docs/architecture/image-acquisition-planning/register.md:247-263`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:137-143`)

[A] Option (b) wins for phase 1. It gives d22 the earlier host boundary check and meets R10 directly. The controller marks observed recoveries. The d12 counters report the losses the adapter can observe. Using the device stamp for d11 or d12 would make the result depend on the unverified reset behavior or delta spread.

## What evidence would change the recommendation

- [Q] Does Logan need a free-run missing-frame estimate for phase 1? Choose option (a) if device deltas meet the d12 half-period limit on a loss-free run and recover known missing counts under load. Compare with SDK frame IDs at the 30 Hz profile and 69.7 Hz design load. (`docs/architecture/image-acquisition-planning/register.md:255-263`, `docs/architecture/image-acquisition-planning/codex/camera/c3.md:45-57`)
- [Q] Must phase 1 detect physical reconnects shorter than the d22 silence threshold? Reopen the choice if cable and power tests show a repeatable device stamp signature that separates these reconnects from loss and normal gaps. (`docs/architecture/image-acquisition-planning/register.md:449-457`)
- [Q] Does a consumer need exposure alignment within a stated error bound? Reopen the time contract with a measured exposure event and clock alignment error.

## Fallback

[A] Draft with one `host_stamp_ns` field from the driver header and pin option (b) for phase 1. Use the controller's epoch events and the steady clock for waits. The d3 metadata, d8 callback, d22 admission test, and bring-up parameters depend on this source.

[A] Switching to the DDS source stamp costs one parameter change and one callback change. Update the stamp description. Repeat the start and reconnect tests with the later stamp. Public device or receipt stamps would also change frame construction and consumer fixtures.
