# Decision register for image acquisition

Checkpoint `589fea7`. Inputs: `coordinator/facts.md`, `claude/positions.md`, `codex/positions.md`, the camera checks `claude/camera/c1.md` and `claude/camera/c2.md`, and the two camera request files from the positions tasks.

## How to read this register

1. Labels:
   - `[F]` is a fact with a citation.
   - `[A]` is a working assumption. It is cheap to reverse.
   - `[Q]` is an open question.
2. Citation forms:
   - `path:line` is a path from the project worktree root.
   - `driver:path:line` is a path from the driver root `vimbax_ros2_driver/`.
   - `ros:path:line` is a path from the ROS 2 Jazzy source root `ros2-jazzy/src/`.
   - `facts 1.4.3` is `coordinator/facts.md`, section 1.4, item 3. That item carries its own source citations.
   - `c1 §3.3` is `claude/camera/c1.md`, section 3.3. `c2` is `claude/camera/c2.md`.
   - "Claude D9" is entry D9 in `claude/positions.md`. "Codex D9" is entry D9 in `codex/positions.md`.
3. Status values:
   - Agreed. The positions match in substance.
   - Settled. The positions differ, and the evidence favors one option or one combination. The entry gives the dissent in one sentence.
   - Disputed. The positions differ, the evidence does not settle them, and the choice crosses the drafting split. The dispute tasks are in `coordinator/emits/register.json`, and they block register-final.
4. The register id of each entry is the lower-case design choice id, for example `d20`. Dispute tasks use that id as the `issue` parameter.
5. "Crosses the split" has the meaning that `coordinator/facts.md` section 5 gives it.

## Summary

| Id | Topic | Status | Decision in one line | Follows |
|---|---|---|---|---|
| d1 | Package layout | Agreed | Three new targets in `venimapping_camera`. No new package. | Both |
| d2 | Port shape | Agreed | A separate ROS-free `FrameSource` port. `CameraGateway` does not change. | Both |
| d3 | Frame type and metadata | Settled | ROS-free `ImageFrame` with layout, identity, and bit-depth fields. Stamp fields follow d20. | Combination |
| d4 | Memory model | Agreed | Keep the received message alive through a type-erased shared owner. No pixel copy. | Both |
| d5 | Thread and executor model | Settled | One node and one executor thread in phase 1. The feed probe decides a split. | Codex |
| d6 | Error vocabulary | Settled | New contractual `kAcquisition` domain with the union of both code lists. | Combination |
| d7 | Consumer API | Agreed | Pull with `take(timeout)` and `try_take()`. Empty result on timeout. | Both |
| d8 | Transport mechanism | Agreed | Plain rclcpp subscription on `<namespace>/image_raw`. Bring-up limits the driver to the raw plugin. | Both |
| d9 | Subscriber QoS | Settled | BEST_EFFORT, KEEP_LAST 2, VOLATILE, fixed in the adapter. | Claude |
| d10 | Queue bound and `buffer_count` | Settled | Capacity per subscription, default 1, drop oldest. `buffer_count` 7 in `camera.yaml`. | Codex |
| d11 | Frame identity | Agreed | `receive_seq` per `FrameSource` plus a controller stream epoch. The stamp-based epoch rule follows d20. | Both |
| d12 | Loss reporting | Settled | Union of both counter sets. The stamp gap estimate is provisional. | Combination |
| d13 | Several consumers | Settled | One subscription, one queue per `FrameSubscription`. Phase 1 allows one feed and one get image. | Combination |
| d14 | Pixel interpretation | Settled | Pass pixels unchanged. Add `significant_bits` from the PixelFormat readback. | Claude |
| d15 | Calibration pairing | Agreed | No `CameraInfo` in phase 1. | Both |
| d16 | Stream ownership | Agreed | The controller worker owns stream calls and feature writes through counted users. | Both |
| d17 | Feed start, readiness, close | Agreed | Match before start. The last release stops the stream. | Both |
| d18 | Configuration ownership | Settled | `settings_file` applies the profile at open and reopen. The controller reads it back and corrects it while stopped. | Codex, with Claude readback |
| d19 | Start and stop failure recovery | Settled | Format check, one reconciliation stop, then `kWedged`. | Combination |
| d20 | Timestamp source | Disputed | Dispute tasks `dispute-d20-*`. | None yet |
| d21 | Driver changes | Agreed | No patch in phase 1. Four candidate patches go to Logan. | Both |
| d22 | Disconnect, silence, outage | Settled | 250 ms floor, suspend admission, check connection, read back profile, new epoch. | Combination |
| d23 | Frame source for get image | Agreed | Sample a running stream, or start and stop free run when idle. No trigger in phase 1. | Both |
| d24 | Freshness rule | Agreed | First frame that the fan-out gives to the get image subscription after it opens. | Both |
| d25 | Idle behavior | Agreed | One subscription for the `FrameSource` lifetime. Cold calls start the stream. | Both |
| d26 | Deadline and timeout result | Settled | One caller deadline, default 2000 ms. The stop is outside it. | Claude |
| d27 | Trigger association | Agreed | Phase 2 only. | Both |
| d28 | Get image during a feed | Agreed | Share the stream. Get image has its own queue. | Both |
| d29 | Get image caller interface | Agreed | C++ only in phase 1. | Both |

## 1. Structure

### D1. Package layout

- Id: `d1`
- Question: Do the new parts go in `venimapping_camera`, or in a new package?
- Options: (a) New targets in `venimapping_camera`. (b) A ROS-free package for ports and policy, with adapters in `venimapping_camera`. (c) One new acquisition package.
- Claude position: (a). Three targets: `venimapping_camera_frame_api`, `venimapping_camera_vimbax_frame_source`, and `venimapping_camera_acquisition`.
- Codex position: (a). The ROS-free acquisition code and the rclcpp frame adapter are separate targets.
- Evidence:
  - `[F]` The package already splits a ROS-free INTERFACE target from the ROS adapter target (`src/venimapping_camera/CMakeLists.txt:22-48`).
  - `[F]` Headers under `include/` install. Private headers under `src/` do not (facts 1.1.22).
- Status: Agreed.
- Decision: Add three targets to `venimapping_camera`:
  1. A ROS-free frame API target with `ImageFrame`, `FrameSource`, and `FrameSubscription`.
  2. A ROS-free acquisition target with the controller. It links only the two ROS-free API targets.
  3. A VimbaX frame source target. It links `rclcpp` and `sensor_msgs`.
- Rationale: The target graph already enforces the ROS-free rule. A package boundary adds a manifest and an export and moves no rule. Both planners name the same trigger to reopen: a consumer that must build without a ROS underlay.

### D2. Port shape

- Id: `d2`
- Question: Does acquisition extend `CameraGateway`, or use a separate data-plane port?
- Options: (a) A separate ROS-free frame port. (b) Frame methods on `CameraGateway`. (c) No port. Consumers subscribe to the driver topic.
- Claude position: (a). `FrameSource` makes `FrameSubscription` objects. `CameraGateway` does not change.
- Codex position: (a). Keep the v1 `FrameSource` port. The controller composes it with `CameraGateway`.
- Evidence:
  - `[F]` Gateway calls block on one bound worker thread. The thread check detects misuse and does not synchronize (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-47`).
  - `[F]` The gateway already has `stream_start`, `stream_stop`, and `feature_command_run` (facts A3).
  - `[F]` Pixels leave the driver only on `image_raw` (facts 1.3.5).
- Status: Agreed.
- Decision: (a). A separate ROS-free `FrameSource` port. `CameraGateway` keeps its 30 methods. The controller composes the two ports.
- Rationale: A frame push from an executor thread does not fit the bound-worker contract of the gateway. Option (c) leaves no project code to assign the sequence, the epoch, and the loss counts. Reopen if Logan states that all frame consumers are other ROS nodes (R1).

### D3. Frame type and metadata

- Id: `d3`
- Question: Which fields does the project frame carry, and does it hide all ROS types?
- Options: Hide all ROS types, or expose `sensor_msgs::msg::Image`. Fields from: width, height, `step`, encoding, `is_bigendian`, device stamp, host stamps, TF frame name, receive sequence, stream epoch, source bit depth, and `CameraInfo`.
- Claude position: Hide ROS. Fields: `width`, `height`, `step`, `encoding`, `tf_frame`, `significant_bits`, `device_stamp_ns`, `publish_stamp_ns`, `receipt_stamp_ns`, `receive_seq`, `stream_epoch`, and a pixel span.
- Codex position: Hide ROS. Fields: width, height, `step`, encoding, `is_bigendian`, the driver host stamp, `frame_id`, receive sequence, stream epoch, and immutable data. The steady receipt time stays inside `FrameSource`. Defer source bit depth and `CameraInfo`.
- Evidence:
  - `[F]` The driver sets `encoding`, `width`, `height`, and `is_bigendian` from each SDK frame (facts 1.3.10).
  - `[F]` `header.frame_id` names a TF frame, not a frame instance. The message carries no counter (facts 1.6.6, 1.6.7).
  - `[F]` The 16-bit wire encoding does not record the source bit depth (facts 1.3.7).
- Status: Settled. The stamp fields are in the scope of dispute d20.
- Decision: `ImageFrame` hides all ROS types. It carries `width`, `height`, `step`, `encoding`, `is_bigendian`, `tf_frame`, `significant_bits` (d14), `receive_seq`, `stream_epoch`, and a read-only pixel span. It carries no `CameraInfo` (d15). The stamp fields follow d20. The steady-clock receipt time stays inside `FrameSource` for the silence check (d22).
- Rationale: Both planners hide ROS and carry the same layout and identity fields. `is_bigendian` costs one field, and the driver sets it on each frame. The name `tf_frame` keeps the word "frame" for one image, so the TF name and the frame identity cannot mix. Dissent: Codex names the field `frame_id` and defers `significant_bits`.

### D4. Memory model

- Id: `d4`
- Question: Does the frame keep the received message alive, or own a copy of the pixels?
- Options: (a) Keep the message alive through a type-erased shared pointer. (b) Copy into a project buffer. (c) Copy into a pool of preallocated buffers.
- Claude position: (a). No pixel copy.
- Codex position: (a). A retained `ImageFrame` keeps the payload alive after close.
- Evidence:
  - `[F]` CycloneDDS does not loan `sensor_msgs/Image`. Each subscription gets a deserialized heap copy (facts 1.3.13).
  - `[F]` One Mono8 feed at the default rate carries 93.2 MB/s (c1 §3.3).
- Status: Agreed.
- Decision: (a). The frame holds a `std::shared_ptr<const void>` that owns the received message. The pixel span points into that message. A copy of `ImageFrame` shares the buffer.
- Rationale: A copy adds 93.2 MB/s of memory traffic at Mono8 and gives no safety, because the message is already heap memory.

### D5. Thread and executor model

- Id: `d5`
- Question: Which thread runs the image subscription callback, and does it share a node and an executor with the gateway?
- Options: (a) One node and one executor thread for gateway replies and image callbacks. (b) One node, a separate callback group, and a `MultiThreadedExecutor`. (c) A separate node and executor thread for images.
- Claude position: (c). Three threads: a controller worker, a control executor, and a data executor on a second node.
- Codex position: (a). One application node and one `SingleThreadedExecutor` thread, as in v1. Blocking controller calls stay on the gateway worker.
- Evidence:
  - `[F]` If the bound gateway thread also spins the node, each call times out (facts 1.1.17). Both positions use a separate worker thread.
  - `[F]` Both adapters take a caller-owned `rclcpp::Node&` (facts 1.1.11, A62).
  - `[F]` The executor thread deserializes each 1.34 MB frame (facts 1.3.13, c1 §3.2).
  - `[A]` One frame take costs a few milliseconds. The gateway timeout is 2000 ms, which is about 140 Mono8 frame periods.
- Status: Settled.
- Decision:
  1. The image callback runs on an executor thread. It admits the frame and fans it out. It never blocks and never calls the gateway.
  2. The controller worker is a separate thread and the only gateway caller.
  3. In phase 1, one node and one `SingleThreadedExecutor` thread spin the gateway clients and the image subscription.
  4. The feed probe measures the gateway service round-trip time while stopped and while streaming Mono8 at 69.7 Hz.
  5. If the streaming value is more than 5 ms above the stopped value, the composition root moves the subscription to a second node and executor.
- Rationale: The data-plane contract in items 1 and 2 is the same in both positions. The thread layout changes only the composition root, so the choice is cheap to reverse. Both planners name the same measurement as the test that decides. Dissent: Claude wants the second node from the start, so that frame load can never delay a gateway reply.

### D6. Error vocabulary

- Id: `d6`
- Question: Which new failures need codes, and in which domain?
- Options: (a) No new domain, private gateway diagnostics. (b) A new contractual acquisition domain. (c) Driver codes and empty results only.
- Claude position: (b). `ErrorDomain::kAcquisition` with `kFeedClosed`, `kDeadlinePassed`, `kStreamWedged`, `kFormatNotStreamable`, `kProfileMismatch`, `kSubscriptionNotMatched`, `kWrongThread`, and `kTriggerNoFrame` reserved for phase 2.
- Codex position: (b). Contractual codes for feed closed, request busy, deadline passed, invalid configuration, and stream recovery required. Empty result for an ordinary feed pull timeout.
- Evidence:
  - `[F]` `ErrorDomain` has two values, `kDriver` and `kGateway` (`src/venimapping_camera/include/venimapping_camera/types/error.hpp:17-20`).
  - `[F]` Gateway diagnostics 1 to 5 are for logs and tests only (`src/venimapping_camera/src/gateway_support/gateway_errors.hpp:15-22`).
  - `[F]` A wedge, a format refusal, and a deadline need different caller actions (facts 1.4.3, 1.4.4, c1 §3.1).
- Status: Settled.
- Decision: Add `ErrorDomain::kAcquisition` and an installed header for its codes. Driver errors pass unchanged. Gateway diagnostics stay private. A feed `take` timeout is an empty result, not an error. The codes are:

  | Code | The controller or the frame source returns it when |
  |---|---|
  | `kFeedClosed` | `take` or `try_take` runs after `close()` or after the `FrameSource` is gone |
  | `kDeadlinePassed` | get image has no frame when its caller deadline passes (d26) |
  | `kRequestBusy` | a request exceeds the phase 1 limit of one open feed or one outstanding get image (d13) |
  | `kStreamWedged` | the controller is in `kWedged` (d19). The text says to restart the driver process |
  | `kFormatNotStreamable` | `PixelFormat` is outside the profile formats on the driver gate (d19) |
  | `kProfileMismatch` | a profile readback still differs after the corrective writes (d18) |
  | `kSubscriptionNotMatched` | no publisher matched the image subscription within the match limit (d17) |
  | `kWrongThread` | a second thread calls `take` or `try_take` on one `FrameSubscription` (d7) |
  | `kTriggerNoFrame` | reserved for phase 2 (d27) |

- Rationale: Both planners want a contractual domain and an empty pull timeout. The union keeps each code that some other entry in this register needs. Each code maps to a different caller action. The error-vocabulary owner assigns the numbers. Dissent: Codex groups the format refusal and the readback failure under one invalid-configuration code.

## 2. Data plane

### D7. Consumer API

- Id: `d7`
- Question: Do consumers pull frames with a timeout, get a callback, or subscribe to the driver topic?
- Options: (a) Pull with a timeout. (b) A callback on a project thread. (c) A callback on the executor thread. (d) The ROS topic is the contract.
- Claude position: (a). `take(timeout)` returns `Expected<std::optional<ImageFrame>>`. `try_take()` does not wait. `close()` is idempotent and wakes a waiting `take`.
- Codex position: (a). `take(timeout)` and `try_take()` on a single-consumer feed. An idempotent close wakes a blocked pull. The image callback never runs consumer code.
- Evidence: `[F]` A consumer callback on an executor thread that calls the gateway makes each gateway call time out (facts 1.1.17).
- Status: Agreed.
- Decision: (a), with the Claude signature. One consumer thread per `FrameSubscription`. `close()` runs from any thread.
- Rationale: Pull keeps consumer code off the executor thread. A callback wrapper over `take` is possible later without a port change.

### D8. Transport mechanism

- Id: `d8`
- Question: Does the feed use an rclcpp subscription, an `image_transport` subscriber, or VmbC without the driver?
- Options: (a) Plain rclcpp subscription on `image_raw`. (b) `image_transport` subscriber. (c) A direct VmbC adapter.
- Claude position: (a), with the message-info callback form. Bring-up sets `image_raw.enable_pub_plugins: ["image_transport/raw"]`.
- Codex position: (a). Use the same namespace input as the gateway. The design must not depend on a raw-only plugin install (Codex T10).
- Evidence:
  - `[F]` The driver opens the camera in exclusive mode (`driver:vimbax_camera/src/vimbax_camera.cpp:164-185`).
  - `[F]` `image_transport` advertises one subtopic per installed plugin unless `image_raw.enable_pub_plugins` limits it (facts 1.3.4).
- Status: Agreed.
- Decision: (a). A plain `rclcpp::Subscription<sensor_msgs::msg::Image>` on `<namespace>/image_raw`, with the namespace input that the gateway uses. Bring-up adds the raw-only plugin filter to `camera.yaml`. The callback form with `rclcpp::MessageInfo` depends on d20.
- Rationale: The filter makes the topic set independent of the host install, which meets the Codex T10 concern. Option (c) moves capture, reconnect, and bring-up into the project.

### D9. Subscriber QoS and history depth

- Id: `d9`
- Question: Does the subscriber use RELIABLE or BEST_EFFORT, and which history depth?
- Options: (a) RELIABLE with a small depth. (b) BEST_EFFORT with depth 1 to 3. (c) Configurable, with one default.
- Claude position: BEST_EFFORT, KEEP_LAST 2, VOLATILE, set once per `FrameSource`.
- Codex position: BEST_EFFORT, KEEP_LAST 1, VOLATILE, fixed in the adapter.
- Evidence:
  - `[F]` A RELIABLE publisher matches a BEST_EFFORT subscriber (facts 1.3.3).
  - `[F]` A reader KEEP_LAST overwrite sets no status (facts X8, `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`).
  - `[F]` `ros2 topic hz` subscribes with `qos_profile_sensor_data` (`ros:ros2/ros2cli/ros2topic/ros2topic/verb/hz.py:42`, `:264-268`), which is BEST_EFFORT, KEEP_LAST 5 (`ros:ros2/rmw/rmw/include/rmw/qos_profiles.h:25-30`). In c1, that reader got 69.7 Hz Mono8 with a longest interval of 16 ms (c1 §3.3 item 2).
- Status: Settled.
- Decision: BEST_EFFORT, KEEP_LAST 2, VOLATILE. The adapter fixes the values for the `FrameSource`. No per-feed QoS.
- Rationale: Both planners choose BEST_EFFORT, and c1 shows a BEST_EFFORT reader with no gap on an idle host. On depth, an overwrite in the reader history is invisible (X8). Depth 2 lets one late take move the older frame into the project queue, where an eviction counts it. The cost is 1.34 MB. Dissent: Codex prefers depth 1, because depth 2 can deliver an older unread frame.

### D10. Queue bound, overflow rule, and `buffer_count`

- Id: `d10`
- Question: What caps the frames the project holds, which frame drops at capacity, and which `buffer_count` does the driver use?
- Options: Capacity 1, 2 to 4, or caller-set. Drop the oldest or the newest. `buffer_count` 7 or a measured value.
- Claude position: Each `FrameSubscription` has a queue, capacity set at subscribe, default 2, range 1 to 8, drop oldest. `buffer_count: 7` in `camera.yaml`, never changed at run time.
- Codex position: One pending feed slot and one get image slot, replace the oldest, count the eviction. `buffer_count` 7.
- Evidence:
  - `[F]` With `buffer_count` 7, about 3100 Mono8 frames and 630 Mono12 frames streamed with no "frames missing" log (c1 §3.7 item 2).
  - `[F]` A `buffer_count` change during a disconnect calls `is_streaming()` on a null camera (facts 1.10.1).
  - `[F]` One Mono8 frame is 1337472 bytes (c1 §3.2).
- Status: Settled.
- Decision:
  1. Each `FrameSubscription` owns one bounded queue. The capacity is a subscribe option, default 1, range 1 to 4.
  2. At capacity, the queue drops the oldest frame and counts the eviction.
  3. Get image uses capacity 1.
  4. Bring-up writes `buffer_count: 7` in `camera.yaml`. No code changes it at run time.
- Rationale: Both planners drop the oldest and keep `buffer_count` 7 in the file. R9 gives newer frames priority, so a default of 1 gives the consumer the newest frame at each take, and each drop stays visible as an eviction. The upper bound of 4 keeps one queue at 5.35 MB of Mono8 for R5. Dissent: Claude wants default 2 to absorb one frame period of consumer delay.

### D11. Frame identity and sequence scope

- Id: `d11`
- Question: How does the project identify a frame, and does the sequence survive a stream restart or a reconnect?
- Options: (a) Receive sequence per subscription. (b) Receive sequence plus a stream epoch. (c) Device stamp as identity. (d) SDK `frameID` from a driver patch.
- Claude position: (b). `receive_seq` per `FrameSource`, never reset. The epoch starts at each controller `stream_start`, and the adapter also starts one when the device stamp goes back or jumps by more than the silence threshold.
- Codex position: (b). `receive_seq` per shared subscription, increasing across starts. The controller opens a new epoch at each logical start and at each observed outage recovery.
- Evidence:
  - `[F]` The message carries no counter. The CycloneDDS RMW leaves both sequence fields unset (facts 1.6.7, 1.6.9).
  - `[F]` The driver restarts the stream after a reopen with no project call (facts 1.9.7).
- Status: Agreed.
- Decision: (b). `receive_seq` is a 64-bit count per `FrameSource`. It increments in the subscription callback and never resets. `stream_epoch` is a 32-bit count. The controller starts a new epoch before each `stream_start` that it makes and before it admits frames after an outage recovery (d22). The adapter rule that starts an epoch from a stamp discontinuity is in the scope of dispute d20.
- Rationale: Both planners use the same two numbers and the same controller rule. The only difference is the stamp rule, which needs the device stamp that d20 decides.

### D12. Loss reporting

- Id: `d12`
- Question: Which loss counters does the feed offer, and how does it state what it cannot see?
- Options: Counters for queue evictions, `message_lost`, a stamp or `frameID` gap, and stall time. A list of invisible losses, or none.
- Claude position: `queue_evictions` per subscription. `frames_received`, `transport_lost`, and `stamp_gap_frames` per source. The contract lists what no counter shows.
- Codex position: Callbacks, slot evictions, and frames discarded for invalid layout or an inactive epoch. The RMW loss count where supported. Time since the last valid frame. The contract documents the visibility gaps.
- Evidence:
  - `[F]` Each loss site in facts 1.7 shows in a different place, and a reader history overwrite shows nowhere (facts 1.7, X8).
  - `[F]` Mono8 receipt intervals were 13 to 16 ms against a 14.34 ms period (c1 §3.3 item 2).
  - `[Q]` The spread of consecutive device stamp deltas is not measured.
- Status: Settled.
- Decision:
  1. Per `FrameSubscription`: `queue_evictions`.
  2. Per `FrameSource`: `frames_received`, `frames_discarded` (invalid layout or inactive epoch), `transport_lost` from the `message_lost` event where the RMW supports it, and the age of the last admitted frame on the steady clock.
  3. `stamp_gap_frames` is provisional. d20 decides its stamp source. The feed probe measures the delta spread. If the spread exceeds 0.5 frame period with no loss, the counter goes.
  4. The contract lists each loss that no counter shows: SDK incomplete frames, SDK buffer shortage, reader history overwrite, loss at an epoch start, and loss in trigger mode.
- Rationale: The two sets do not conflict. Each counter reports a different loss site, and a counter is an additive field. Dissent: Codex does not propose a stamp gap estimate.

### D13. Several consumers

- Id: `d13`
- Question: Can two feeds be open at the same time, and do they share one subscription?
- Options: (a) One feed only. (b) Several feeds, one subscription, one queue each. (c) Several feeds, one subscription each.
- Claude position: (b). One ROS subscription. Each `FrameSubscription` has its own queue.
- Codex position: One open feed and one pending get image per camera, both fed from one subscription.
- Evidence:
  - `[F]` Each ROS subscription gets its own deserialized copy (facts 1.3.13). Both planners therefore use one subscription.
  - `[A]` R1 names one in-process consumer.
- Status: Settled.
- Decision:
  1. One `FrameSource` owns one image subscription.
  2. `FrameSource::subscribe(options)` returns a `FrameSubscription` with its own bounded queue (d10).
  3. The callback pushes each admitted frame to each open subscription.
  4. In phase 1, the controller allows one open feed and one outstanding get image. A further request returns `kRequestBusy`.
- Rationale: The queue object gives the feed and get image one type, and the Codex slot pair is the case with two queues. The controller limit keeps the R5 memory bound under R1. A change to the limit is one constant. Dissent: Codex prefers two fixed slots, because per-consumer queues add memory policy beyond R1.

### D14. Pixel interpretation

- Id: `d14`
- Question: Does the project pass the encoding unchanged, or undo or record the MSB shift?
- Options: (a) Pass unchanged. (b) Add the source bit depth to the frame. (c) Undo the shift in the adapter.
- Claude position: (b). Pass pixels and `encoding` unchanged. Add `significant_bits`, 8 or 12, from the `PixelFormat` that the controller reads before start.
- Codex position: (a). Pass unchanged with Mono8 as the first profile. Document that Mono12 publishes as `mono16` with the upper 12 bits significant.
- Evidence:
  - `[F]` Only Mono8 and Mono12 pass the gate on this camera. Mono12 publishes as `mono16` with a 4-bit left shift (c1 §3.1, facts 1.3.7).
  - `[F]` The message does not record the shift (facts 1.3.7).
- Status: Settled.
- Decision: (b). Pass pixels and `encoding` unchanged. The frame carries `significant_bits` from the `PixelFormat` value of its epoch. The controller gets that value from the readback that d19 and d22 already make before each epoch.
- Rationale: Codex rejects the field because it needs trusted metadata. d19 and d22 read `PixelFormat` back before each epoch, so the value is a readback and not a guess. The cost is one field. Dissent: Codex wants to defer the field until a consumer needs more than 8 bits.

### D15. Calibration pairing

- Id: `d15`
- Question: Does a frame come with its `CameraInfo`, and how is a zero `K` reported?
- Options: (a) No `CameraInfo` in phase 1. (b) Pair by header in the adapter. (c) Load calibration in the project.
- Claude position: (a). Bring-up leaves `camera_info_url` empty.
- Codex position: (a). If pairing comes later, a zero `K[0]` means no calibration.
- Evidence: `[F]` No calibration file exists for this camera (c1 §3.5 item 5). `K[0] == 0.0` means uncalibrated (facts 1.8.3).
- Status: Agreed.
- Decision: (a). No `CameraInfo` subscription and no `CameraInfo` field in phase 1. A later pairing uses the shared header and treats `K[0] == 0` as no calibration.
- Rationale: No calibration exists to pair, and R11 does not need intrinsics.

## 3. Stream control and configuration

### D16. Stream ownership

- Id: `d16`
- Question: Which one component may call `stream_start` and `stream_stop`?
- Options: (a) One controller owns both, with a count of users. (b) Each feed starts and stops the stream. (c) Bringup or an operator starts the stream.
- Claude position: (a). The `AcquisitionController` worker owns stream calls and all feature writes through counted leases. It also owns `TriggerSelector`.
- Codex position: (a). The controller owns project stream calls and camera configuration. An open feed and a pending get image count as separate users.
- Evidence:
  - `[F]` Start and stop serialize in the driver. A start while active succeeds with no effect (facts 1.4.8, 1.4 table).
  - `[F]` `camera_status()` moves `TriggerSelector` (facts 1.5.7, c2 §3.3).
- Status: Agreed.
- Decision: (a). Only the controller worker calls stream services and feature setters. Each open feed and each outstanding get image holds one lease. The worker calls `stream_start` when the count goes from 0 to 1 and `stream_stop` when it goes from 1 to 0.
- Rationale: A count in the project is the only way to know when the last user leaves. Reopen if Logan states that another client must also control the stream (R15).

### D17. Feed start, readiness, and close

- Id: `d17`
- Question: Does opening a feed start the stream, what marks the feed ready, and what does close do if another user still needs frames?
- Options: Open starts the stream or only arms delivery. Ready means subscription created, reader matched, or first frame received. Close stops always, never, or at the last user.
- Claude position: Open takes a lease. Before the first `stream_start` of an epoch, the worker waits for `get_publisher_count() >= 1`, polled every 10 ms for at most 1000 ms, else `kSubscriptionNotMatched`. The last release stops the stream.
- Codex position: The frame port reports a raw publisher match. The controller starts the stream if idle and returns the feed after a successful start reply. A frame may fill the slot before the reply. Close clears the slot and wakes the consumer. The last release queues a stop.
- Evidence:
  - `[F]` The first frame arrives 30 to 43 ms after the driver handles `stream_start`, and 69 to 79 ms before the reply (c1 §3.5).
  - `[F]` A subscription made before `stream_start` does not prove a match, because the publisher is VOLATILE (facts A66).
  - `[F]` `get_publisher_count()` reads the DDS matched status of the reader (`ros:ros2/rclcpp/rclcpp/src/rclcpp/subscription_base.cpp:277-281`).
- Status: Agreed.
- Decision:
  1. `feed_open` takes a lease and opens a `FrameSubscription` before any start.
  2. Before each project `stream_start`, the worker waits for a matched publisher through a `FrameSource` query. The match limit is 1000 ms, inside any caller deadline. No match gives `kSubscriptionNotMatched`.
  3. `feed_open` returns after a successful start reply, or at once if the stream already runs. Frames that arrive before the reply stay in the queue.
  4. Close clears the queue, wakes a waiting `take`, and releases the lease. The last release makes the worker stop the stream.
- Rationale: Both planners use "reader matched" as ready and the last release as the stop. c1 shows that a reader made after the reply misses 3 to 5 frames.

### D18. Configuration ownership and order

- Id: `d18`
- Question: Do pixel format, size, rate, and trigger mode come from `settings_file`, a camera `UserSet`, or service writes, and when can they change?
- Options: (a) `settings_file` on each open and reopen. (b) A camera `UserSet`. (c) Service writes by the controller before each start. (d) A mix, with rate and exposure writable at run time.
- Claude position: (c). A project `AcquisitionProfile` is the only source. The controller writes values that differ while stopped and reads each back. No `settings_file` in phase 1. `ExposureTime` may change during a stream.
- Codex position: (a). One verified free-run profile in the bring-up `settings_file` for open and reopen. Read back shape, `PixelFormat`, trigger state, and rate before each project start. No profile change during a stream in phase 1.
- Evidence:
  - `[F]` The driver loads `settings_file` inside `initialize_camera` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:390-400`). On a reconnect, it sets the restart flag only after that function returns (`:561-566`). The graph thread then restarts the stream (`:590-593`).
  - `[F]` A failed load only logs an error, and the driver continues (`driver:vimbax_camera/src/vimbax_camera_node.cpp:394-399`).
  - `[F]` `PixelFormat`, `Width`, and `TriggerMode` are read only while streaming (c1 §3.6).
  - `[F]` The gateway does no readback, and a setter that times out can still apply (facts 1.1.10, 1.1.14).
  - `[A]` A power cycle resets values that the project wrote through services (facts 1.9.10, R16).
- Status: Settled.
- Decision:
  1. Bring-up keeps one camera settings file for the phase 1 profile. `camera.yaml` sets `settings_file` to its installed path. The driver loads it on each open and reopen.
  2. A project `AcquisitionProfile` file in the bringup config holds the expected values for readback.
  3. Before each project `stream_start` and after each reconnect, the controller reads back each profile value. It writes `FrameStart` to `TriggerSelector` before it reads `TriggerMode`.
  4. If a value differs, the stream must be stopped first (d22). The controller then writes the profile values in this order: shape, the selector and `TriggerMode`, the rate pair, and `ExposureTime`.
  5. The controller reads back again. A remaining difference gives `kProfileMismatch`.
  6. Phase 1 makes no feature write during a stream.
  7. A bring-up test starts the driver with the settings file and checks the readback against the `AcquisitionProfile` file.
- Rationale: Only `settings_file` applies the profile before the driver restarts the stream after a reopen. Service writes come after that restart, so a reset shape value streams until the controller stops the stream. The silent load failure is covered by the readback that both planners require. Claude names power-cycle loss plus a profile that differs from the power-on values as its trigger to change. A 30 Hz rate (R4) already differs from the c1 values. Dissent: Claude wants service writes only, because a failed file load is invisible and a camera XML file is hard to review.

### D19. Start and stop failure recovery

- Id: `d19`
- Question: How does the project detect and recover from a state left at `kStarting` or `kStopping`?
- Options: (a) Check `PixelFormat` before each start. (b) Detect the wedge, then restart the driver process. (c) Patch the driver. (d) Report it to the operator only.
- Claude position: (a) and (d). A two-value allow-list. `kWedged` on -15, or on `status.streaming` true with no active stream. Each lease request returns `kStreamWedged`. A reconnect clears the wedge. Patch (c) if Logan accepts patches.
- Codex position: Check `PixelFormat` against the intersection of the profile and the gate. After a failed or uncertain operation, make one bounded reconciliation stop. If it returns -15 or the stopped state stays unconfirmed, require a supervised driver restart. Revalidate the profile and wait for a match before resuming.
- Evidence:
  - `[F]` Each error return in `start_streaming` leaves `kStarting`, and each in `stop_streaming` leaves `kStopping`. No service resets the state (facts 1.4.1 to 1.4.4).
  - `[F]` `stream_stop` returns -15 in `kStarting` and in `kStopping` (facts 1.4 table).
  - `[F]` `is_streaming()` is true for `kActive` and `kStarting` only (facts X3, `driver:vimbax_camera/src/vimbax_camera.cpp:1508-1513`). A `status` test alone therefore misses a `kStopping` wedge.
  - `[F]` A reconnect with a wedged state starts a stream on a new camera object (facts 1.10.5).
  - `[F]` Four formats that the camera offers fail the gate (c1 §3.1).
- Status: Settled.
- Decision:
  1. Before each project `stream_start`, the controller reads `PixelFormat`. If the value is outside the profile formats that are on the driver gate, it returns `kFormatNotStreamable` and makes no call. The phase 1 profile allows Mono8 only.
  2. If `stream_start` or `stream_stop` fails or times out, the worker makes one `stream_stop` to reconcile, if the camera is reachable.
  3. If that stop returns -15, or the stopped state stays unconfirmed, the controller enters `kWedged`. It closes frame admission. Each lease request returns `kStreamWedged` with no service call.
  4. The project does not restart the driver process. The error text tells the operator to restart it.
  5. A detected reconnect clears `kWedged`. The controller then reads back the profile and waits for a match before it admits frames.
- Rationale: One stop tells a wedge from a transient failure, and it catches `kStopping`, which the `status` test misses. A gateway timeout can leave a call applied, so a timeout needs the same reconciliation. The project does not own the driver process (facts 1.1.2). Dissent: Claude detects the wedge from -15 or `status` and has no reconciliation stop.

### D20. Timestamp source

- Id: `d20`
- Question: Does bringup keep `use_ros_time: false` or set it to true? Which stamp fields does `ImageFrame` carry?
- Options: (a) Keep false and add host stamps in the adapter. (b) Set true. (c) Keep false and map device time to host time with a measured offset. (d) Patch the driver to publish both stamps.
- Claude position: (a). `device_stamp_ns` from `header.stamp`, `publish_stamp_ns` from the DDS source timestamp, and `receipt_stamp_ns` from the rmw receipt time.
- Codex position: (b). `use_ros_time: true` and `use_sim_time: false`. The image stamp is driver processing time. Local deadlines use the steady clock.
- Evidence:
  - `[F]` With `use_ros_time: false`, the stamp is camera-clock nanoseconds with an unknown origin, not comparable with the host clock (c1 §3.4 items 1 to 4, 8).
  - `[F]` The offset to the host clock changes by 10.4 ms between Mono8 and Mono12 and drifts about 4 ppm (c1 §3.4 item 5, c2 §3.5 item 2).
  - `[F]` With `use_ros_time: true`, the stamp is `node->now()` after the transform and before publish (facts 1.6.3).
  - `[F]` The CycloneDDS RMW puts the DDS source timestamp and a receipt time in the message info (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3280-3283`). On one host, the two differ by about 2 ms at Mono8 (c1 §3.4 item 9).
  - `[A]` The device stamp is taken before the payload transfer (c1 §3.4 item 6).
- Status: Disputed.
- Decision: None. register-final records the outcome of the dispute tasks.
- Rationale for the dispute:
  1. Both options meet R10 on one host. The evidence does not show that one is better for the project.
  2. Option (a) gives the adapter a superset of stamps. But every reader of `image_raw` outside the adapter, for example a bag recorder or a TF lookup, sees the camera clock.
  3. Option (b) gives each ROS reader a host stamp. But it removes the device stamp, which the Claude rules in d11 and d12 use.
  4. The choice crosses the split. Bring-up sets the parameter, and the data plane defines the stamp fields.
- Scope of the dispute. The outcome decides these parts of other entries:
  1. The stamp fields of `ImageFrame` (d3).
  2. The adapter rule that starts an epoch from a stamp discontinuity (d11).
  3. The stamp source of the provisional `stamp_gap_frames` (d12).
  4. The stamp that marks the epoch boundary for frame admission after a reconnect (d22).
  5. Whether the adapter uses the `rclcpp::MessageInfo` callback form (d8).
- Questions for the dispute positions:
  1. Does any phase 1 rule need the device stamp for a result that host stamps cannot give?
  2. Under R1, does any reader of `image_raw` outside the adapter need `header.stamp` on the host clock?
  3. Is the DDS source timestamp under `use_ros_time: false` an equal substitute for the header stamp under `use_ros_time: true`?

### D21. Driver changes

- Id: `d21`
- Question: Does the design work around driver defects, or patch the fork?
- Options: (a) Work around all. (b) Patch the fork for a listed subset. (c) Replace the data path with VmbC.
- Claude position: (a) for the design. Recommend three patches as a Logan decision: the wedge reset, the `buffer_count` null check, and `TriggerSelector` save and restore in `status`. The double shared lock is a fourth candidate.
- Codex position: (a). No phase 1 patch. Keep `autostream` off, set `buffer_count` only at launch, and supervise recovery. A wedge or lock patch needs regression coverage first.
- Evidence:
  - `[F]` The project pins a fork tag (`README.md:13-15`).
  - `[F]` The `:604` guard has no effect with `autostream: 0` (facts 1.4.12).
  - `[F]` The `buffer_count` callback calls `is_streaming()` on a possibly null `camera_` (facts 1.10.1).
- Status: Agreed.
- Decision: (a). No part of phase 1 needs a patch. The candidate patches for Logan, in order: the wedge reset, the `buffer_count` null check, `TriggerSelector` save and restore in `status`, and the double shared lock. Each patch lands with a fault-injection test of the path it changes.
- Rationale: Both planners keep the design free of patches and treat the patches as a Logan decision. The test condition comes from Codex and costs nothing in phase 1.

### D22. Disconnect, silence, and outage

- Id: `d22`
- Question: How long without a frame before the project checks the connection, and what does it report and do after a reconnect?
- Options: A fixed silence time or a multiple of the frame period. On reconnect: keep the driver restart and mark a new epoch, restart under project control, or close the feed.
- Claude position: Threshold `max(500 ms, 5 periods)`. Then `connection_status()`. `kOutage` keeps the feed open, polled every 250 ms. After reconnect, read back the profile and keep the driver restart if all values match. Else stop, apply, and start a new epoch. `kStalled` gets one stop and start cycle.
- Codex position: Threshold `max(250 ms, 5 periods)`. Suspend delivery and clear pending frames at the stall. Check `connected` and poll at 250 ms. Label a service failure as connection unknown. Read back the profile and open a new epoch before admitting frames. One guarded start if no frame comes, then d19. With zero users, reconcile a driver restart to stopped.
- Evidence:
  - `[F]` No ROS event exists for connection. Each camera service returns -3 while the camera is unavailable (facts 1.9.2, 1.9.5).
  - `[F]` The driver restarts a stream that was active or starting at the disconnect and ignores the result (facts 1.9.7).
  - `[F]` Mono8 receipt intervals were at most 16 ms (c1 §3.3 item 2).
  - `[A]` A false silence alarm costs one `connection_status()` call (Claude D22).
- Status: Settled.
- Decision:
  1. The worker checks silence on a 100 ms tick while a lease exists and the stream runs in free run.
  2. The threshold is `max(250 ms, 5 x nominal frame period)` on the steady clock, from the last admitted frame or from the `stream_start` request.
  3. At the threshold, the source stops admission and clears the queues. The worker calls `connection_status()`.
  4. False or -3 gives `kOutage`. Another service failure gives "connection unknown". The feed stays open, and `take` returns empty. The worker polls every 250 ms while a user remains.
  5. After a reconnect, the worker reads back the profile (d18). If a value differs, it stops the stream, writes the profile, reads back, and starts again.
  6. The worker starts a new epoch before admission resumes. The stamp rule that excludes frames from before the boundary follows d20.
  7. If no admitted frame comes within one more threshold, the worker makes one `stream_start`. A failure goes to d19.
  8. If `connection_status()` is true and silence continues, the state is `kStalled`. The worker makes one stop and start cycle. A failure goes to d19. Continued silence leaves `kStalled` with no more action.
  9. If a reconnect restarts the stream with zero users, the worker stops it.
- Rationale: Both planners keep the feed open, check the connection, read back the profile, and mark a new epoch. The 250 ms floor detects an outage sooner, and the Claude assumption says a false alarm costs one call. Suspended admission keeps frames with an unverified profile from consumers after a driver restart. Dissent: Claude uses a 500 ms floor and lets the adapter mark the epoch from device stamps.

## 4. Get image

### D23. Frame source for get image

- Id: `d23`
- Question: Does get image take a frame from a running stream, start and stop a stream for one frame, or use a software trigger?
- Options: (a) Sample a running stream. (b) Start and stop per call. (c) Software trigger. (d) Choose per call.
- Claude position: (a) when a lease is active, (b) when idle. No trigger in phase 1.
- Codex position: Sample the active free-run stream when a feed is open. If idle, start free run for one frame and stop at the last release. Defer the trigger.
- Evidence:
  - `[F]` One `TriggerSoftware` gives one frame only under the current `FrameStart` selector (c2 §3.2, §3.3).
  - `[F]` `TriggerMode` is read only while streaming (c1 §3.6), so a trigger capture must stop a feed.
- Status: Agreed.
- Decision: (a) while a lease is active, (b) when idle. The software trigger is out of phase 1.
- Rationale: R6 needs only "received after the request". A trigger adds the selector race and stops the feed, which R8 forbids.

### D24. Freshness rule

- Id: `d24`
- Question: Which frame counts as the answer?
- Options: (a) The next frame received after the request. (b) The first frame with a host stamp after the request. (c) The first frame exposed after the request.
- Claude position: (a). The first frame with a `receive_seq` above the value read at the request.
- Codex position: (a). The first valid frame that the callback admits after the request arms its slot. Arming and admission share one lock.
- Evidence: `[F]` A frame received after the request can have been exposed before it (facts A68). R6 accepts this.
- Status: Agreed.
- Decision: (a). The answer is the first frame from an admitted epoch that the fan-out pushes to the get image subscription after it opens. Opening the subscription and the fan-out take the same lock. The frame therefore has a `receive_seq` above any frame that existed at the request.
- Rationale: The two formulations give the same frame. The lock rule from Codex makes the order exact.

### D25. Idle behavior and subscription lifetime

- Id: `d25`
- Question: If no stream runs, does get image start one, keep one running, or fail? Does an idle project keep a matched subscription?
- Options: (a) A stream and a subscription per call. (b) Keep a matched subscription and start the stream per call. (c) Keep both running. (d) Fail if no stream runs.
- Claude position: (b). An optional linger time after the last release, default 0.
- Codex position: (b). The idle subscription holds no admitted frame. A cold call waits for a match before the start.
- Evidence: `[F]` With `autostream: 0`, a reader does not start the driver (facts 1.4.12). A stopped stream publishes nothing.
- Status: Agreed.
- Decision: (b). The `FrameSource` keeps its subscription for its whole life. A cold get image waits for the match (d17), starts the stream, takes one frame, and releases its lease. `ControllerOptions` has a linger time, default 0.
- Rationale: A matched idle reader costs no traffic, and it removes the match time from each cold call.

### D26. Deadline and timeout result

- Id: `d26`
- Question: Which steps count against the get image deadline, and what does a timeout return?
- Options: One deadline for all steps, or one per step. The stop inside or outside. An empty result or an error.
- Claude position: One caller deadline, default 2000 ms, for the lease, the format check, the match, the start, and the first frame. The stop is outside it. A timeout is `kDeadlinePassed`. The caller waits on a future, and the worker can finish a call later.
- Codex position: One steady deadline that also covers the required stop, with the last 250 ms reserved for it. Warm calls capped at two frame periods. Deadline-aware gateway calls. A stop failure is reported with the request result and blocks new starts until stopped state is confirmed.
- Evidence:
  - `[F]` A successful stop takes at least 100 ms (facts 1.4.6).
  - `[F]` The gateway has one timeout for all calls, set at `create` (facts 1.1.11).
  - `[F]` A frame arrives about 79 ms before the start reply at Mono8 (c1 §3.5).
- Status: Settled.
- Decision:
  1. `GetImageOptions::deadline` is one steady-clock deadline from the call, default 2000 ms. A caller can set a shorter one.
  2. It covers the lease, the format check, the profile readback, the match, `stream_start`, and the first frame.
  3. The `stream_stop` after delivery is outside it.
  4. A passed deadline returns `kDeadlinePassed`.
  5. The caller waits on a future with the deadline. The worker finishes a pending gateway call after the caller leaves. The gateway keeps its one timeout per call.
  6. A failed stop goes to d19. It blocks new starts until the reconciliation ends.
- Rationale: The stop cannot change the frame that the caller already holds. A stop failure becomes a controller state in d19, which both planners accept, and the next request sees it. Including the stop adds at least 100 ms to each cold call. A deadline-aware gateway call changes the existing gateway API for no gain, because the future already bounds the wait. Dissent: Codex holds that a success return before the stop hides an uncertain stream state.

### D27. Trigger association and restore

- Id: `d27`
- Question: If a trigger is used, how does get image find its frame, handle an uncertain command result, and restore the trigger features?
- Options: Association by the first frame after the command, by device stamp, or by a quiet interval. Restore all trigger features under each selector, also on failure.
- Claude position: Phase 2 only. Selector write before each trigger write and each command. No `status` while trigger mode is on. First frame after the command send, 500 ms frame deadline, `kTriggerNoFrame`. Restore `FrameStart` and `Off`.
- Codex position: Defer to phase 2. Exclusive stream, matched reader, quiet interval, one command, first frame after dispatch, no retry. Stop before restore. Save and restore all selectors and the original selector last.
- Evidence:
  - `[F]` Two of nine commands returned error code 0 and gave no frame (c2 §3.2 item 3).
  - `[F]` The frame arrives before the `command_run` reply (c2 §3.4).
- Status: Agreed.
- Decision: Phase 2 only. Phase 1 has no trigger code. Both rule sets agree on the core: no `status` during a trigger, a selector write before each selector-dependent call, the first frame after the command send, and a frame deadline as the only proof. The phase 2 design merges the two restore sequences.
- Rationale: No phase 1 code depends on it. The detailed restore order is a phase 2 choice.

### D28. Get image during an open feed

- Id: `d28`
- Question: What happens if get image runs while a feed is open?
- Options: (a) Share the feed stream. (b) Stop the feed, take a frame, and restore the feed. (c) Fail with an error.
- Claude position: (a). Get image takes a lease and a one-frame `FrameSubscription`.
- Codex position: (a). Get image uses its own slot and does not take the pending feed frame.
- Evidence: `[F]` `TriggerMode` is locked during acquisition (c1 §3.6). R8 states that get image must not stop a feed.
- Status: Agreed.
- Decision: (a). Get image takes a lease and a capacity-1 subscription on the shared source (d13). The feed queue does not change.
- Rationale: The feed keeps its frames, and the warm wait is at most about one frame period.

### D29. Get image caller interface

- Id: `d29`
- Question: Is get image a C++ call only, or also a ROS service for other nodes?
- Options: (a) C++ only. (b) C++ plus a thin ROS service node. (c) ROS service only.
- Claude position: (a).
- Codex position: (a). `get_image` returns `Expected<ImageFrame>`.
- Evidence: `[F]` No project node consumes frames today (facts 1.1.1).
- Status: Agreed.
- Decision: (a). `AcquisitionController::get_image` returns `Expected<ImageFrame>`.
- Rationale: R1 names one in-process consumer. A service wrapper can come later with no port change.

## 5. Camera requests

| Request | Part | Result | Reason |
|---|---|---|---|
| `codex/camera-requests/positions-codex.json` | Rate enable, a 30 Hz write while stopped, and the delivered rate | Accepted as check `camera-c3` on codex | It decides the rate in the d18 profile and the R4 assumption. If 30 Hz does not work, the phase 1 profile stays at 69.7 Hz free run. |
| same | `status` call to read each `TriggerMode` | Removed | c2 read `Off` under all seven selectors, and the runner restored them (c2 §3.1 item 5, `camera-log.md`). A `status` call moves `TriggerSelector`. |
| `claude/camera-requests/positions-claude.json` | BEST_EFFORT depth 2 against RELIABLE over 20 s each | Rejected | c1 already measured a BEST_EFFORT reader at 69.7 Hz with no gap (d9 evidence). An idle-host run cannot test T9 load, so the result cannot change d9. |
| same | Spread of consecutive header stamp deltas | Rejected | The allowed check tools print stamps but cannot compute 1400 deltas, and c2 §2 item 5 reports no loops or scripts. The feed probe measures it (d12). |
| same | Rate writable while stopped, and the delivered rate after a 30.0 write | Merged into `camera-c3` | Same question as the codex request. |
| same | Rate writable while streaming, and a 20.0 write during a stream | Rejected | d18 allows no feature write during a stream in phase 1. The answer cannot change a phase 1 choice. |

The check `camera-c3` lists `AcquisitionFrameRateEnable` before `AcquisitionFrameRate`. The runner restores in reverse order, so it writes the rate while the enable can still be true, then the enable (`runner/camera_guard.py:138-146`).

## 6. Emitted tasks

The file `coordinator/emits/register.json` adds these tasks. Each one blocks register-final.

| Task | Template | Tool | Depends on |
|---|---|---|---|
| `camera-c3` | camera-check | codex | none |
| `dispute-d20-position-claude` | dispute-position | claude | none |
| `dispute-d20-position-codex` | dispute-position | codex | none |
| `dispute-d20-judge-claude` | dispute-judge | claude | both d20 positions |
| `dispute-d20-judge-codex` | dispute-judge | codex | both d20 positions |

## 7. Working assumptions

The R and T ids come from `coordinator/facts.md` section 4. "Now" gives the assumption after c1, c2, and both positions. Cost to reverse is Low when one value or one file changes, Medium when a contract or a sequence changes, and High when a package or an owner changes.

### 7.1 Requirements from Logan

| Id | Assumption now | What depends on it | Cost to reverse |
|---|---|---|---|
| R1 | One C++ consumer in the same process, on the driver host. No other node reads frames from the project. | d1, d2, d7, d13, d20, d29 | High. Another-process consumer moves the contract toward a ROS topic or service. |
| R2 | Full sensor, 1296 x 1032, no binning. Interfaces take size and `step` from each frame. | d10 byte bounds, d18 profile | Low. Profile values and byte numbers change. |
| R3 | Mono8 in phase 1. Mono12 only if a consumer needs more than 8 bits. | d14, d18, d19 allow-list | Low. One profile value. `significant_bits` already carries the depth. |
| R4 | The design must carry 69.7 Hz Mono8, 93.2 MB/s. The phase 1 profile uses 30 Hz only if `camera-c3` shows that the write works and gives 29 to 31 Hz. | d9, d10, d18, d22 threshold, bring-up DDS tuning | Low. One profile value. Period-based thresholds follow it. |
| R5 | The project holds at most `(queue capacity + frames the consumer holds) x 1.34 MB` per subscription. No fixed byte budget. | d10, d13 | Low. One range limit. |
| R6 | "Received after the request" is enough. | d23, d24, d27 | Medium. "Exposed after the request" brings the trigger path into phase 1. |
| R7 | A cold get image may take up to 2 s. Warm calls take about one frame period. | d25, d26 | Low above 200 ms. Below that, d25 must keep the stream warm. |
| R8 | Get image less than once per second. It may overlap a feed and must not stop it. | d13, d25, d28 | Low. The linger time and the request limit change. |
| R9 | The feed may drop frames. Newer frames have priority. Each visible drop is counted. | d9, d10, d12 | High if loss must be zero. RELIABLE delivery and driver identity enter. |
| R10 | Consumers need a stamp on the host clock. No PTP or hardware sync. | d20 | Medium. Exposure alignment needs a new time contract. |
| R11 | No intrinsics in phase 1. | d3, d15 | Low. One subscription and one field. |
| R12 | Driver and consumers on one host with CycloneDDS. | d8, d9, d20 | Medium. A second host puts host stamps on two clocks and may need compressed transport. |
| R13 | The design works without a fork patch. | d19, d21 | Low. Patches remove workarounds and change no interface. |
| R14 | An outage does not close a feed. The feed reports it and starts a new epoch. | d11, d22 | Low. `take` returns an error instead of empty. |
| R15 | While the project acquires, no other client writes features, calls stream services, or calls `status`. | d16, d18, d27 | Medium. Shared control needs `status` checks before each decision. |
| R16 | A power cycle resets service writes. The profile must apply again after each reopen. | d18, d22 | Medium. If writes persist, d18 can drop the settings file. |

### 7.2 Technical assumptions

| Id | Assumption now | What depends on it | Cost to reverse |
|---|---|---|---|
| T3 | Free run gives 69.7 Hz Mono8 and 45.1 Hz Mono12 at `ExposureTime` 4999.455 us (c1 §3.3). `camera-c3` tests 30 Hz. | R4, d10, d22 | Low |
| T4 | The device stamp origin and its exposure event stay unknown. | d20 | Low if d20 chooses host stamps. Medium if a rule needs the origin. |
| T7 | `AcquisitionFrameRate` writability during a stream stays unknown. Phase 1 does not need it. | Phase 2 live rate control | Low |
| T9 | A RELIABLE reader can make the driver block in `publish`. d9 avoids it. A RELIABLE tool such as `ros2 topic echo` can still cause it. | d9, d10, bring-up notes | Low |
| T10 | The installed `image_transport` plugins are unknown. The bring-up filter removes the dependency. | d8 | Low |
| T11 | Host socket buffers are not tuned. Bring-up lists the 8 MiB values as a host check. | d9, load results | Low |
| T12 | Match time is unknown. d17 waits on the match, so no rule needs the number. The feed probe records it. | d17, d25 | Low |
| P1 | The camera power-on values equal the phase 1 shape values. | d18, d22 reconnect path | Low. The corrective-write path already exists. |
| P2 | The settings file and the `AcquisitionProfile` file describe the same values. A bring-up test checks this. | d18 | Low. One test. |
| P3 | One frame take costs a few milliseconds on the executor thread. | d5 | Low. The composition root changes. |
| P4 | The double shared lock does not hang on glibc. It stays a patch candidate. | d21 | Medium if an unplug test hangs. A fork patch is then needed. |
| P5 | A `buffer_count` change during a disconnect crashes the driver. Bring-up sets it only in the file. | d10, d21 | Low |

## 8. Neutrality check

The coordinator runs on Claude and checked each Settled entry against its evidence, not its author.

| Outcome | Entries |
|---|---|
| Agreed | d1, d2, d4, d7, d8, d11, d15, d16, d17, d21, d23, d24, d25, d27, d28, d29 |
| Settled toward Claude | d9, d14, d26 |
| Settled toward Codex | d5, d10, d18 |
| Settled as a combination | d3, d6, d12, d13, d19, d22 |
| Disputed | d20 |

In d19 and d22, the combination takes the detection and admission rules from Codex. In d6 and d13, it takes the type shape and the names from Claude. In d3 and d12, it takes the union of both field sets.
