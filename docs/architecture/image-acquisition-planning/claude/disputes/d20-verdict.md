# Claude verdict on dispute d20, timestamp source

Checkpoint `2c00d88`. Inputs: `register.md` entry D20, `claude/disputes/d20-position.md` ("the Claude position"), `codex/disputes/d20-position.md` ("the Codex position"), `coordinator/facts.md`, and checks c1 and c3.

Labels and citation forms follow `register.md`, "How to read this register". `ros:` paths are from the ROS 2 Jazzy source root. "K" marks a check of the source that I made for this file.

## 1. Verdict

Adopt a combination. The base is the Claude recommendation, option (a) narrowed, as in its section 1.1. Three rules come from the Codex position.

### 1.1 Rules for the drafters

1. Bring-up writes `use_ros_time: false` and `use_sim_time: false` in `camera.yaml`, under the existing `/**/vimbax_camera` key.
2. The application node sets `use_sim_time: false`. (From Codex.)
3. No project code changes `use_ros_time` or `use_sim_time` while acquisition runs. A bring-up test reads the driver `use_ros_time` parameter before the first `stream_start` and fails on `true`. (Codex rule, Claude test.)
4. The adapter subscribes with the message-info callback form: `std::shared_ptr<const sensor_msgs::msg::Image>` and `const rclcpp::MessageInfo &`.
5. `ImageFrame` carries two stamps and no other stamp field. Both values are nanoseconds.
   - `std::int64_t host_stamp_ns()`. The adapter fills it from `MessageInfo::get_rmw_message_info().source_timestamp`. The contract states that it marks the driver publish call on host `CLOCK_REALTIME`, not the exposure.
   - `std::optional<std::int64_t> device_stamp_ns()`. The adapter fills it from `header.stamp` as `sec * 1000000000 + nanosec`. The contract states that its origin and exposure event are unknown (T4).
6. The frame has no receipt stamp. The steady-clock receipt time stays inside `FrameSource` for the silence check (d22).
7. d11: only the controller starts an epoch. No stamp rule starts an epoch.
8. d22: the worker reads host `CLOCK_REALTIME` under the admission lock when it opens an epoch. That value is the boundary. The source admits a frame only if `host_stamp_ns` is at or after the boundary.
9. d12: `stamp_gap_frames` stays provisional and uses `device_stamp_ns` deltas in free run only. It has a value only when `device_stamp_ns` has a value.
10. d12: the feed probe keeps `stamp_gap_frames` only if both of these conditions are true. (The second condition is from Codex.)
    - On a run with no loss, the spread of consecutive device stamp deltas stays within 0.5 frame period.
    - Under load, the counter agrees with the "N frames missing" count in the driver log. The probe runs this at the 30 Hz phase 1 profile and at the 69.7 Hz design load.
11. A bring-up test reads the first frame and checks that `host_stamp_ns` is within 1 s of the adapter receipt time on host `CLOCK_REALTIME`. A zero or foreign value fails the test.

### 1.2 Effect on the entries in the scope of the dispute

| Entry | Rule |
|---|---|
| d3 | `host_stamp_ns` and `device_stamp_ns`, as in rule 5 |
| d8 | The message-info callback form, as in rule 4 |
| d11 | No stamp-based epoch rule. The Claude position withdrew it (Claude position §1.3 item 3) |
| d12 | `stamp_gap_frames` from device stamp deltas, provisional, with the two probe conditions of rule 10 |
| d22 | Boundary on host `CLOCK_REALTIME`, compared with `host_stamp_ns`, as in rule 8 |
| Bring-up | The `camera.yaml` lines of rule 1, the application node parameter of rule 2, and the tests of rules 3 and 11 |

## 2. Reasons

### 2.1 Both options give an equal host stamp on one host

1. `[F]` With `use_ros_time: true`, the driver sets `header.stamp = node_->now()` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1608-1609`). Checked.
2. `[F]` With sim time off, the ROS clock returns system time (`ros:ros2/rcl/rcl/src/rcl/time.c:65-70`), and system time is `CLOCK_REALTIME` (`ros:ros2/rcutils/src/time_unix.c:63-66`). Checked.
3. `[F]` The CycloneDDS RMW reads `dds_time()` at the start of `rmw_publish` and writes with that stamp (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:1967-1969`). `dds_time()` reads `CLOCK_REALTIME` (`ros:eclipse-cyclonedds/cyclonedds/src/ddsrt/src/time/posix/time.c:21-25`). Checked.
4. `[F]` The reader gets that value as `source_timestamp` (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3280`). Checked.
5. `[F]` Between the two clock reads, the driver builds `CameraInfo` and calls `CameraPublisher::publish` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1620-1631`). That call publishes the image first (`ros:ros-perception/image_common/image_transport/src/camera_publisher.cpp:135-136`). Checked.
6. `[F]` `dds_time()` runs before `dds_write_ts`. A RELIABLE reader that blocks the write therefore delays the return, not the stamp (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:1967-1969`). K.
7. `[A]` The header stamp of option (b) and the source timestamp of option (a) differ by the `CameraInfo` build and the plugin dispatch. Both positions agree that no check measured this interval.

Both stamps mark the same driver event on the same clock. R10 does not separate the options.

### 2.2 Option (b) removes the only loss signal from before the host pipeline

1. `[F]` The driver writes either the host stamp or the device stamp, never both (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1608-1618`, facts 1.6.5). Checked.
2. `[F]` An SDK buffer shortage shows only in a driver log, and a reader history overwrite shows nowhere (facts 1.7). No loss signal reaches the message. Checked.
3. `[F]` The SDK defines the frame timestamp as a time set by the camera (`driver:vmbc_interface/include/VmbC/VmbCTypeDefinitions.h:443`). Checked.
4. `[F]` The frame thread pops a frame, transforms it, stamps it, publishes it, and then requeues the buffer (`driver:vimbax_camera/src/vimbax_camera.cpp:458-482`, `:1745-1757`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1631-1633`). Host stamps therefore include queue wait and transform time. Checked.
5. `[F]` R9 requires a count of each visible drop (register §7.1). Under option (a), device stamp gaps can count SDK and reader history loss. Under option (b), the project has no counter for these two loss sites.
6. `[F]` Register d12 item 3 keeps `stamp_gap_frames` only after the feed probe measures the device delta spread (`docs/architecture/image-acquisition-planning/register.md:262`). Under option (b), the deployed configuration cannot make that measurement.
7. The Codex position grants the value of the device stamp for camera-side loss and reader history overwrite (Codex position, "The other side"). Its objection is that the delta spread is not measured. Rule 10 answers that objection with a probe gate. Option (b) answers it by removing the data that the probe needs.

### 2.3 The gain of option (b) has no phase 1 reader

1. `[F]` No project code receives pixels or reads `image_raw` (facts 1.1.1).
2. `[F]` K: no file outside `docs/` in the worktree contains `tf2`, `static_transform`, `robot_state_publisher`, `use_ros_time`, `use_sim_time`, or `rosbag`. This confirms the Claude position §2.3 item 2.
3. `[A]` R1 names one in-process consumer that reads `ImageFrame`, not the header (`docs/architecture/image-acquisition-planning/register.md:594`).
4. `[F]` The Jazzy bag recorder stores `source_timestamp` for each message (`ros:ros2/rosbag2/rosbag2_transport/src/rosbag2_transport/recorder.cpp:796-802`). A bag made under option (a) keeps both the device stamp and the host publish time. Checked. The other branch, at `:782-787`, also stores `source_timestamp`.

The Codex strength, a host `header.stamp` for each ROS reader, serves readers that R1 excludes. If Logan names such a reader, rule 1 changes to `use_ros_time: true` (section 3).

### 2.4 The Codex boundary argument does not separate the options

1. The Codex position says option (b) "gives d22 the earlier host boundary check". The header stamp precedes the source timestamp by the interval of section 2.1 item 7. The Codex position itself calls that interval unmeasured. No citation supports a material effect.
2. `[F]` In c1, the first Mono8 frame arrived 79 ms before the `stream_start` reply (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:160`). Checked. Both positions set the boundary before `stream_start`, not at the reply. This fact therefore does not favor either option.
3. `[F]` Both host stamps follow the queue wait and transform (`driver:vimbax_camera/src/vimbax_camera.cpp:458-482`). Checked. This limit applies to both options equally.

### 2.5 The cost of option (a) is bounded

1. `[F]` The source timestamp is not in the message. A reader sees it only through the message-info form (`ros:ros2/rclcpp/rclcpp/include/rclcpp/any_subscription_callback.hpp:110-113`). This is the only added code under option (a).
2. `[F]` The RMW fills `source_timestamp`. R12 assumes CycloneDDS. The bring-up test of rule 11 catches a zero or foreign value before a consumer sees it.
3. `[F]` The driver reads `use_ros_time` on each frame (facts 1.6.4). Rule 3 keeps a run-time change from mixing two clocks in one stream.

### 2.6 Rules taken from the Codex position

1. `use_sim_time: false` on the application node. If sim time became active there, a boundary read from the node clock would not be on `CLOCK_REALTIME`. Rule 8 reads `CLOCK_REALTIME` directly, and rule 2 removes the trap for other node clock users.
2. Fixed time parameters during acquisition. The Codex rule is correct, and facts 1.6.4 shows the failure it prevents.
3. The second probe condition in rule 10. A narrow delta spread alone does not show that the counter finds real loss. The driver "N frames missing" log (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1596-1601`) gives a reference count. The 30 Hz profile comes from c3 (`docs/architecture/image-acquisition-planning/codex/camera/c3.md:50`).

### 2.7 Citations that do not support their claim

1. Codex position, recommendation, second paragraph. `docs/architecture/image-acquisition-planning/register.md:594-605` does not contain the assumption that the host wall clock does not step during acquisition. The R rows say nothing about clock steps. The claim is a valid `[A]`, but the citation does not support it.
2. Codex position, "The other side", last paragraph. The claim that option (b) "gives d22 the earlier host boundary check" has no citation. Section 2.4 item 1 gives the reason it does not hold as a material effect.
3. Codex position, evidence item 4. `docs/architecture/image-acquisition-planning/claude/camera/c1.md:149-161` is accurate. It supports a rule against a boundary at the reply, which neither position proposes. It does not support option (b).
4. Claude position §2.1 item 6. c1 §3.4 item 9 gives the 1.85 to 2.09 ms interval only. The c1 table at `docs/architecture/image-acquisition-planning/claude/camera/c1.md:130-135` shows that the receipt time is Unix time. The citation supports the claim only together with that table.
5. Claude position §2.2 item 4. The example compares a device stamp rule with a host stamp gap rule. Neither position proposes a host stamp gap rule. The Codex position omits the counter. The example shows a real limit of host stamps, but it does not answer the Codex position. Section 2.2 item 5 gives the comparison that applies.
6. Claude position §2.2 item 4 uses the 69.7 Hz period. The phase 1 profile is 30 Hz (c3 §3 item 4). At 33.3 ms, six free buffers cover about 200 ms. The argument holds at both rates, with a longer block before loss at 30 Hz.

All other citations in both positions support their claims. I checked each driver and `ros:` citation against the source, and each planning file citation against the file.

## 3. Working assumption and cost to reverse

This verdict states a combination, so no fallback assumption is necessary. The terms below say when to reverse it.

1. Reverse to option (b) if one of these events occurs:
   - Logan names a reader of `image_raw` outside the adapter that needs a host `header.stamp`.
   - The feed probe fails a condition of rule 10, and no other phase 1 rule uses `device_stamp_ns`.
   - The rule 11 test fails under the deployed RMW.
2. To reverse, change these items:
   - `use_ros_time` in `camera.yaml`.
   - The adapter fill of `host_stamp_ns`, from `source_timestamp` to `header.stamp`.
   - The adapter fill of `device_stamp_ns`, to empty.
   - The rule 3 test, which then expects `true`.
3. Consumer code does not change, because consumers read `host_stamp_ns` under both options. Only the stats code reads `device_stamp_ns`, and it already handles an empty value.
4. Cost to reverse: Low. One configuration value, two adapter fills, and one test change.

What depends on the verdict:

| Part | Dependency |
|---|---|
| d3 frame fields | The two accessors and their contract text |
| d8 adapter callback | The message-info form |
| d12 loss counters | Whether `stamp_gap_frames` has a value, and the probe conditions |
| d22 admission after reconnect | The `host_stamp_ns` boundary on `CLOCK_REALTIME` |
| Bring-up | The `camera.yaml` lines, the application node parameter, and two tests |
| Testing | Fake frames set both stamps. Fakes also cover an empty `device_stamp_ns` |
