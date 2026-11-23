## Data plane

[F] The driver publishes `sensor_msgs/msg/Image` on `image_raw`. The project gateway uses services and binds blocking calls to one worker thread. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:350-357,1620-1638`, `src/venimapping_camera/src/vimbax_camera_gateway.cpp:49-69`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-64`)

Keep v1's separate frame port and pull interface. The controller composes `FrameSource` with `CameraGateway`. Consumers pull from `FrameSubscription` on their own threads. This keeps frame processing off the executor. The frame API and the VimbaX adapter use separate libraries in `venimapping_camera` (`d1`, `d2`, `d7`, `ic8`). (`docs/architecture/image-acquisition-design-v1.md:306-346`)

[A] Phase 1 serves one local C++ consumer on the driver host with CycloneDDS. The controller allows one feed and one outstanding get image request. This assumption sets the local port and the controller's queue limits (`d13`, `d29`, R1, R12).

[Q] Will a consumer need another process or host, calibration, or more than 8 bits (L2, R11, L5)?

### Frame and pixel ownership

`ImageFrame` is a ROS-free value in `venimapping::camera` (`d3`, `d4`, `d11`, `d14`, `d15`, `ic1`). It exposes one `const noexcept` accessor per field. Scalar accessors return by value. `encoding()` and `tf_frame()` return `const std::string&` into the shared frame block. This avoids a string allocation in a `noexcept` accessor.

| Field | Type | Meaning |
|---|---|---|
| `width`, `height` | `std::uint32_t` each | Image dimensions in pixels, from the message. |
| `step` | `std::uint32_t` | Bytes per row, from the message. |
| `encoding` | `std::string` | Wire encoding, unchanged. |
| `is_bigendian` | `bool` | Pixel byte order, from the message. |
| `tf_frame` | `std::string` | Coordinate frame name from `header.frame_id`. |
| `significant_bits` | `std::uint8_t` | Source bit depth from the final verified `PixelFormat` for this epoch. |
| `host_stamp_ns` | `std::int64_t` | Driver stamp on host `CLOCK_REALTIME`, in nanoseconds since the Unix epoch. |
| `receive_seq` | `std::uint64_t` | Receive sequence for this `FrameSource`, starting at 1. |
| `stream_epoch` | `std::uint32_t` | Admission epoch for this `FrameSource`, starting at 1. |
| `pixels()` | `std::span<const std::byte>` | Read-only view into the received payload. |

`ImageFrame::create(ImageFrameFields, std::shared_ptr<const void>, std::span<const std::byte>)` returns `Expected<ImageFrame>`. It returns `kInvalidArgument` if either dimension is zero or if `step × height` exceeds the span size. Compute the product in 64 bits before the comparison (`ic1`, `ic5`).

`ImageFrame` declares `frame_support::FrameFanout` as a friend. The private `stage` factory validates the layout and allocates a mutable frame block before the fan-out lock. The public `create` factory uses the same validation and returns an immutable frame. Under the lock, only `FrameFanout` sets `stream_epoch` and `significant_bits` on its unpublished block. It then moves the sole staging handle into an `ImageFrame` with a const block and publishes that frame to the queues. The frame is immutable after `FrameFanout` publishes it (`ic1`, `ic3`, `ic8`).

The adapter uses the received message as the type-erased owner and points the span into its `data`. The shared frame block holds the fields, owner, and span. A frame copy increments one reference count and allocates no memory. Accessors are safe on any thread. Keep a frame copy alive while using its string references or pixel span. A retained frame stays valid after the subscription, source, and node are gone. [A] The adapter uses the default message allocator, so the payload lifetime does not depend on the node (`d4`, `ic1`).

[F] The local CycloneDDS receive path uses a regular message because `Image` has unbounded fields. The driver can copy or shift pixels before publish. (`ros:ros2/common_interfaces/sensor_msgs/msg/Image.msg:21-26`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:2949-2984`, `driver:vimbax_camera/src/vimbax_camera.cpp:1695-1712,1781-1806`)

Keep v1's shared owner so fan-out adds no pixel copy. Pass through the payload and encoding. Add `significant_bits` to preserve the source bit depth (`d4`, `d14`). [F] The driver publishes Mono12 as `mono16` with samples shifted left four bits. (`docs/architecture/image-acquisition-design-v1.md:261-305`, `driver:vimbax_camera/src/vimbax_camera.cpp:1791-1797,1835-1844`)

[A] The initial profile uses full-sensor Mono8 at 1296 × 1032 and 30 Hz. The load target is 69.7 Hz. Profile changes affect payload size and load estimates. Each frame carries its own layout (`d10`, `d18`, R2–R5).

[F] The c1 check measured 1,337,472 bytes per image and 93.2 MB/s at the load target. The c3 check measured 30.010 Hz at the initial profile. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:100-119`, `docs/architecture/image-acquisition-planning/codex/camera/c3.md:45-50`)

### Source, subscription, and backpressure

`VimbaXFrameSource` keeps one ROS subscription for its lifetime, including while idle (`d13`, `d25`). `FrameSource::subscribe` opens an empty project queue. The controller owns stream operations and leases (`d16`, `d17`). Get image opens its own capacity-1 subscription on the same source (`d24`, `d28`).

```cpp
struct SubscribeOptions {
  std::size_t capacity = 1;
};

struct FrameSubscriptionStats {
  std::uint64_t frames_delivered;
  std::uint64_t queue_evictions;
  std::uint64_t frames_cleared;
};

struct EpochStart {
  std::uint32_t epoch;
  std::int64_t boundary_ns;
};

struct FrameSourceStats {
  std::uint64_t frames_received;
  std::uint64_t frames_admitted;
  std::uint64_t discarded_layout;
  std::uint64_t discarded_stamp_basis;
  std::uint64_t discarded_admission;
  std::uint64_t callback_ns_max;
  std::uint64_t callback_ns_total;
  std::optional<std::uint64_t> transport_lost;
  std::optional<std::chrono::steady_clock::time_point> last_admitted;
  std::uint32_t current_epoch;
  bool admission_open;
};

class FrameSubscription {
 public:
  virtual ~FrameSubscription() = default;
  [[nodiscard]] virtual Expected<std::optional<ImageFrame>> take(
      std::chrono::milliseconds timeout) = 0;
  [[nodiscard]] virtual Expected<std::optional<ImageFrame>> try_take() = 0;
  virtual void close() noexcept = 0;
  [[nodiscard]] virtual FrameSubscriptionStats stats() const = 0;
};

class FrameSource {
 public:
  virtual ~FrameSource() = default;
  [[nodiscard]] virtual Expected<std::unique_ptr<FrameSubscription>> subscribe(
      const SubscribeOptions& options) = 0;
  [[nodiscard]] virtual std::size_t matched_publishers() const = 0;
  [[nodiscard]] virtual EpochStart open_admission(std::uint8_t significant_bits) = 0;
  virtual void close_admission() noexcept = 0;
  [[nodiscard]] virtual FrameSourceStats stats() const = 0;
};
```

`subscribe` accepts capacities 1 through 4 and returns `kInvalidArgument` outside that range. The error text gives the supplied capacity. Each admission pushes a shared frame to every open queue and increments `frames_delivered` for each push. At capacity, the queue evicts its oldest frame and counts one `queue_evictions` event. The callback never waits for space. Capacity 1 keeps the newest pending frame. This replaces v1's default of 4 to limit backlog for the phase 1 consumer (`d10`, `d13`, `ic2`). (`docs/architecture/image-acquisition-design-v1.md:348-359,714-724`)

`take` returns the oldest queued frame. If the queue is empty, it waits on a condition variable with a steady-clock deadline. A timeout of zero or less acts as `try_take`. A timeout or empty `try_take` returns a successful empty optional, including during suspended admission. The first pull binds the consumer thread. A pull from another thread on an open subscription returns `kWrongThread` (`d7`, `ic2`, `ic5`).

The adapter and `FakeFrameSource` each hold a `FrameFanout` by value. The adapter holds it in a private implementation block in its source file. `FrameFanout` holds shared state with the fan-out lock and the list of open queues. Each list entry holds a shared pointer to its queue block. Each concrete subscription holds a shared pointer to its queue block and another to the shared state. The queue block holds the ring, pull condition variable, closed flag, and subscription counters. The shared state and queue blocks have no references to the source or clock.

`subscribe` creates the subscription, queue storage, and list node before it takes the fan-out lock. It splices the preallocated node into the list under the lock. Any thread can call `stats` or `close`. `close` marks the queue closed, unlinks its node, counts and clears its frames, and wakes a waiting pull under the lock. Destroy detached list nodes after unlocking. Destruction of the concrete subscription calls `close`.

When the source goes away, `FrameFanout` closes and unlinks all remaining queues under the same lock. A waiting or later pull returns `kFeedClosed`. A later `close` sees the closed flag in its own queue block and returns. Subscription stats remain readable. The subscription uses its shared state and queue block throughout, so the source can disappear while a consumer waits (`ic2`, `ic5`).

Use four local frame holders when evicting or clearing entries under the fan-out lock. Each open queue holds a suffix of admitted pushes because each push reaches every open queue and each removal takes the oldest frame. With capacity at most 4, the queues can contain at most four distinct frames when the operation starts. Use `receive_seq` to match references to the same frame. Move one reference per distinct frame into a holder before removing duplicate references. Release the holders after unlocking. This covers a push, `close_admission`, subscription close, and source teardown. A pull moves its frame out before unlocking. It builds any error result after unlocking (`ic8`).

For the Mono8 profile, each queue retains at most `capacity × step × height` pending payload bytes. The feed and get image queues together hold at most five pending references. Those references cover at most four distinct payloads, or 5,349,888 bytes. Consumer-held frames add up to `step × height` each. Deferred release holders, DDS history, the in-flight callback, and SDK buffers can also hold payloads. Bring-up sets `buffer_count: 7` in `camera.yaml` at launch (`d10`, `d13`, `ic1`).

### Admission and loss reporting

[A] Phase 1 sets driver `use_ros_time: true` and sets `use_sim_time: false` on the driver and application node. [F] The driver then stamps each frame after the transform and before publish. The stamp marks processing time. (`d20`, `ic6`, `driver:vimbax_camera/src/vimbax_camera.cpp:1745-1757`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1605-1618`, `ros:ros2/rcl/rcl/src/rcl/time.c:62-72`, `ros:ros2/rcutils/src/time_unix.c:58-74`)

`FrameFanout` manages admission and source counters (`ic3`, `ic7`). The source starts with admission closed and `current_epoch` zero. Only the controller worker opens admission. For a project start, it opens admission after the match and format checks, before `stream_start`. If it keeps a driver restart after reconnect, it opens admission after profile verification (`d11`, `d17`, `d19`, `d22`). Under the lock, `open_admission` increments the epoch, reads the `CLOCK_REALTIME` boundary, stores `significant_bits`, and opens the gate. It returns `EpochStart`. Under the same lock, `close_admission` closes the gate and clears every queue. It counts each removed frame in `frames_cleared` and leaves the subscriptions open.

The private header `src/frame_support/frame_fanout.hpp` declares `FrameFanoutClock` and `FrameFanout` in `venimapping::camera::frame_support`. The clock provides `realtime_ns()` as `std::int64_t` and `steady_now()` as `std::chrono::steady_clock::time_point`. Construct `FrameFanout` with a `FrameFanoutClock&`. The clock must outlive `FrameFanout`. The adapter owns the production clock and the fake borrows the test clock (`ic7`).

`FrameFanout` exposes `subscribe(const SubscribeOptions&)`, `open_admission(std::uint8_t)`, `close_admission()`, and `stats() const` with the port signatures. Both sources forward these methods. Each source implements `matched_publishers()` itself. `FrameFanout` also exposes `set_transport_lost(std::optional<std::uint64_t>)` for the adapter's RMW event total.

The adapter forwards each converted message to `void on_message(std::shared_ptr<const void> owner, ImageFrameFields fields, std::span<const std::byte> pixels)`. The fields `receive_seq`, `stream_epoch`, and `significant_bits` arrive as zero. The fake uses the same method. Keep the staging handle and the incoming frame's local reference outside the lock scope. A discard goes directly to step 7 (`d11`, `d12`, `d20`, `ic3`, `ic7`).

1. Set `receive_seq = frames_received.fetch_add(1) + 1` on the source's zero-initialized `std::atomic<std::uint64_t>`.
2. Read `steady_now()` for receipt time and the duration start. Read `realtime_ns()` for the stamp check.
3. Stage the frame before taking the fan-out lock. If validation fails, count `discarded_layout`.
4. If the stamp differs from the realtime read by more than 1 s, count `discarded_stamp_basis`.
5. Under the fan-out lock, check admission. If admission is closed or the stamp is at or below the boundary, count `discarded_admission`.
6. Otherwise, finish the unpublished block with the epoch and bit depth. Push the immutable frame to each open queue. Set `last_admitted` to the steady read. Increment `frames_admitted` before unlocking.
7. Release local frame references outside the lock. Read `steady_now()` again. Add the elapsed nanoseconds to `callback_ns_total` with an atomic increment. If the duration exceeds `callback_ns_max`, use atomic compare-and-exchange to raise the maximum.

Each message takes a sequence, including messages that the fan-out discards. The first value is 1 and the sequence never resets. `stats().frames_received` loads the same atomic and gives the last sequence assigned at that load. The duration fields start at zero. `callback_ns_max` is the longest measured interval and `callback_ns_total` is their sum. Concurrent stats reads use atomic loads for these aggregates and for discard counters written outside the lock. The duration covers fan-out work, lock wait, and deferred releases. Adapter conversion and ROS deserialization occur before this interval (`ic3`, `ic7`, `ic8`).

The queue link orders `subscribe` against a push because both use the fan-out lock. Only pushes after the link reach the new queue. A callback can take its sequence before `subscribe` and push after the link. Its sequence can be at or below `frames_received` at the time of `subscribe`.

For get image, the controller worker reads `R = stats().frames_received` for the request before it calls `subscribe`. The control plane skips each frame with `receive_seq <= R`. A qualifying frame has a push after the queue link and `receive_seq > R`. Capacity 1 can evict an earlier qualifying frame before the caller pulls. A test can pause the callback in its first `steady_now()` read to put a queue link between receipt and push (`d24`, `ic7`, `ic8`, `i12`).

The worker reads `last_admitted` on its 100 ms silence tick. The controller owns the threshold and recovery (`d22`). [A] A 1 s stamp check catches the observed device clock basis. A backward host clock step can delay admission until realtime passes the boundary or recovery opens a new epoch (P6, P9). (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:123-143`)

Keep separate counts for callback discards, queue evictions, clears, and RMW events (`d12`). `transport_lost` starts at zero when the RMW supports `message_lost` and stays empty without event support. Phase 1 omits `stamp_gap_frames` and the device stamp. The separate device stamp probe informs L1 (`d20`).

[F] The driver logs incomplete SDK frames and SDK frame ID gaps. CycloneDDS reports DDS sample loss through `message_lost`. It can overwrite an unread history entry without that event. (`driver:vimbax_camera/src/vimbax_camera.cpp:1724-1742`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1603`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3943-3955`, `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`)

An admission discard counts a message that reached the callback. A consumer sequence gap measures a gap in delivery of numbered messages. Incomplete SDK receives, SDK buffer shortages, and unread DDS history overwrites can occur before sequence assignment. Loss before the first received frame of an epoch or in trigger mode can also go unseen (`d12`).

### VimbaX adapter and threads

`VimbaXFrameSource::create(rclcpp::Node&, const std::string& camera_namespace)` returns `Expected<std::unique_ptr<VimbaXFrameSource>>`. The node outlives the adapter. The adapter forbids copy and move. The factory maps creation failures to `kSourceCreateFailed` (`ic2`, `ic5`).

If `camera_namespace` is empty, return `kSourceCreateFailed` before creating the ROS subscription. For a nonempty input, strip trailing slashes. Append `/image_raw`. Create one `rclcpp::Subscription<sensor_msgs::msg::Image>` in the default callback group. [F] The gateway rejects empty input and uses the same name rule for services. (`d8`, `ic2`, `src/venimapping_camera/src/vimbax_camera_gateway.cpp:21-25`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:36-46`)

Fix QoS at BEST_EFFORT, KEEP_LAST 2, VOLATILE. Depth 2 gives the executor one extra unread sample before DDS can overwrite it. The project queue counts its own evictions. [F] The driver's RELIABLE, KEEP_LAST 10, VOLATILE publisher matches this reader. (`d9`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:354-357`, `ros:ros2/rmw/rmw/include/rmw/qos_profiles.h:51-62`, `ros:ros2/rmw_dds_common/rmw_dds_common/src/qos.cpp:114-124`)

Keep v1's plain rclcpp reader for raw pixels. The bring-up filter selects only the raw plugin, so extra installed plugins cannot add image topics (`d8`, `ic6`). (`docs/architecture/image-acquisition-design-v1.md:377-389`, `ros:ros-perception/image_common/image_transport/src/publisher.cpp:112-155`)

Parse `header.stamp` as `int64(sec) × 1,000,000,000 + nanosec`. The callback takes only `std::shared_ptr<const sensor_msgs::msg::Image>`. It passes layout, stamp, owner, and byte span to `FrameFanout` (`d20`, `ic7`). [A] Phase 1 needs only raw frames. This sets the scope of the adapter's reader and leaves calibration pairing open (`d15`, R11).

The adapter reports the matched publisher count from `get_publisher_count()`. It returns zero if that call fails. It registers a `message_lost` callback and records the RMW total. If the RMW rejects event registration as unsupported, create the reader without the event (`d17`, `ic2`). (`ros:ros2/rclcpp/rclcpp/src/rclcpp/subscription_base.cpp:162-166,277-288`)

The application runs one node and one `SingleThreadedExecutor` thread for gateway replies, image callbacks, and loss events. The controller uses a separate bound worker. Consumers wait on their own threads. `FrameSource` methods are safe from any thread. In phase 1, the worker owns subscriptions and admission. The callback only contends for the fan-out lock. Under the lock, it does no heap allocation or deallocation, pixel copy, I/O, logging, or consumer work. It completes every push before it returns (`d5`, `ic2`, `ic4`, `ic8`).

1. During shutdown, keep the executor spinning while the controller closes admission, completes any required stop, and joins its worker.
2. Stop and join the executor.
3. Destroy the adapters and node in the composition root's shutdown order (`ic4`).

The feed probe reads the callback duration fields from source stats. It measures gateway round-trip time while stopped and while streaming Mono8 at 69.7 Hz. If streaming adds more than 5 ms to the median, the composition root passes a second node and executor to the adapter (`d5`, `ic4`, `ic7`). (`docs/architecture/image-acquisition-planning/claude/sections/testing.md:149-154`)
