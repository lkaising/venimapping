## Data plane

[F] The driver publishes `sensor_msgs/msg/Image` on `image_raw`. The project gateway uses services and binds its blocking calls to one worker thread. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:350-357,1620-1638`, `src/venimapping_camera/src/vimbax_camera_gateway.cpp:49-69`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-64`)

Keep v1's separate frame port and pull interface. The controller composes `FrameSource` with `CameraGateway`. Consumers pull from `FrameSubscription` on their own threads, so frame processing cannot hold the executor. The frame API and the VimbaX adapter are separate libraries in `venimapping_camera` (`d1`, `d2`, `d7`, `ic8`). (`docs/architecture/image-acquisition-design-v1.md:306-346`)

[A] Phase 1 serves one local C++ consumer on the driver host with CycloneDDS. The controller allows one feed and one outstanding get image. This assumption sets the local port and queue limits (`d13`, `d29`, R1, R12). [Q] Will a consumer need another process or host, calibration, or more than 8 bits (L2, R11, L5)?

### Frame and pixel ownership

`ImageFrame` is a ROS-free value in `venimapping::camera` (`d3`, `d4`, `d11`, `d14`, `d15`, `ic1`). It carries these fields from `ImageFrameFields` and exposes a `const noexcept` accessor for each field.

| Field | Type | Meaning |
|---|---|---|
| `width`, `height` | `std::uint32_t` each | Image dimensions in pixels, from the message. |
| `step` | `std::uint32_t` | Bytes per row, from the message. |
| `encoding` | `std::string` | Wire encoding, unchanged. |
| `is_bigendian` | `bool` | Pixel byte order, from the message. |
| `tf_frame` | `std::string` | Coordinate frame name from `header.frame_id`. |
| `significant_bits` | `std::uint8_t` | Source bit depth from the `PixelFormat` readback for this epoch. |
| `host_stamp_ns` | `std::int64_t` | Driver stamp on host `CLOCK_REALTIME`, in nanoseconds since the Unix epoch. |
| `receive_seq` | `std::uint64_t` | Receive sequence for this `FrameSource`. |
| `stream_epoch` | `std::uint32_t` | Admission epoch for this `FrameSource`, starting at 1. |
| `pixels()` | `std::span<const std::byte>` | Read-only view into the received payload. |

`ImageFrame::create(ImageFrameFields, std::shared_ptr<const void>, std::span<const std::byte>)` returns `Expected<ImageFrame>`. If either dimension is zero, it returns `kInvalidArgument`. It returns the same error if `step` times `height` exceeds the span size. Compute that product in 64 bits before the comparison (`ic1`, `ic5`).

The adapter uses the received image as the type-erased owner and points the span into its `data`. A shared block holds the fields, the owner, and the span. Copying an `ImageFrame` increments one reference count and allocates no memory. Accessors are safe on any thread. Keep an `ImageFrame` alive while using its span. A retained frame stays valid after the subscription, source, and node are gone. [A] The adapter uses the default message allocator, so the payload lifetime does not depend on the node (`d4`, `ic1`).

[F] With the local CycloneDDS receive path, an image uses a regular received message. Its unbounded fields prevent a loan. The driver can also copy or shift pixels before publish. (`ros:ros2/common_interfaces/sensor_msgs/msg/Image.msg:21-26`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:2949-2984`, `driver:vimbax_camera/src/vimbax_camera.cpp:1695-1712,1781-1806`)

Keep v1's shared owner so fan-out adds no pixel copy. Pass through both the payload and encoding. Add `significant_bits` because the wire encoding alone cannot give the original bit depth (`d4`, `d14`). [F] The driver publishes Mono12 as `mono16` with samples shifted left four bits. (`docs/architecture/image-acquisition-design-v1.md:261-305`, `driver:vimbax_camera/src/vimbax_camera.cpp:1791-1797,1835-1844`)

[A] The initial profile uses full-sensor Mono8 at 1296 × 1032 and 30 Hz. The load target is 69.7 Hz. [F] The c1 check measured 1,337,472 bytes per image and 93.2 MB/s at that load. The c3 check measured 30.010 Hz. A different profile changes the payload and load estimates. Each frame supplies its own layout (`d10`, `d18`, R2–R5). (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:100-119`, `docs/architecture/image-acquisition-planning/codex/camera/c3.md:45-50`)

### Source, subscription, and backpressure

The source keeps one ROS subscription for its lifetime, including while idle (`d13`, `d25`). `subscribe` opens an empty project queue. The controller owns stream operations and leases (`d16`, `d17`). Get image opens a capacity-1 subscription on the same source and leaves the feed queue independent (`d24`, `d28`).

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

`subscribe` accepts capacities 1 through 4 and returns `kInvalidArgument` outside that range. It allocates queue storage before locking the fan-out. Each admission pushes a shared frame to every open queue and increments `frames_delivered` for each push. At capacity, the queue evicts its oldest frame and increments `queue_evictions`. The callback never waits for space. Capacity 1 keeps the newest pending frame. This replaces v1's default of 4 to limit backlog for the phase 1 consumer (`d10`, `d13`, `ic2`). (`docs/architecture/image-acquisition-design-v1.md:348-359,714-724`)

`take` returns the oldest queued frame. If the queue is empty, it waits on a condition variable with a steady-clock deadline. A timeout of zero or less acts as `try_take`. A timeout or empty `try_take` returns a successful empty optional, including during suspended admission. The first pull binds the consumer thread. A pull from another thread on an open subscription returns `kWrongThread` (`d7`, `ic2`, `ic5`).

Any thread can call `stats` or `close`. `close` is idempotent. It removes the queue from fan-out, counts its cleared frames, and wakes a waiting pull. Destruction of the concrete subscription closes it. Source destruction also closes its subscriptions, which can outlive it. After either close, a waiting or later pull returns `kFeedClosed` (`ic2`, `ic5`).

For the Mono8 profile, each queue retains at most `capacity × step × height` payload bytes. Capacity 4 retains at most 5,349,888 bytes. The feed and get image queues together retain at most five payloads, or 6,687,360 bytes. Both queues can reference the same payload. Consumer-held frames add up to `step × height` each at that profile. DDS history, the in-flight callback, and SDK buffers have their own storage. Bring-up sets `buffer_count: 7` in `camera.yaml` at launch (`d10`, `d13`, `ic1`).

### Admission and loss reporting

[A] Phase 1 sets driver `use_ros_time: true` and sets `use_sim_time: false` on the driver and application node. [F] The driver then stamps each frame after the transform and before publish. The stamp marks processing time. (`d20`, `ic6`, `driver:vimbax_camera/src/vimbax_camera.cpp:1745-1757`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1605-1618`, `ros:ros2/rcl/rcl/src/rcl/time.c:62-72`, `ros:ros2/rcutils/src/time_unix.c:58-74`)

`FrameFanout` owns the queues, the fan-out lock, admission, and counters (`ic3`, `ic7`). The source starts with admission closed and `current_epoch` zero. Only the controller worker opens admission. It does so before its start call, after matching and format checks, or before admission resumes after recovery (`d11`, `d17`, `d19`, `d22`). Under the lock, `open_admission` increments the epoch, reads the `CLOCK_REALTIME` boundary, stores `significant_bits`, and returns `EpochStart`. `close_admission` closes the gate and clears every queue. It adds each cleared frame to `frames_cleared` and leaves the subscriptions open.

The adapter forwards each converted message to `FrameFanout::on_message(owner, fields, pixels)` with the three epoch and identity fields initially zero. Tests inject the realtime and steady clocks. The fan-out applies these steps (`d11`, `d12`, `d20`, `ic3`, `ic7`).

1. Increment `frames_received`. Assign the next `receive_seq`, including for a message that admission later discards.
2. Read `CLOCK_REALTIME` and the steady clock once each.
3. Build the frame with `ImageFrame::create` before taking the fan-out lock. If layout validation fails, count the discard in `discarded_layout`.
4. If the stamp differs from the realtime read by more than 1 s, count the discard in `discarded_stamp_basis`.
5. Under the fan-out lock, compare the stamp to the active boundary. If admission is closed or the stamp is at or below the boundary, count the discard in `discarded_admission`.
6. Under the same lock, finish the unpublished frame with the epoch and bit depth. Push it to each open queue. Set `last_admitted` to the steady read. Increment `frames_admitted` before any pull can return the frame.

`receive_seq` never resets during the lifetime of the source. Opening a subscription and fan-out use the same lock. The first admitted push after the queue opens is eligible for get image (`d24`, `ic8`). The worker reads `last_admitted` on its 100 ms silence tick. The controller owns the silence threshold and recovery (`d22`). [A] A 1 s stamp check catches the observed device clock basis. A backward host clock step can delay admission until realtime passes the boundary or recovery opens a new epoch (P6, P9). (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:123-143`)

Use separate counts for callback discards, queue evictions, clears, and RMW events (`d12`). `transport_lost` starts at zero when the RMW supports the event and stays empty when it does not. Phase 1 has no `stamp_gap_frames` or device stamp. The separate device stamp probe informs L1 (`d20`).

[F] The driver logs incomplete SDK frames and SDK frame ID gaps. CycloneDDS reports DDS sample loss through `message_lost`. It can overwrite an unread history entry without that event. (`driver:vimbax_camera/src/vimbax_camera.cpp:1724-1742`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1603`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3943-3955`, `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`)

The counters cannot give the number of lost frames from incomplete receives, SDK buffer shortages, or reader history overwrites. They also cannot count unseen losses at epoch starts or in trigger mode (`d12`). An admission discard counts a message that reached the callback. A receive sequence gap at a consumer therefore does not measure camera loss.

### VimbaX adapter and threads

`VimbaXFrameSource::create(rclcpp::Node&, const std::string& camera_namespace)` returns `Expected<std::unique_ptr<VimbaXFrameSource>>`. The node outlives the adapter, which is neither copyable nor movable. The factory maps creation failures to `kSourceCreateFailed` (`ic2`, `ic5`).

Create one `rclcpp::Subscription<sensor_msgs::msg::Image>` in the node's default callback group. Strip trailing slashes from `camera_namespace` and append `/image_raw`. [F] The gateway uses this namespace rule for its service names. (`d8`, `ic2`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:36-46`)

Fix QoS at BEST_EFFORT, KEEP_LAST 2, VOLATILE. Depth 2 gives the executor one extra unread sample before DDS can overwrite it. The project queue counts its own evictions. [F] The driver's RELIABLE, KEEP_LAST 10, VOLATILE publisher matches this reader. (`d9`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:354-357`, `ros:ros2/rmw/rmw/include/rmw/qos_profiles.h:51-62`, `ros:ros2/rmw_dds_common/rmw_dds_common/src/qos.cpp:114-124`)

Keep v1's plain rclcpp reader for raw pixels. The bring-up filter selects only the raw plugin, so extra installed plugins cannot add image topics (`d8`, `ic6`). (`docs/architecture/image-acquisition-design-v1.md:377-389`, `ros:ros-perception/image_common/image_transport/src/publisher.cpp:112-155`)

Parse `header.stamp` as `int64(sec) × 1,000,000,000 + nanosec`. The callback takes only `std::shared_ptr<const sensor_msgs::msg::Image>`. It passes layout, stamp, owner, and byte span to `FrameFanout` (`d20`, `ic7`). [A] Phase 1 needs only raw frames, so the adapter has no `CameraInfo` reader or pairing policy (`d15`, R11).

The adapter reports the matched publisher count from `get_publisher_count()`. It returns zero if that call fails. It registers a `message_lost` callback and records the RMW count. If event registration fails because the RMW lacks support, create the reader without the event (`d17`, `ic2`). (`ros:ros2/rclcpp/rclcpp/src/rclcpp/subscription_base.cpp:162-166,277-288`)

The application runs one node and one `SingleThreadedExecutor` thread for gateway replies, image callbacks, and loss events. The controller uses a separate bound worker and never pulls a frame. Consumers wait on their own threads. `FrameSource` methods are safe from any thread. In phase 1, the worker owns subscriptions and admission. The callback only contends for the fan-out lock. Under the lock, it does no heap allocation, pixel copy, I/O, logging, or consumer work. Each admitted frame reaches every open queue before the callback returns (`d5`, `ic2`, `ic4`, `ic8`).

During shutdown, keep the executor spinning until the controller closes admission, completes any required stop, and joins its worker. Then stop and join the executor before destroying the adapters and node. The feed probe measures callback time and gateway round-trip time while stopped and while streaming Mono8 at 69.7 Hz. If streaming adds more than 5 ms, the composition root passes a second node and executor to the adapter (`d5`, `ic4`, `ic7`).
