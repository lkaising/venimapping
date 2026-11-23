# Claude positions on the image acquisition design choices

Checkpoint `25faa9d`. Inputs: `coordinator/facts.md`, `claude/trace.md`, `codex/trace.md`, camera checks c1 and c2, and v1.

## How to read this file

1. Labels:
   - `[F]` is a fact with a citation.
   - `[A]` is a working assumption. It is cheap to reverse.
   - `[Q]` is an open question.
2. Citation forms:
   - `path:line` is a path from the project worktree root.
   - `driver:path:line` is a path from the driver root `vimbax_ros2_driver/`.
   - `ros:path:line` is a path from the ROS 2 Jazzy source root `ros2-jazzy/src/`.
   - `facts 1.4.3` is `docs/architecture/image-acquisition-planning/coordinator/facts.md`, section 1.4, item 3. That item carries its own source citations.
   - `c1 §3.3` is `docs/architecture/image-acquisition-planning/claude/camera/c1.md`, section 3.3. `c2` is `claude/camera/c2.md` in the same folder.
3. Each choice has five parts: position, evidence, rejected options, what would change my mind, and cost to reverse.
4. Numbers in this file use the c1 values unless a part says otherwise. Mono8 full sensor is 1296 x 1032, 1337472 bytes per frame, 69.716 Hz free run, and a 14.34 ms frame period (c1 §3.2, §3.3).

## 1. Summary of the positions

| Id | Position in one line |
|---|---|
| D1 | Keep all new parts in `venimapping_camera`, as three new CMake targets. No new package. |
| D2 | A separate ROS-free frame port, `FrameSource` and `FrameSubscription`. |
| D3 | A ROS-free `ImageFrame` with three stamps, a receive sequence, a stream epoch, and significant bits. |
| D4 | Keep the received message alive through a type-erased shared pointer. No copy. |
| D5 | Three project threads: a controller worker, a control executor, and a data executor on a second node. |
| D6 | A new contractual `kAcquisition` error domain with seven codes and one code reserved for phase 2. |
| D7 | Pull with a timeout. An empty result on timeout. |
| D8 | A plain rclcpp subscription on `image_raw`. |
| D9 | BEST_EFFORT, KEEP_LAST 2, VOLATILE, set once per `FrameSource`. |
| D10 | Each `FrameSubscription` owns a queue of capacity 2 by default, drop oldest. `buffer_count` 7, written in `camera.yaml`. |
| D11 | `receive_seq` per `FrameSource` plus `stream_epoch` with two fixed start rules. |
| D12 | Queue evictions, `message_lost`, and a device-stamp gap count. The contract lists what stays invisible. |
| D13 | Several feeds share one subscription. Each feed has its own queue. |
| D14 | Pass pixels unchanged. Add `significant_bits`, 8 or 12. |
| D15 | No `CameraInfo` in the first phase. |
| D16 | The `AcquisitionController` worker owns stream start, stream stop, and all feature writes, through counted leases. |
| D17 | Open takes a lease. Ready means a matched reader, checked before `stream_start`. The last lease release stops the stream. |
| D18 | A project `AcquisitionProfile`, applied by the controller while stopped and checked by readback. No `settings_file` in the first phase. |
| D19 | Prevent with a two-value `PixelFormat` allow-list. Report a wedge as `kStreamWedged`. Fix it with a fork patch if Logan accepts patches. |
| D20 | Keep `use_ros_time: false`. Take two host stamps from the rmw message info. |
| D21 | The design works without a patch. Recommend three small fork patches as a Logan decision. |
| D22 | Silence threshold `max(500 ms, 5 frame periods)`, then `connection_status`, profile check after reconnect, and an epoch from the frame stamps. |
| D23 | Sample the running stream when a lease is active. Start and stop per call when idle. No trigger in the first phase. |
| D24 | The first frame with `receive_seq` above the value read at the request. |
| D25 | Keep the subscription matched for the `FrameSource` lifetime. Start the stream per call. |
| D26 | One caller deadline, default 2000 ms, for lease, start, and first frame. The stop is outside it. A timeout is `kDeadlinePassed`. |
| D27 | Phase 2 only. Selector write before each trigger write, no `status` while trigger mode is on, first frame after the command. |
| D28 | Share the feed stream. Get image takes the next frame from its own one-frame queue. |
| D29 | C++ only in the first phase. |

## 2. Structure

### D1. Package layout

1. Position. Add the new parts to `venimapping_camera` as three new targets. The targets are `venimapping_camera_frame_api` (ROS-free headers), `venimapping_camera_vimbax_frame_source` (rclcpp and `sensor_msgs`), and `venimapping_camera_acquisition` (links the two ROS-free API targets only).
2. Evidence.
   - `[F]` The package already separates a ROS-free INTERFACE target from the ROS adapter target (`src/venimapping_camera/CMakeLists.txt:22-48`).
   - `[F]` Private headers under `src/` are not installed. Headers under `include/` are installed (facts 1.1.22).
   - `[F]` The package exports `rclcpp` and `vimbax_camera_msgs` to all users (`src/venimapping_camera/CMakeLists.txt:75`). Under R1 the only consumer is a C++ process on the driver host, which already links `rclcpp`.
   - `[A]` The ROS-free boundary is a link rule between targets. A package boundary adds a `package.xml`, an export, and a build order, and moves no rule.
3. Rejected options.
   - (b) A ROS-free package for ports and policy. It doubles the package files for a boundary that the target graph already enforces. Its only gain is a consumer that must not see `vimbax_camera_msgs`, and R1 has no such consumer.
   - (c) One new acquisition package for ports, adapters, and policy. It splits the gateway and the frame source, which share a node, a namespace rule, and the error types.
4. What would change my mind. A consumer package that must build without `rclcpp` or `vimbax_camera_msgs`, or a second camera backend such as a direct VmbC adapter. Either one makes (b) the better choice.
5. Cost to reverse. Medium. A move to a new package changes `find_package` names and target names in each consumer, but the header paths can stay under `venimapping_camera/`.

### D2. Port shape

1. Position. Use a separate ROS-free data-plane port: `FrameSource` makes `FrameSubscription` objects, and each `FrameSubscription` gives frames by pull. `CameraGateway` does not change.
2. Evidence.
   - `[F]` `CameraGateway` calls block on one bound worker thread. The thread check detects misuse and does not synchronize (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-47`). A frame push from an executor thread does not fit that contract.
   - `[F]` The gateway already has `stream_start`, `stream_stop`, and `feature_command_run` (facts 1.1.9, A3). The control plane needs no new gateway method.
   - `[F]` No driver service returns pixels. Pixels leave the driver only on `image_raw` (facts 1.3.5).
3. Rejected options.
   - (b) Frame methods on `CameraGateway`. The 30-method port would get two thread contracts, and each gateway fake would need a frame path.
   - (c) No port. Consumers subscribe to the driver topic. Then no project code assigns the sequence, the epoch, or the loss counts, and controller tests need ROS.
4. What would change my mind. Logan states that all frame consumers are other ROS nodes (R1). Then the ROS topic is the contract, and the port has no in-process user.
5. Cost to reverse. Medium. Consumers would move from `take` calls to topic subscriptions, and the controller would lose its frame input for get image.

### D3. Frame type and metadata

1. Position. `ImageFrame` hides all ROS types. It carries `width`, `height`, `step`, `encoding`, `tf_frame`, `significant_bits`, `device_stamp_ns`, `publish_stamp_ns`, `receipt_stamp_ns`, `receive_seq`, `stream_epoch`, and a pixel span. It carries no `CameraInfo`.

   ```cpp
   // Sketch only. Copies share the pixel buffer.
   class ImageFrame {
    public:
     std::uint32_t width() const noexcept;
     std::uint32_t height() const noexcept;
     std::uint32_t step() const noexcept;
     std::string_view encoding() const noexcept;      // wire value, for example "mono8"
     std::string_view tf_frame() const noexcept;      // header.frame_id, a TF frame name
     std::uint8_t significant_bits() const noexcept;  // 8 for Mono8, 12 for Mono12
     std::int64_t device_stamp_ns() const noexcept;   // header.stamp, camera clock
     std::int64_t publish_stamp_ns() const noexcept;  // DDS source timestamp, host clock
     std::int64_t receipt_stamp_ns() const noexcept;  // rmw take time, host clock
     std::uint64_t receive_seq() const noexcept;
     std::uint32_t stream_epoch() const noexcept;
     std::span<const std::byte> data() const noexcept;
   };
   ```

2. Evidence.
   - `[F]` With `use_ros_time: false`, `header.stamp` is the camera clock in nanoseconds on this camera, because `DeviceTimestampFrequency` is absent (c1 §3.4 items 1, 2, 4).
   - `[F]` The CycloneDDS RMW copies the DDS `source_timestamp` into the message info and sets `received_timestamp` to `system_clock::now()` at take (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3280-3283`).
   - `[F]` rclcpp accepts a subscription callback with `std::shared_ptr<const Msg>` and `const rclcpp::MessageInfo &` (`ros:ros2/rclcpp/rclcpp/include/rclcpp/any_subscription_callback.hpp:110-113`).
   - `[F]` On one host, the source timestamp came 1.85 to 2.09 ms before receipt at Mono8, and both are Unix time (c1 §3.4 item 9).
   - `[F]` `header.frame_id` names a TF frame, not a frame instance. No counter reaches the message (facts 1.6.6, 1.6.7).
   - `[F]` The 16-bit wire encoding does not record the source bit depth (facts 1.3.7).
   - `[A]` `encoding` and `tf_frame` are views into the kept-alive message, so they cost no copy.
3. Rejected options.
   - Expose `sensor_msgs::msg::Image`. It puts ROS in each consumer and in each controller test. It also has no place for the sequence, the epoch, or the host stamps.
   - Only one stamp, as in v1. v1 had to choose between exposure-related time and host time. The message info gives both host stamps at no cost, so the choice is not needed.
   - Optional `CameraInfo` in the frame. No calibration file exists for this camera (c1 §3.5 item 5), and R11 does not need it. D15 has the reason.
4. What would change my mind. A consumer that needs the SDK `frameID` (only a driver patch gives it), or a measurement that shows `source_timestamp` is not on the host system clock.
5. Cost to reverse. Low. Fields are additive accessors, and the adapter fills them in one function.

### D4. Memory model

1. Position. The frame keeps the received `sensor_msgs::msg::Image` alive through a type-erased `std::shared_ptr<const void>`. The pixel span points into that message. The project makes no pixel copy.
2. Evidence.
   - `[F]` CycloneDDS does not loan `sensor_msgs/Image`. Each subscription gets a deserialized heap copy (facts 1.3.13). Holding that copy is safe for any time.
   - `[F]` At the default Mono8 rate, one feed carries 93.2 MB/s (c1 §3.3). A second copy in the project adds the same memory traffic again.
   - `[A]` One subscription for all feeds (D13) means one deserialized copy per frame, shared by all queues.
3. Rejected options.
   - (b) Copy into a project buffer. It adds 93.2 MB/s of copy work at Mono8 and 120.7 MB/s at Mono12, and it gives no new safety.
   - (c) Copy into a pool of preallocated buffers. The pool removes allocation cost but keeps the copy. The RMW allocates each message anyway.
4. What would change my mind. A profile that shows allocation of 1.34 MB messages at 69.7 Hz takes a large share of a core. Then a custom rclcpp message memory strategy with a pool is the fix, not a project copy.
5. Cost to reverse. Low. The frame factory is private to the adapter, and the public frame accessors do not change.

### D5. Thread and executor model

1. Position. The project process has three threads for acquisition. Consumers use their own threads.
   1. The controller worker. The composition root binds the gateway to it with `bind_to_current_thread()` and then calls `AcquisitionController::run_worker()`. It makes all gateway calls and runs a 100 ms supervision tick.
   2. The control executor. A `SingleThreadedExecutor` spins the gateway node and so delivers service replies.
   3. The data executor. A second `SingleThreadedExecutor` spins a second node that holds only the image subscription and its `message_lost` event.
2. Evidence.
   - `[F]` If the bound gateway thread also spins the node, each call times out (facts 1.1.17).
   - `[F]` The probe already uses one worker thread and one executor thread (facts 1.1.18).
   - `[F]` The take path deserializes each 1.34 MB frame into heap memory in the executor thread (facts 1.3.13). At 69.7 Hz that is 93.2 MB/s of work on that thread.
   - `[F]` `bind_to_current_thread()` is on the concrete `VimbaXCameraGateway`, not on the `CameraGateway` port (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:63-64`). The composition root must therefore start the worker. The controller cannot bind through the port.
   - `[A]` Two nodes in one process share one DDS participant in Jazzy, so the second node costs one executor thread and a few discovery entries.
3. Rejected options.
   - (a) One node and one executor thread for replies and images. A burst of frame takes delays service replies, so gateway deadlines then depend on frame load.
   - (b) One node with a separate callback group on a `MultiThreadedExecutor`. It gives the same isolation as (c) but adds a thread pool and group rules that each new callback must follow.
   - The v1 model, in which the controller runs on the caller thread. A silence check and a reconnect check need a thread that runs when no caller calls (D22).
4. What would change my mind. A probe measurement that shows one executor thread keeps all service replies under 5 ms at 69.7 Hz Mono8. Then (a) is simpler and enough.
5. Cost to reverse. Low. Only the composition root changes. Both adapters already take a caller-owned `rclcpp::Node&`.

### D6. Error vocabulary

1. Position. Add `ErrorDomain::kAcquisition = 2` and `Error::from_acquisition(code, text)` to `types/error.hpp`. Put the codes in a new installed header, `types/acquisition_error.hpp`. The codes are contractual. Driver errors still pass unchanged, and gateway diagnostics stay private.

   | Code | Name | The controller or the frame source returns it when |
   |---|---|---|
   | 1 | `kFeedClosed` | `take` or `try_take` runs after `close()` or after the `FrameSource` is gone |
   | 2 | `kDeadlinePassed` | get image has no frame when its caller deadline passes |
   | 3 | `kStreamWedged` | `stream_start` or `stream_stop` returned -15, or an earlier start or stop failed and left the driver in a transition state |
   | 4 | `kFormatNotStreamable` | the current `PixelFormat` is not Mono8 or Mono12, so the controller does not call `stream_start` |
   | 5 | `kProfileMismatch` | a profile readback differs from the value that the controller wrote |
   | 6 | `kSubscriptionNotMatched` | the image subscription has no matched publisher 1000 ms after the request |
   | 7 | `kWrongThread` | a second thread calls `take` or `try_take` on one `FrameSubscription` |
   | 8 | `kTriggerNoFrame` | reserved for phase 2: the trigger command succeeded and no frame came before the deadline |

2. Evidence.
   - `[F]` `ErrorDomain` has two values, `kDriver` and `kGateway` (`src/venimapping_camera/include/venimapping_camera/types/error.hpp:17-20`).
   - `[F]` Gateway diagnostics 1 to 5 are for logs and tests only, and callers classify by domain (`src/venimapping_camera/src/gateway_support/gateway_errors.hpp:15-22`).
   - `[F]` -15 from a stream service comes only from a state that an earlier failure left at `kStarting` or `kStopping`, and no service resets it (facts X1, 1.4.3, 1.4.4). The caller action is "restart the driver", which no driver code tells the caller.
   - `[F]` Four formats that the camera offers wedge the driver at start (c1 §3.1 item 2).
   - `[F]` A trigger command can return error code 0 and give no frame (c2 §3.2 item 3).
3. Rejected options.
   - (a) No new domain, as v1 proposed. A caller cannot tell "restart the driver" from "try again" if both are non-contractual gateway codes.
   - (c) Driver codes and empty results only. A wedge, a format refusal, and a deadline need three different caller actions. An empty result cannot carry that.
4. What would change my mind. Logan decides that no caller acts on the failure kind and that all failures go to a log. Then (a) with private codes is enough.
5. Cost to reverse. Medium. Callers that switch on the codes must change, but the `Error` type and the two existing domains stay.

## 3. Data plane

Codex owns the data-plane section. These positions give the control-plane view of each choice.

### D7. Consumer API

1. Position. Pull. `FrameSubscription::take(timeout)` returns `Expected<std::optional<ImageFrame>>`. An empty optional means no frame in the timeout. `try_take()` does not wait. `close()` runs from any thread, is idempotent, and wakes a waiting `take`.
2. Evidence.
   - `[F]` A consumer callback on an executor thread that calls the gateway makes each gateway call time out (facts 1.1.17).
   - `[F]` `connection_status()` already returns a successful negative (facts A48). An empty `take` follows the same rule.
3. Rejected options.
   - (b) A callback on a project thread. It needs the same queue as pull plus a thread per consumer, and it hides the queue depth.
   - (c) A callback on the executor thread. Consumer work then delays the image take and can call the gateway on the wrong thread.
   - (d) The ROS topic is the contract. D2 has the reason.
4. What would change my mind. A consumer that needs a callback for an event loop it does not own. A thin wrapper over `take` covers that without a port change.
5. Cost to reverse. Low. A callback wrapper over `take` is about 30 lines.

### D8. Transport mechanism

1. Position. A plain `rclcpp::Subscription<sensor_msgs::msg::Image>` on `<namespace>/image_raw`, with the message-info callback form. Bring-up also limits the driver to the raw plugin with `image_raw.enable_pub_plugins: ["image_transport/raw"]` in `camera.yaml`.
2. Evidence.
   - `[F]` `image_transport` advertises one subtopic for each installed plugin, unless `<base>.enable_pub_plugins` limits it (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:114-153`). Bringup does not set it (facts 1.3.4).
   - `[F]` The driver opens the camera in exclusive mode (`driver:vimbax_camera/src/vimbax_camera.cpp:164-185`), so a VmbC adapter cannot run next to the driver.
   - `[F]` The message-info callback form exists (`ros:ros2/rclcpp/rclcpp/include/rclcpp/any_subscription_callback.hpp:110-113`). D3 needs it for the host stamps.
3. Rejected options.
   - (b) `image_transport` subscriber. It adds a plugin loader and a dependency to read raw frames, which a plain subscription already reads. Its raw transport is a plain subscription.
   - (c) A direct VmbC adapter. It replaces the driver data path, needs the camera in exclusive mode, and moves bring-up, reconnect, and the frame thread into the project. R13 and R12 give no reason for that cost.
4. What would change my mind. A consumer on another host that needs a compressed topic (R12), or a measurement that the DDS hop costs more than the frame budget at the required rate.
5. Cost to reverse. Low for (b), because only the adapter changes. High for (c).

### D9. Subscriber QoS and history depth

1. Position. BEST_EFFORT, KEEP_LAST 2, VOLATILE. `FrameSource` sets it once at construction through `FrameSourceOptions`. The default is not per feed, because all feeds share one subscription (D13).
2. Evidence.
   - `[F]` A RELIABLE publisher matches a BEST_EFFORT subscriber (facts 1.3.3).
   - `[A]` A RELIABLE reader can make the driver block in `publish`. The SDK buffer then returns late, and frames drop where only the driver log shows them (facts 1.3.14, T9). A BEST_EFFORT reader takes no part in writer flow control.
   - `[A]` R9 assumes that newer frames have priority and that the feed can drop frames.
   - `[A]` D12 counts losses from device-stamp gaps, so a BEST_EFFORT loss stays visible to the project. My camera request tests the count.
   - `[F]` One Mono8 frame is 1337472 bytes, so depth 2 holds 2.67 MB in the reader (c1 §3.2).
   - `[A]` Depth 2 gives the data executor one frame period, 14.3 ms, of delay before the reader history replaces a sample.
3. Rejected options.
   - (a) RELIABLE with a small depth, as v1 proposed. Its overflow goes to the driver and the SDK, which is the place the project sees least.
   - (c) Configurable per feed with one default. Feeds share one subscription, so a per-feed value has no meaning.
4. What would change my mind. My camera request: if a BEST_EFFORT reader at Mono8 69.7 Hz with the current host buffers loses frames that a RELIABLE reader gets, with no "frames missing" log in the driver. Then RELIABLE is the default until T11 tuning is done.
5. Cost to reverse. Low. One option value changes in the adapter.

### D10. Queue bound, overflow rule, and `buffer_count`

1. Position. Each `FrameSubscription` owns one bounded queue. The capacity is set at `subscribe`, default 2, allowed range 1 to 8. At capacity, the queue drops the oldest frame and counts the drop. Bring-up writes `buffer_count: 7` in `camera.yaml` and never changes it at run time.
2. Evidence.
   - `[F]` With `buffer_count` 7 and one or two CLI readers, about 3100 Mono8 frames and 630 Mono12 frames streamed with no "frames missing" log (c1 §3.7 item 2).
   - `[F]` A `buffer_count` change during a disconnect calls `is_streaming()` on a null camera (facts 1.10.1). A file value avoids that path.
   - `[F]` At 69.7 Hz, capacity 2 holds at most 28.7 ms of frames. R7 allows two frame periods for a warm get image.
   - Memory bound for one Mono8 feed. Sizes are `[F]` from c1 §3.2. The writer history row is `[A]`.

     | Holder | Frames | Bytes |
     |---|---|---|
     | Driver SDK buffers | 7 | 9.36 MB |
     | DDS writer history in the driver, at most | 10 | 13.4 MB |
     | DDS reader history in the project | 2 | 2.67 MB |
     | One project queue | 2 | 2.67 MB |
     | Frames that the consumer holds | n | n x 1.34 MB |
3. Rejected options.
   - Capacity 1 as the default. It is the right value for get image (D28), but a feed consumer then drops a frame on each scheduling delay over one period.
   - Capacity 4, as v1 proposed. It doubles the staleness to 57 ms with no stated need.
   - Drop newest. R9 gives newer frames priority.
   - A measured `buffer_count` now. c1 showed no loss at 7. A change waits for a loss measurement under load.
4. What would change my mind. A probe run that shows "frames missing" at 7 buffers with the D9 QoS, or a consumer that needs bursts longer than 28.7 ms.
5. Cost to reverse. Low. The default is one constant, and `buffer_count` is one line in `camera.yaml`.

### D11. Frame identity and sequence scope

1. Position. `receive_seq` is a 64-bit count per `FrameSource`. It starts at 0, increments in the subscription callback, and never resets. `stream_epoch` is a 32-bit count that starts a new value at two events:
   1. The controller calls `FrameSource::begin_epoch(StreamInfo)` just before each `stream_start` that it makes.
   2. The adapter starts a new epoch itself if the device stamp does not increase, or increases by more than the silence threshold of D22, against the previous frame.
2. Evidence.
   - `[F]` The message carries no counter, and the CycloneDDS RMW leaves both sequence fields unset (facts 1.6.7, 1.6.9).
   - `[F]` The driver restarts the stream after a reopen without a project call (facts 1.9.7). The controller can see it only later, so rule 2 must not wait for the controller.
   - `[F]` The device stamp advances at 1 ns per ns within 13 ppm of the host clock (c1 §3.4 item 4). The clock did not reset across two checks about 10 min apart (c2 §3.5 item 3).
   - `[A]` A camera power cycle resets the camera clock, so its stamp goes back. A link drop without power loss leaves a gap larger than the silence threshold.
   - `[F]` One shared subscription (D13) gives the same `receive_seq` to the same frame in each queue. Get image and a feed then agree on identity.
3. Rejected options.
   - (a) Receive sequence per subscription only. It cannot mark R14 outages or restarts.
   - (c) Device stamp as identity. It is unique within a camera clock epoch only, and it resets at an unknown event (c1 §3.4 item 8).
   - (d) SDK `frameID` from a driver patch. R13 assumes no patch. The stamp gap of D12 gives the loss count that `frameID` would give.
4. What would change my mind. A camera check that shows the device stamp does not go back after a power cycle and a link drop gap is shorter than the threshold. Then rule 2 needs the controller outage signal instead.
5. Cost to reverse. Low. The epoch rules are two branches in the adapter callback.

### D12. Loss reporting

1. Position. The feed reports four counters, and the contract lists the loss that no counter shows.
   - Per `FrameSubscription`: `queue_evictions`.
   - Per `FrameSource`: `frames_received`, `transport_lost` from the `message_lost` event, and `stamp_gap_frames`.
   - `stamp_gap_frames` applies in free run only. If `d` is the device stamp delta and `p` is the nominal period from `StreamInfo`, and `d > 1.5 p`, the adapter adds `round(d / p) - 1`.
   - The contract states that `stamp_gap_frames` includes SDK, driver, DDS, and reader history loss, and that it cannot separate them.
   - The contract states that loss at an epoch start and in trigger mode is not counted.
2. Evidence.
   - `[F]` A reader KEEP_LAST overwrite sets no status (facts X8). An incomplete SDK frame and an SDK buffer shortage show only in the driver log (facts 1.7).
   - `[F]` `AcquisitionFrameRate` reads 69.71556 and the delivered rate was 69.721 Hz, so the read value is the free-run period source (c1 §3.3 item 1).
   - `[F]` Receipt intervals at Mono8 were 13 to 16 ms, all under 1.5 periods (c1 §3.3 item 2).
   - `[Q]` The jitter of consecutive device stamps is not measured. My camera request asks for it.
3. Rejected options.
   - Queue evictions and `message_lost` only, as v1 proposed. Both miss the reader overwrite and all driver-side loss (facts A41).
   - A `frameID` gap counter. It needs a driver patch (D21).
   - No list of invisible losses. A consumer would then read a zero counter as zero loss.
4. What would change my mind. A measurement that shows consecutive device stamps vary by more than 0.5 period with no loss. Then the threshold is wrong, and only a `frameID` patch gives a reliable count.
5. Cost to reverse. Low. Counters are additive fields in a stats struct.

### D13. Several consumers

1. Position. (b) One `FrameSource` has one ROS subscription. Each `FrameSubscription` has its own queue. The subscription callback pushes the same frame to each open queue.
2. Evidence.
   - `[F]` Each ROS subscription gets its own deserialized copy (facts 1.3.13). Two subscriptions double the 93.2 MB/s copy work.
   - `[F]` Get image during a feed needs a second queue on the same stream (D28).
3. Rejected options.
   - (a) One feed only. Get image during a feed then needs its own subscription or a stop of the feed, and R8 forbids the stop.
   - (c) One subscription per feed. It doubles the deserialization, and it gives two `receive_seq` values to one frame.
4. What would change my mind. Two consumers that need different QoS. Then each QoS needs its own subscription.
5. Cost to reverse. Low. The fan-out is inside the adapter.

### D14. Pixel interpretation

1. Position. (b) Pass pixels and `encoding` unchanged. Add `significant_bits` to the frame from the epoch `StreamInfo`: 8 for Mono8 and 12 for Mono12. The controller fills `StreamInfo` from the `PixelFormat` that it reads before start.
2. Evidence.
   - `[F]` Only Mono8 and Mono12 pass the gate on this camera. Mono12 publishes as `mono16` with `step` 2592 and a 4-bit left shift (c1 §3.1, §4 row T1).
   - `[F]` The message does not record the shift (facts 1.3.7).
3. Rejected options.
   - (a) Pass unchanged with no bit depth. A `mono16` consumer cannot tell Mono12 from a real 16-bit format on another camera.
   - (c) Undo the shift in the adapter. It is a full pass over 2.67 MB per frame at 45 Hz. It also makes `encoding` lie about the value range.
4. What would change my mind. R3 stays Mono8 for all phases. Then the field is always 8 and can wait.
5. Cost to reverse. Low. One field.

### D15. Calibration pairing

1. Position. (a) No `CameraInfo` in the first phase. The adapter does not subscribe to `camera_info`. Bring-up leaves `camera_info_url` empty.
2. Evidence.
   - `[F]` No calibration file exists for this camera. The driver logs that the file is not found (c1 §3.5 item 5).
   - `[F]` Without a match, the driver publishes `CameraInfo` with only width and height set (facts 1.8.2).
   - `[F]` `image_raw` and `camera_info` share one header (facts 1.3.1). A later pairing by `device_stamp_ns` is exact.
3. Rejected options.
   - (b) Pair by header now. It pairs each frame with an all-zero `K` today.
   - (c) Load calibration in the project. No calibration exists to load.
4. What would change my mind. Logan states that the first consumer needs intrinsics (R11), and a calibration file exists for 1296 x 1032.
5. Cost to reverse. Low. Pairing adds one subscription and one optional field.

## 4. Stream control and configuration

### D16. Stream ownership

1. Position. (a) One `AcquisitionController` owns `stream_start`, `stream_stop`, and all feature writes. Only its worker thread makes these calls. Each open feed and each running get image holds a lease. The worker calls `stream_start` when the count goes from 0 to 1 and `stream_stop` when it goes from 1 to 0.

   ```cpp
   // Sketch only. Public calls are safe from any thread. They post a job to the worker.
   class AcquisitionController {
    public:
     static Expected<std::unique_ptr<AcquisitionController>> create(
         CameraGateway& gateway, FrameSource& frames,
         AcquisitionProfile profile, ControllerOptions options);
     void run_worker();   // the composition root calls this on the bound gateway thread
     void shutdown();     // any thread
     Expected<FeedLease> feed_open(const FeedOptions& options);
     Expected<ImageFrame> get_image(const GetImageOptions& options);
     ControllerState state() const;  // kIdle, kStreaming, kOutage, kStalled, kWedged
   };
   ```

2. Evidence.
   - `[F]` Start and stop serialize in the driver, and a start while active succeeds with no effect (facts 1.4.8, 1.4 table). A count in the project is the only way to know when the last user leaves.
   - `[F]` `TriggerMode` is read only while streaming, and the trigger setup needs a selector write just before each mode write (c1 §3.6, c2 §3.3). One owner must also own `TriggerSelector` (c2 §4 row D16).
   - `[F]` `camera_status()` moves `TriggerSelector` (facts 1.5.7). The controller calls it only while trigger mode is off on all selectors.
3. Rejected options.
   - (b) Each feed starts and stops the stream. The first feed to close stops the stream under a second feed.
   - (c) Bringup or an operator starts the stream. Get image when idle then cannot work (D25), and the stream runs at 93.2 MB/s with no user.
4. What would change my mind. Logan states that another tool must also start and stop the stream while the project runs (R15). Then the controller must read `status.streaming` before each decision, and the lease count is not enough.
5. Cost to reverse. Medium. Feed open and get image both depend on the lease rule.

### D17. Feed start, readiness, and close

1. Position. `feed_open` takes a lease. Before the first `stream_start` of an epoch, the worker waits for a matched reader. It checks `get_publisher_count() >= 1` on the image subscription every 10 ms, for at most 1000 ms. If no publisher matches, `feed_open` returns `kSubscriptionNotMatched`. Destruction of the `FeedLease` releases the lease. The last release stops the stream.
2. Evidence.
   - `[F]` `get_publisher_count()` reads the DDS matched status of the reader (`ros:ros2/rclcpp/rclcpp/src/rclcpp/subscription_base.cpp:277-281`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3149-3160`).
   - `[F]` The first frame arrives 30 to 43 ms after the driver handles `stream_start`, and 69 to 79 ms before the reply. A reader made after the reply misses 3 to 5 frames (c1 §3.5 items 1 to 3).
   - `[F]` A subscription made before `stream_start` does not prove a match, because the publisher is VOLATILE (facts A66).
   - `[A]` On one host, a matched reader means the writer also knows the reader within the same discovery round. The probe measures this (T12).
3. Rejected options.
   - Open only arms delivery. The consumer must then start the stream through a second call, which breaks D16.
   - Ready means subscription created. A66 shows that it can lose startup frames.
   - Ready means first frame received. It makes a feed open wait one frame and gives no gain over the match check, because the controller starts the stream after the match.
   - Close always stops, or never stops. "Always" stops the stream under another lease. "Never" leaves 93.2 MB/s running with no user.
4. What would change my mind. A probe result that shows a matched reader still misses the first frame. Then ready must mean "first frame received", with a one-frame cost.
5. Cost to reverse. Low. The readiness rule is one wait loop in the worker.

### D18. Configuration ownership and order

1. Position. (c) with a fixed rule set. A project `AcquisitionProfile` is the only source of camera configuration. Its values live in the bringup config next to `camera.yaml`. The controller applies it with gateway writes while the stream is stopped. It writes only values that differ, and it reads back each value. It applies the profile before the first stream start and after each reconnect. While streaming, only `ExposureTime` can change. The phase 1 profile:

   | Feature | Value | Status |
   |---|---|---|
   | `PixelFormat` | `Mono8` | `[F]` on the gate and offered (c1 §3.1) |
   | `Width`, `Height` | 1296, 1032 | `[F]` full sensor (c1 §3.2) |
   | `OffsetX`, `OffsetY` | 0, 0 | `[A]` not read in c1 |
   | `TriggerMode` under `FrameStart` | `Off` | `[F]` baseline (c2 §3.1 item 5) |
   | `AcquisitionFrameRateEnable` | `false` until Logan sets R4 | `[F]` exists and is writable (c1 §3.7) |
   | `ExposureTime` | 4999.455 us until Logan sets it | `[F]` current value (c1 §2.1 step 11) |

   Write order: shape features, then the selector write and `TriggerMode`, then the rate pair, then `ExposureTime`. Then the controller reads back all values. A difference gives `kProfileMismatch`.
2. Evidence.
   - `[F]` `PixelFormat`, `Width`, and `TriggerMode` are read only while streaming. `ExposureTime` and `AcquisitionFrameRateEnable` stay writable (c1 §3.6 item 1).
   - `[F]` A `settings_file` load failure only logs an error. The driver then continues (`driver:vimbax_camera/src/vimbax_camera_node.cpp:390-400`). The project cannot see that failure.
   - `[F]` The gateway does no readback, and a setter that times out can still apply (facts 1.1.10, 1.1.14).
   - `[F]` After a reopen, the driver restarts the stream within one 50 ms graph tick (`driver:vimbax_camera/src/vimbax_camera_node.cpp:561-568`, `:586-593`). A shape write after a reconnect therefore needs a stop first.
   - `[A]` The camera power-on values equal the phase 1 profile for shape features. Then a reconnect needs no stop, and the profile check after a reconnect only reads.
3. Rejected options.
   - (a) `settings_file` on each open. It applies before the driver restart, which is good. But a failed load is invisible, and a camera-generated XML dump is hard to review in git.
   - (b) A camera `UserSet`. It survives a power cycle, but the values live in the camera and not in the repository.
   - (d) A mix with rate writable at run time. c1 did not show that `AcquisitionFrameRate` is writable while streaming (c1 §3.6 item 3). My camera request asks.
4. What would change my mind. Two facts would move me to (a) or (b). First, the camera loses the profile at power cycle (R16). Second, the profile differs from the power-on values for a shape feature. Then the driver restart after a reconnect runs with the wrong shape, and only `settings_file` or a `UserSet` applies earlier.
5. Cost to reverse. Medium. The apply and readback code stays, but the source of the values and the reconnect sequence change.

### D19. Start and stop failure recovery

1. Position. (a) and (d), with (c) as a requested patch.
   1. Before each `stream_start` that it makes, the controller reads `PixelFormat`.
   2. If the value is not Mono8 or Mono12, the controller returns `kFormatNotStreamable` and does not call `stream_start`.
   3. If `stream_start` or `stream_stop` fails, the controller sets its state to `kWedged` when the driver code is -15 or when a later `camera_status()` reports `streaming` true with no active stream.
   4. In `kWedged`, each lease request returns `kStreamWedged` with no service call. The error text says to restart the driver process.
   5. A detected reconnect clears `kWedged`, because the reopen makes a new driver state machine.
2. Evidence.
   - `[F]` Each error return in `start_streaming` leaves `kStarting`. Each error return in `stop_streaming` leaves `kStopping`. No service resets the state (facts 1.4.1 to 1.4.4).
   - `[F]` The camera offers Mono10, Mono10p, Mono12p, and Mono12Packed, which fail the gate (c1 §3.1).
   - `[F]` A reconnect with a wedged state starts a stream on a new camera object (facts 1.10.5).
   - `[F]` A `PayloadSize` or `CaptureStart` failure also wedges the state (facts 1.4.1). The allow-list cannot prevent those.
3. Rejected options.
   - (b) Detect, then restart the driver process from the project. The project does not own the driver process. Bringup starts it (facts 1.1.2).
   - (c) alone. It needs a fork patch, and R13 assumes the design works without one.
   - (d) alone. It lets a known format mistake wedge the driver.
4. What would change my mind. Logan accepts fork patches (R13). Then patch (c) resets the state to `kStopped` on each failed transition, and `kStreamWedged` becomes rare.
5. Cost to reverse. Low. The check is one read before start, and the wedge state is one controller state.

### D20. Timestamp source

1. Position. (a), extended. Bring-up keeps `use_ros_time: false` and writes it in `camera.yaml`. The adapter fills `device_stamp_ns` from `header.stamp`, `publish_stamp_ns` from the DDS source timestamp, and `receipt_stamp_ns` from the rmw receipt time.
2. Evidence.
   - `[F]` The CycloneDDS RMW gives `source_timestamp` and `received_timestamp` in the message info (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3280-3283`).
   - `[F]` Both host values are Unix time and differ by about 2 ms at Mono8 (c1 §3.4 item 9). Under R12 both are on the consumer host clock.
   - `[F]` With `use_ros_time: true`, the stamp is `node->now()` after the transform and before publish (facts 1.6.3). `source_timestamp` is taken in that same `publish`, so it gives nearly the same host time.
   - `[A]` The device stamp is the only stamp taken before the payload transfer (c1 §3.4 item 6). D11 and D12 need it.
   - `[F]` A change of `use_ros_time` during a stream changes the time basis between two frames (facts 1.6.4). A fixed file value avoids that.
3. Rejected options.
   - (b) `use_ros_time: true`, as v1 proposed. It removes the device stamp, so D11 and D12 lose their input. The host stamp it adds is already in the message info.
   - (c) A device-to-host offset map. The offset changes by 10.4 ms between Mono8 and Mono12 and drifts about 4 ppm (c1 §3.4 item 5, c2 §3.5 item 2). R10 does not need exposure time.
   - (d) A driver patch for two stamps. The message info gives the host stamp without a patch.
4. What would change my mind. A deployment with the driver and the consumer on two hosts (R12). Then `source_timestamp` is on the driver host clock, and a time sync or option (b) is needed.
5. Cost to reverse. Low. Each stamp is one field fill in the adapter.

### D21. Driver changes

1. Position. (a) for the design: no part of the design needs a patch. I also recommend that Logan accept three small patches to the fork, in this order:
   1. Reset the stream state to `kStopped` after each failed start or stop (`driver:vimbax_camera/src/vimbax_camera.cpp:416-510`, `:527-575`). It removes the wedge.
   2. Add a null check for `camera_` in the `buffer_count` callback (`driver:vimbax_camera/src/vimbax_camera_node.cpp:311-312`). It removes a crash.
   3. Save `TriggerSelector` before the `status` loop and write it back after (`driver:vimbax_camera/src/vimbax_camera.cpp:1452-1473`). It removes the selector race for all clients. Phase 2 trigger work needs it.
2. Evidence.
   - `[F]` The project pins a fork tag, so a patch has a home (`README.md:13-15`).
   - `[F]` The `:604` guard has no effect with `autostream: 0` (facts 1.4.12). A patch there changes nothing for the project.
   - `[F]` D12 counts loss from device stamps, and D20 gets a host stamp from the message info. `frameID` in the message and a second stamp are therefore not needed.
   - `[A]` The double shared lock (facts 1.10.3) does not hang on glibc, because the default `pthread_rwlock_t` prefers readers. It stays undefined behavior in C++, so it is the fourth candidate.
3. Rejected options.
   - (b) as a design dependency. R13 is unknown, so the design must not need a patch.
   - (c) Replace the data path with VmbC. D8 has the reason.
4. What would change my mind. Logan rejects all fork patches. Then the wedge and the crash stay as documented bring-up rules, and the trigger path stays out of all phases unless no tool calls `status`.
5. Cost to reverse. Low. Each patch is under 20 lines and needs no interface change.

### D22. Disconnect, silence, and outage

1. Position. The controller worker checks silence on each 100 ms tick while a lease exists and the stream runs in free run.
   1. The silence threshold is `max(500 ms, 5 x nominal period)`. At Mono8 69.7 Hz it is 500 ms.
   2. If no frame arrives within the threshold, the worker calls `connection_status()`.
   3. If the result is false or the call returns -3, the state becomes `kOutage`. The feed stays open, and `take` returns empty.
   4. In `kOutage`, the worker calls `connection_status()` every 250 ms.
   5. After it reads true, the worker reads the profile values. If all match, it keeps the stream that the driver restarted.
   6. If a value differs, the worker stops the stream, applies the profile, and starts it with a new epoch.
   7. If no frame arrives within 1000 ms after the reconnect, the worker calls `stream_start` once.
   8. If `connection_status()` is true and silence continues, the state becomes `kStalled`. The worker makes one stop and start cycle, then reports `kStalled` and does nothing more.
2. Evidence.
   - `[F]` No ROS event exists for connection. Each camera service returns -3 while the camera is unavailable (facts 1.9.2, 1.9.5).
   - `[F]` The driver restarts a stream that was active or starting at the disconnect, also with `autostream: 0`, and ignores the result (facts 1.9.7).
   - `[F]` Receipt intervals at Mono8 were at most 16 ms (c1 §3.3 item 2). 500 ms is 35 periods.
   - `[A]` A false silence alarm costs one `connection_status()` call. A short threshold is therefore cheap.
3. Rejected options.
   - A fixed time only. At a low frame rate set by R4, a fixed 500 ms fires on each frame period over 500 ms.
   - Let the driver restart with no project check. A power cycle that loses the profile (R16) then streams the wrong configuration with no report.
   - Close the feed with an error on an outage. R14 states that a disconnect does not close the feed.
4. What would change my mind. Logan states that an outage must close the feed (R14). Then step 3 returns an error from `take`, and steps 4 to 7 move to the next `feed_open`.
5. Cost to reverse. Low. The rules are inside the worker tick, and the feed API does not change.

## 5. Get image

### D23. Frame source for get image

1. Position. (a) when a lease is active: take the next frame from the running stream. (b) when idle: take a lease, start the stream, take the first frame, and release the lease. (c) the software trigger stays out of phase 1.
2. Evidence.
   - `[F]` `FrameStart`, `Software`, and `TriggerSoftware` exist, and one command gives one frame (c2 §3.1, §3.2).
   - `[F]` `TriggerMode` is read only while streaming (c1 §3.6). A trigger get image during a feed must stop the feed, and R8 forbids that.
   - `[F]` In process, the trigger path and the start-and-stop path cost about the same (c2 §4 row D25).
   - `[F]` Each trigger command needs a selector write, and a `status` call between them sends the command to the wrong selector (c2 §3.3).
   - `[A]` R6 needs only "received after the request".
3. Rejected options.
   - (b) only. A get image during a feed would stop and start the shared stream.
   - (c) now. It adds the selector race and the stop of the feed for a freshness that R6 does not need.
   - (d) Choose per call, as v1 proposed. Two code paths for one requirement, and the trigger path needs D21 patch 3 to be safe.
4. What would change my mind. Logan states that get image needs a frame exposed after the request (R6). Then (c) enters phase 2, with D27 rules, and it runs only when no feed is open.
5. Cost to reverse. Medium. A trigger path adds the trigger setup, the restore, and an error code, but no port change.

### D24. Freshness rule

1. Position. (a) At the request, the worker reads the last `receive_seq` that the source gave. The answer is the first frame with a greater `receive_seq`.
2. Evidence.
   - `[F]` A frame received after the request can have been exposed before it (facts A68). R6 accepts this.
   - `[F]` `receive_seq` increments in the subscription callback in receipt order (D11). The rule uses no clock.
3. Rejected options.
   - (b) First frame with a host stamp after the request. It needs a clock compare, and it differs from (a) by about 2 ms (c1 §3.4 item 9).
   - (c) First frame exposed after the request. It needs a trigger or an offset map (D20), and R6 does not need it.
4. What would change my mind. R6 changes to "exposed after the request".
5. Cost to reverse. Low. The rule is one compare in the controller.

### D25. Idle behavior and subscription lifetime

1. Position. (b) The `FrameSource` keeps its subscription for its whole life, so the reader stays matched while idle. Each cold get image starts the stream and stops it after the frame. `ControllerOptions::idle_linger` keeps the stream for a set time after the last release. The default is 0.
2. Evidence.
   - `[F]` A matched reader costs no frame traffic while the stream is stopped, because the driver publishes nothing then (facts 1.4.12).
   - `[F]` The first frame comes about 30 ms after the driver handles `stream_start`. The reply comes about 110 ms after it. The stop takes at least 100 ms (c1 §3.5, facts 1.4.6).
   - `[A]` In process, a cold get image returns in about 110 to 150 ms, because the worker gives the frame to the caller before it calls `stream_stop`.
3. Rejected options.
   - (a) A subscription per call. It adds the match time, T12, to each call.
   - (c) Keep the stream running. It moves 93.2 MB/s through DDS and deserializes each frame for a call that R8 makes less than once per second.
   - (d) Fail if no stream runs. R7 allows a 2 s cold call.
4. What would change my mind. Get image more than about 3 times per second (R8). Then `idle_linger` of 1000 ms makes most calls warm.
5. Cost to reverse. Low. The linger value is one option.

### D26. Deadline and timeout result

1. Position. One caller deadline, `GetImageOptions::deadline`, default 2000 ms from the call. It covers the lease, the format check, the match wait, `stream_start`, and the first frame. The `stream_stop` after delivery is outside it. A passed deadline returns `kDeadlinePassed`. The gateway timeout is 2000 ms per call.
2. Evidence.
   - `[F]` The gateway has one timeout for all calls (facts 1.1.11). A command call can take up to the 1 s driver default plus 100 ms (facts 1.5.3).
   - `[F]` The probe already uses 2000 ms (facts 1.1.19).
   - `[F]` A worker that waits in a gateway call cannot stop that call. The caller waits on a future with the deadline, and the worker finishes the call after the caller has left.
   - `[A]` R7 allows 2 s cold.
3. Rejected options.
   - One deadline per step. The caller cares about the total, and per-step values need tuning for each step.
   - An empty result on timeout. Get image promises one frame, so a missing frame is a failure. A feed `take` is different, because silence is normal there.
   - The stop inside the deadline. The caller already has the frame, and a stop failure is a controller state, not a get image result.
4. What would change my mind. Logan sets R7 below 200 ms for a cold call. Then cold get image cannot meet it, and D25 must keep the stream warm.
5. Cost to reverse. Low. The deadline is one option and one error code.

### D27. Trigger association and restore

1. Position. Phase 2 only. When used, the rules are these.
   1. The setup runs while stopped. Before each `TriggerMode` or `TriggerSource` write, the worker writes `TriggerSelector` to `FrameStart`.
   2. The controller does not call `camera_status()` while trigger mode is on.
   3. Before each `TriggerSoftware`, the worker writes `TriggerSelector` to `FrameStart` and reads the last `receive_seq`.
   4. The answer is the first frame with a greater `receive_seq`. The frame deadline is 500 ms from the command send.
   5. No frame by the deadline gives `kTriggerNoFrame`, also when the command returned 0.
   6. The restore writes `FrameStart` and `TriggerMode` `Off`, then reads `TriggerMode` back under `FrameStart`. It also runs on each failure path.
2. Evidence.
   - `[F]` `TriggerSoftware` acts on the current selector. Two of nine commands gave no frame with error code 0 (c2 §3.2 item 3, §3.3).
   - `[F]` Each frame arrived 277 to 290 ms before the `command_run` CLI exited (c2 §3.2 item 6).
   - `[A]` In process, the frame arrives about 80 to 100 ms before the `command_run` reply (c2 §3.4 item 4).
   - `[F]` Only `FrameStart` changes, and the baseline is `Off` and `Software` under all seven selectors (c2 §3.1 item 5). A misdirected restore write is then harmless.
3. Rejected options.
   - Association by device stamp. No reply field carries a stamp (facts 1.5.1).
   - Association by quiet interval. It adds wait time and still fails if a free-run frame is in flight.
   - Restore through `status` readback. `status` moves the selector again (facts 1.5.7).
4. What would change my mind. D21 patch 3 lands. Then rule 2 is no longer needed, and a `status` readback becomes safe.
5. Cost to reverse. Low. No phase 1 code depends on it.

### D28. Get image during an open feed

1. Position. (a) Get image takes a lease, which keeps the stream running, and opens a one-frame `FrameSubscription` on the shared source. It returns the first frame that passes D24 and then closes that subscription.
2. Evidence.
   - `[A]` R8 states that get image must not stop a feed.
   - `[F]` Two periods at Mono8 are 28.7 ms (c1 §4 row R7). A warm get image waits at most one period plus the take delay.
3. Rejected options.
   - (b) Stop the feed, take a frame, and restore the feed. It breaks R8 and costs at least 200 ms of feed silence.
   - (c) Fail with an error. It makes get image depend on feed state that the caller does not own.
4. What would change my mind. A trigger get image (D23 c) becomes required. Then (b) is the only choice during a feed, and R8 must change.
5. Cost to reverse. Low. Only the controller job changes.

### D29. Get image caller interface

1. Position. (a) C++ only in phase 1. A ROS service node can wrap `AcquisitionController::get_image` later without a port change.
2. Evidence.
   - `[F]` No project node consumes frames today (facts 1.1.1). R1 assumes one in-process C++ consumer.
3. Rejected options.
   - (b) C++ plus a ROS service now. No caller exists, and the service must still choose an image message type and a size limit.
   - (c) ROS service only. The in-process consumer then pays a serialize and deserialize pass for 1.34 MB per call.
4. What would change my mind. A consumer in another process or on another host (R1, R12).
5. Cost to reverse. Low. A wrapper node adds a package target and does not change the controller.

## 6. Comments on the working assumptions

### 6.1 Inline assumptions in facts sections 1.3 to 1.10

| Item | Accept | Reason |
|---|---|---|
| 1.3.14, a RELIABLE writer can block on a slow reader | Yes, as a risk | D9 avoids it with a BEST_EFFORT reader. A RELIABLE tool such as `ros2 topic echo` can still bring it back, so bring-up documents it. |
| 1.9.10, a power cycle resets service writes | Yes | It is the safe side. D18 applies the profile after each reconnect, so the design works either way. A PoE power-cycle test can close it. |
| 1.10.2, a `buffer_count` change during a disconnect crashes | Yes | The code dereferences a null `camera_` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:311-312`, `:554`). D10 sets the value in the file only. |
| 1.10.4, the double shared lock can hang | Partly | On glibc the default `pthread_rwlock_t` prefers readers, so a waiting writer does not block the second shared lock `[A]`. It is still undefined behavior, so it stays fourth in D21. |

### 6.2 Requirements from Logan

| Id | Accept | Comment |
|---|---|---|
| R1 | Yes | D2, D5, and D29 depend on it. If any consumer is another node, D2 and D29 change first. |
| R2 | Yes | c1 shows that the current settings are full sensor, 1296 x 1032 (c1 §3.2). |
| R3 | Yes | Only Mono8 and Mono12 can stream on this camera (c1 §3.1). Mono8 halves the data rate. |
| R4 | No, as written | The camera free-runs at 69.7 Hz by default (c1 §3.3). I propose this working assumption: the design must carry 69.7 Hz Mono8, 93.2 MB/s. A lower rate is a profile value after Logan sets R4. The camera request checks whether the rate write works. |
| R5 | Yes, with numbers | D10 gives the bound for one feed. The project holds `(queue capacity + held frames) x 1.34 MB`. |
| R6 | Yes | D24 implements it with no clock. |
| R7 | Yes | Warm is at most 28.7 ms at Mono8 (c1 §4 row R7). Cold is about 110 to 150 ms in process `[A]`, far inside 2 s. |
| R8 | Yes | D25 and D28 depend on it. Above about 3 calls per second, `idle_linger` must change. |
| R9 | Yes | D9 and D10 implement drop oldest, and D12 counts each drop that the project can see. |
| R10 | Yes | D20 meets it with `publish_stamp_ns` and `receipt_stamp_ns`, with no driver change. |
| R11 | Yes | No calibration file exists (c1 §3.5 item 5). |
| R12 | Yes | D20 depends on it most. On two hosts, `publish_stamp_ns` is on the driver host clock. |
| R13 | Yes | D21 keeps the design free of patches and lists three patches for Logan. |
| R14 | Yes | D11 and D22 implement it. The adapter starts the epoch from the stamps, so it does not race the controller. |
| R15 | Yes, but extend it | c2 shows a `status` poll every 3 s broke the trigger setup in 3 of 13 windows (c2 §3.3 item 6). The rule must be: no other client calls `status` while trigger mode is on, and no other client calls stream services or feature writes. |
| R16 | Yes | D18 depends on it. A PoE power-cycle test answers it. |

### 6.3 Technical unknowns

| Id | Accept | Comment |
|---|---|---|
| T1 | Closed by c1 | Mono8 and Mono12 pass. Four offered formats wedge the driver (c1 §3.1). D19 uses the result. |
| T2 | Closed by c1 | 1337472 bytes at Mono8 and 2674944 bytes at Mono12 (c1 §3.2). D10 uses the numbers. |
| T3 | Closed by c1 | 69.7 Hz at Mono8 and 45.1 Hz at Mono12 (c1 §3.3). The 30 Hz assumption of R4 does not hold by default. |
| T4 | Closed by c1, with one open part | The stamp is camera-clock nanoseconds and is not comparable with the host clock (c1 §3.4). The origin and the exposure event stay open `[Q]`. D20 does not need them. |
| T5 | Closed by c1 | 30 to 43 ms to the first frame and about 110 ms to the reply, after the driver handles the call (c1 §3.5). The assumption "more than 100 ms" was wrong for the frame. |
| T6 | Closed by c2 | One command gives one frame under `FrameStart`, with the selector condition (c2 §3.2, §3.3). |
| T7 | Partly closed by c1 | Shape and `TriggerMode` are locked while streaming. `ExposureTime` is writable. `AcquisitionFrameRate` writability with the enable true is open. My camera request asks. |
| T8 | Closed by c1 | `AcquisitionFrameRateEnable` exists and is false (c1 §3.7). |
| T9 | Yes, as a risk | D9 makes the design avoid it. My camera request compares the two reliabilities at the current host buffers. |
| T10 | Yes | D8 adds the plugin allow-list to `camera.yaml`, so the topic set no longer depends on the host. |
| T11 | Yes | Bring-up must state the host check and the 8 MiB values (facts A64). D9 lowers the effect of untuned buffers on the driver. |
| T12 | Yes | D17 checks the match directly, so the design does not depend on the number. The probe records it. |

## 7. Consequences for the sections that claude owns

### 7.1 Control plane

1. The controller worker thread is the only caller of the gateway. The composition root binds it and calls `run_worker()` (D5).
2. Controller states are `kIdle`, `kStreaming`, `kOutage`, `kStalled`, and `kWedged` (D16, D19, D22).
3. The lease count decides start and stop. `idle_linger` defaults to 0 (D16, D25).

### 7.2 Bring-up

`camera.yaml` gets these explicit driver values. Each one already has a reason above.

| Parameter | Value | Choice |
|---|---|---|
| `camera_id` | `"0GPF3"` | existing |
| `autostream` | `0` | existing |
| `buffer_count` | `7` | D10 |
| `use_ros_time` | `false` | D20 |
| `command_feature_timeout` | `0` | facts 1.5.3, A33 |
| `image_raw.enable_pub_plugins` | `["image_transport/raw"]` | D8 |
| `settings_file`, `camera_info_url` | not set | D15, D18 |

The `AcquisitionProfile` values of D18 go in a separate bringup file that the project node reads. A host check list covers T10, T11, and R15.

### 7.3 Testing

1. Unit tests without ROS: the queue (capacity, drop oldest, `close` wakes `take`, `kWrongThread`), the epoch rules (D11), and the stamp gap count (D12).
2. Controller tests with `FakeCameraGateway` and `FakeFrameSource`: lease start and stop, the allow-list, the wedge state, the profile readback, get image warm and cold, and the silence and outage steps.
3. A hardware probe, `camera_feed_probe`: delivered rate, stamp gaps, evictions, match time (T12), and cold get image time.
4. A hardware outage test: unplug and replug the PoE cable during a feed. It checks D22 and R16.
5. Any trigger hardware test must stop each tool that calls `status`, including the runner guard (c2 §4 row Testing).

### 7.4 Implementation sequence

1. Bring-up values in `camera.yaml` (no code).
2. The `kAcquisition` domain and codes, with unit tests. This adds the first gtest target.
3. `ImageFrame`, `FrameSubscription` queue, and unit tests.
4. `VimbaXFrameSource` and `camera_feed_probe`. The probe gives the D9, D10, and D12 numbers.
5. `AcquisitionController` with fakes and unit tests: leases, profile, allow-list, wedge, get image, silence.
6. The outage hardware test.
7. Phase 2: fork patches if Logan accepts them, then the trigger get image.
