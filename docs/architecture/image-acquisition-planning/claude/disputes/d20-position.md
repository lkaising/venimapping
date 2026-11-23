# Claude position on dispute d20, timestamp source

Checkpoint `44322da`. Inputs: `register.md` entry D20, `coordinator/facts.md`, `claude/trace.md`, `codex/trace.md`, `claude/positions.md`, `codex/positions.md`, and camera checks c1, c2, and c3.

Labels and citation forms follow `register.md`, "How to read this register". In addition, `ros:` paths below are from the ROS 2 Jazzy source root, and "K" marks a check of the source that I made for this file.

## 1. Recommendation

Option (a), narrowed. I change my earlier position in three places. Section 1.3 lists them.

### 1.1 Rules for the drafters

1. Bring-up writes `use_ros_time: false` and `use_sim_time: false` in `camera.yaml`, under the existing `/**/vimbax_camera` key. No code changes `use_ros_time` at run time.
2. The adapter subscribes with the message-info callback form. This closes the open part of d8.
3. `ImageFrame` carries two stamps and no other stamp field:

   ```cpp
   // Sketch only. Both values are nanoseconds.
   std::int64_t host_stamp_ns() const noexcept;                   // host CLOCK_REALTIME at the driver publish call
   std::optional<std::int64_t> device_stamp_ns() const noexcept;  // camera clock, origin and exposure event unknown (T4)
   ```

4. The adapter fills `host_stamp_ns` from `MessageInfo::get_rmw_message_info().source_timestamp`.
5. The adapter fills `device_stamp_ns` from `header.stamp`, as `sec * 1000000000 + nanosec`.
6. The steady-clock receipt time stays inside `FrameSource` for the silence check (d22). The frame has no receipt stamp.
7. Consumers that need a host time (R10) read `host_stamp_ns`. The contract states that it marks the driver publish event, not the exposure.

### 1.2 Effect on the entries in the scope of the dispute

| Entry | Rule |
|---|---|
| d3 | The stamp fields are `host_stamp_ns` and `device_stamp_ns`, as in section 1.1. |
| d8 | The callback takes `std::shared_ptr<const sensor_msgs::msg::Image>` and `const rclcpp::MessageInfo &`. |
| d11 | No stamp rule starts an epoch. Only the controller starts an epoch, as d11 and d22 already state. |
| d12 | `stamp_gap_frames` uses `device_stamp_ns` deltas in free run. The feed probe measures the spread of both stamp deltas. The d12 removal rule stays. |
| d22 | The epoch boundary is a host `CLOCK_REALTIME` time that the worker records when it opens the epoch. The source admits a frame only if `host_stamp_ns` is at or after the boundary. |

### 1.3 Changes from my earlier position

1. I remove `receipt_stamp_ns` from the frame. Codex D3 is correct that no consumer needs a second host event. The feed probe can log publish-to-receipt latency without a frame field.
2. I rename `publish_stamp_ns` to `host_stamp_ns`. The name then keeps one meaning under both options, which the fallback in section 5 uses.
3. I withdraw the d11 adapter rule that starts an epoch from a device stamp step. The settled d22 rule already starts an epoch at each detected outage. A camera power cycle takes longer than the 250 ms silence floor, so the controller sees it first `[A]`.

## 2. Evidence

### 2.1 Question 3 of the register. Is the DDS source timestamp an equal substitute for the header stamp under `use_ros_time: true`?

Yes, on one host with CycloneDDS and the raw-only plugin filter. The two values come from the same clock, in the same thread, a few calls apart.

1. `[F]` With `use_ros_time: true`, the driver sets `header.stamp = node_->now()` in the frame callback (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1608-1609`).
2. `[F]` `node->now()` reads the ROS clock. If sim time is not active, the ROS clock returns system time (`ros:ros2/rcl/rcl/src/rcl/time.c:65-70`). System time is `CLOCK_REALTIME` (`ros:ros2/rcutils/src/time_unix.c:63-66`).
3. `[F]` The CycloneDDS RMW reads `dds_time()` at the start of `rmw_publish` and writes the sample with that time (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:1967-1969`). On POSIX, `dds_time()` is `CLOCK_REALTIME` (`ros:eclipse-cyclonedds/cyclonedds/src/ddsrt/src/time/posix/time.c:21-25`). The reader gets it as `source_timestamp` (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3280`).
4. `[F]` Between the two clock reads, the driver builds `CameraInfo` and calls `CameraPublisher::publish` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1620-1631`). That call publishes the image before `camera_info` (`ros:ros-perception/image_common/image_transport/src/camera_publisher.cpp:135-136`).
5. `[F]` `image_transport` publishes to each plugin that has a subscriber, in list order (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:183-187`). With the raw-only filter of d8, the raw plugin is the only one. `[A]` The gap between the two clock reads is then microseconds.
6. `[F]` The source timestamp came 1.85 to 2.09 ms before receipt at Mono8, and both values are Unix time (c1 §3.4 item 9).
7. `[F]` The driver is a separate process (facts 1.1.2), so rclcpp intra-process delivery cannot bypass the RMW message info.

The substitute is not equal in two ways. Section 3 weighs both.

1. `[F]` The source timestamp is not in the message. Only a reader that uses the message-info callback form sees it (`ros:ros2/rclcpp/rclcpp/include/rclcpp/any_subscription_callback.hpp:110-113`).
2. `[F]` The RMW fills it. Another RMW can fill it differently or not at all. R12 assumes CycloneDDS.

### 2.2 Question 1. Does a phase 1 rule need the device stamp for a result that host stamps cannot give?

Yes, one rule: the d12 `stamp_gap_frames` estimate. The d11 and d22 rules do not need it.

1. `[F]` The driver frame thread pops a complete frame, transforms it, stamps it, publishes it, and only then requeues the SDK buffer (`driver:vimbax_camera/src/vimbax_camera.cpp:458-482`, `:1745-1757`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1631-1633`). A host stamp therefore includes the queue wait, the transform, and the scheduling of that thread.
2. `[A]` The device stamp is taken before the payload transfer (c1 §3.4 item 6). It does not include any host delay.
3. `[A]` A RELIABLE reader, for example `ros2 topic echo`, can block the driver in `publish` (register T9, facts 1.3.14). Frames then wait in the frame queue and publish back to back after the block ends.
4. Measurable consequence `[A]`. Take an 80 ms block at Mono8, 14.34 ms period, `buffer_count` 7. The blocked frame holds one buffer. The other six cover about 86 ms, so the SDK loses no frame.
   - A host-stamp gap rule sees one delta of about 80 ms. It adds `round(80 / 14.34) - 1 = 5` lost frames. The consumer then receives all five.
   - A device-stamp gap rule sees regular deltas of one period. It adds 0, which is correct.
   - If the block exceeds the buffers, only the device stamps show the frames that the camera exposed and the SDK could not store.
5. `[F]` The driver reports SDK frame ID gaps only in its log (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1596-1601`). No loss signal reaches the message (facts 1.7). The device stamp is the only per-frame value from before the host pipeline that reaches the project.
6. `[F]` Register d12 item 3 makes the counter depend on a feed probe measurement of the device stamp delta spread. Under option (b) the probe cannot make that measurement without a change to `camera.yaml`.
7. `[F]` The d22 boundary rule compares each frame with a time that the worker records. The worker clock is the host clock, so the rule needs a host stamp. A device stamp cannot serve, because its offset to the host clock is about 1795400876 s and changes with the format (c1 §3.4 items 3 and 5). Both options give a host stamp.
8. `[F]` The d24 freshness rule uses the fan-out order and `receive_seq`, not a stamp (register d24).

### 2.3 Question 2. Under R1, does a reader of `image_raw` outside the adapter need `header.stamp` on the host clock?

No reader in phase 1.

1. `[F]` No project code receives pixels or reads `image_raw` (facts 1.1.1).
2. `[F]` K: at `44322da`, no file outside `docs/` in the worktree contains `tf2`, `static_transform`, `robot_state_publisher`, `use_ros_time`, `use_sim_time`, or `rosbag`. The project has no TF tree and no time synchronizer.
3. `[F]` The Jazzy bag recorder stores the receipt time and the source timestamp of each message (`ros:ros2/rosbag2/rosbag2_transport/src/rosbag2_transport/recorder.cpp:796-802`). A bag made under option (a) therefore keeps a host publish time for each frame.
4. `[A]` R1 names one in-process C++ consumer. It reads `ImageFrame`, not the header.

### 2.4 Summary of what each option gives

| Need | Option (a), as recommended | Option (b) |
|---|---|---|
| R10 host stamp in `ImageFrame` | `host_stamp_ns` from the source timestamp | `host_stamp_ns` from `header.stamp` |
| d22 boundary | Yes, from `host_stamp_ns` | Yes, from `host_stamp_ns` |
| d12 gap estimate free of host delay | Yes | No. Host delay enters the estimate |
| d12 probe of the device delta spread | Yes | Not without a `camera.yaml` change |
| Host time in `header.stamp` for other ROS readers | No. Camera clock, about 12674 s at c1 | Yes |
| Device stamp kept in bags and on the wire | Yes | No. Lost for each frame published |
| Message-info callback form | Needed | Not needed |

## 3. The other side

### 3.1 The strongest case for option (b)

1. Each ROS reader gets a host stamp in the header with no special callback. `rviz`, `message_filters`, TF lookups, and bag playback by header all work as their users expect.
2. If R1 changes and another process reads frames, the contract moves toward the ROS topic (register R1). Those readers then need a host `header.stamp`.
3. Option (a) depends on a value that the RMW fills. A change of RMW can change or remove it.
4. The device stamp has an unknown origin and exposure event (T4). The d12 counter that uses it is provisional and can still go.
5. Option (b) gives a smaller frame contract with one stamp.

### 3.2 Why it loses

1. Points 1 and 2 serve readers that do not exist in phase 1 (section 2.3). R1 has no such reader. If one appears, the switch is one line in `camera.yaml` and one fill in the adapter (section 5). Consumer code does not change, because it reads `host_stamp_ns` under both options.
2. The two options are not symmetric in what they destroy. Option (a) keeps the device stamp on the wire and the host publish time in the message info and in bags. Option (b) discards the device stamp for each frame, and no later reader can get it back.
3. Point 3 is real, and R12 limits it. A bring-up test reads the first frame and checks that `host_stamp_ns` is within 1 s of the adapter receipt time. A zero or foreign value then fails at bring-up, not in a consumer.
4. Point 4 argues for a measurement, not for option (b). Under option (b), the probe that d12 item 3 needs cannot run. The counter then goes by default, not by evidence.
5. Point 5 saves one optional field. The cost of that saving is the d12 estimate in section 2.2 item 4, which miscounts each publisher block as loss.

## 4. What evidence would change my recommendation

1. Logan names a reader of `image_raw` outside the adapter that needs `header.stamp` on the host clock, for example a time synchronizer or a TF lookup on a moving frame. Then I move to option (b), or to option (d) if Logan accepts patches (R13).
2. The feed probe shows that the device stamp delta spread exceeds 0.5 frame period with no loss. Then d12 removes `stamp_gap_frames`, no phase 1 rule uses the device stamp, and option (b) costs nothing in phase 1.
3. The feed probe shows that host stamp deltas stay within 0.5 frame period under a T9 load, with a RELIABLE `ros2 topic echo` reader and a slow consumer. Then the host stamp serves d12 as well, and the device stamp has no phase 1 use.
4. A bring-up run shows that `source_timestamp` is zero or not on the host clock under the deployed RMW.
5. Logan sets R12 to two hosts. This alone does not change the choice, because both host stamps then come from the driver host clock. It adds a time sync requirement to both options.

I make no camera request. The question that decides item 2 needs about 1400 stamp deltas, and the register rejected that check for the allowed tools (register section 5). The feed probe measures it.

## 5. Fallback

If the judges disagree, both planners can draft against this working assumption. The drafted interfaces are the same under option (a) and option (b). Only one configuration value differs.

1. `[A]` `ImageFrame` has `host_stamp_ns()` as an `std::int64_t` and `device_stamp_ns()` as an `std::optional<std::int64_t>`, as in section 1.1.
2. `[A]` `FrameSourceOptions` has `header_stamp_clock`, with the values `kDevice` and `kHost`.
3. `[A]` With `kDevice`, the adapter fills `host_stamp_ns` from the source timestamp and `device_stamp_ns` from `header.stamp`.
4. `[A]` With `kHost`, the adapter fills `host_stamp_ns` from `header.stamp` and leaves `device_stamp_ns` empty.
5. `[A]` The adapter uses the message-info callback form in both modes.
6. `[A]` `stamp_gap_frames` is an optional counter. It has a value only when `device_stamp_ns` has a value.
7. `[A]` The d22 boundary uses `host_stamp_ns` in both modes.
8. `[A]` The default is `kDevice` with `use_ros_time: false`, because that is the driver default (facts 1.1.5) and it keeps both stamps.
9. `[A]` A bring-up test reads the driver `use_ros_time` parameter and checks that it agrees with `header_stamp_clock`.

What depends on it:

| Part | Dependency |
|---|---|
| d3 frame fields | The two accessors and their meaning |
| d8 adapter callback | The message-info form |
| d12 loss counters | Whether `stamp_gap_frames` has a value |
| d22 admission after reconnect | The `host_stamp_ns` boundary |
| Bring-up `camera.yaml` | The `use_ros_time` and `use_sim_time` lines |
| Testing | Fake frames set both stamps. One bring-up test checks the mode and the source timestamp. |

Cost to reverse: Low. A change of option changes one `camera.yaml` value and one `FrameSourceOptions` value. Consumer code does not change, because consumers read `host_stamp_ns` in both modes. Only the stats code reads `device_stamp_ns`, and it already handles an empty value.
