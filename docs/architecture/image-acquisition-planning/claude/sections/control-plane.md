## Control plane

The control plane is the `AcquisitionController` class. It decides when the driver stream starts and stops, which camera values it expects, and what a feed or a get image call sees during a failure. It is ROS-free. It uses two ports and owns neither of them: `CameraGateway` for driver services and `FrameSource` for frames (d2, d16).

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption that is cheap to reverse. `[Q]` is an open question. Register ids are in lower case, for example `d17`. Citations of the form `path:line` are from the project worktree root. `driver:path:line` is from the driver root.

### Inputs from the code

1. `[F]` `CameraGateway` already has every call that the controller needs: `connection_status`, `stream_start`, `stream_stop`, and the enum, int, bool, and float feature getters and setters (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:35-110`). The controller adds no gateway method (d2).
2. `[F]` The gateway does no readback, and a setter that times out can still apply (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:24-26`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:49`).
3. `[F]` Gateway calls block. They must come from the thread that called `bind_to_current_thread()`, and that thread must not spin the node (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-47`, `:63-64`).
4. `[F]` `camera_status()` leaves `TriggerSelector` on its last value (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:69-71`). The controller never calls it in phase 1.
5. `[F]` With `autostream: 0`, only a `stream_start` call and the reconnect restart start the stream (`src/venimapping_bringup/config/camera.yaml:12`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:588-593`).
6. `[F]` A start while active and a stop while stopped succeed with no effect. A start or a stop in `kStarting` or `kStopping` returns -15, and no service resets that state (`driver:vimbax_camera/src/vimbax_camera.cpp:516-519`, `:582-585`).

### Public interface

Header `include/venimapping_camera/acquisition_controller.hpp`, target `venimapping_camera_acquisition` (d1, ic0, ic8). The sketch gives names and signatures. The header carries the full comments.

```cpp
namespace venimapping::camera {

struct AcquisitionProfile {                 // d18, values from the bringup file
  std::string pixel_format;                 // "Mono8"
  std::int64_t width;                       // 1296
  std::int64_t height;                      // 1032
  std::string trigger_mode;                 // "Off", under TriggerSelector FrameStart
  bool frame_rate_enable;                   // true
  double frame_rate_hz;                     // 30.0
  double exposure_time_us;                  // 4999.455
  std::vector<std::string> allowed_formats; // {"Mono8"}, each must be on the driver gate
};

struct ControllerOptions {
  AcquisitionProfile profile;
  std::chrono::milliseconds linger{0};      // d25
};

struct FeedOptions {
  std::size_t capacity = 1;                 // 1 to 4 (d10)
};

struct GetImageOptions {
  std::chrono::milliseconds deadline{2000}; // d26
};

enum class StreamState : std::uint8_t {
  kIdle, kStreaming, kOutage, kConnectionUnknown, kStalled, kWedged, kShutDown,
};

struct ControllerStatus {
  StreamState state;
  std::uint32_t leases;
  std::uint32_t epoch;                      // last EpochStart::epoch, 0 before the first
  std::optional<Error> last_error;          // last gateway or acquisition failure
};

class Feed final {                          // move-only, ic2
 public:
  Feed(Feed&&) noexcept;
  Feed& operator=(Feed&&) noexcept;
  ~Feed();                                  // runs close()
  [[nodiscard]] Expected<std::optional<ImageFrame>> take(std::chrono::milliseconds timeout);
  [[nodiscard]] Expected<std::optional<ImageFrame>> try_take();
  void close() noexcept;
  [[nodiscard]] FrameSubscriptionStats stats() const;
};

class AcquisitionController final {
 public:
  using WorkerInit = std::function<Expected<void>()>;

  // Fails with kInvalidArgument for a bad option, and with kFormatNotStreamable
  // if an allowed format is not on the driver gate. Starts no thread.
  [[nodiscard]] static Expected<std::unique_ptr<AcquisitionController>> create(
      CameraGateway& gateway, FrameSource& frames, ControllerOptions options);

  // Starts the worker. The worker runs init first. Returns the init result.
  [[nodiscard]] Expected<void> start(WorkerInit init);

  // Idempotent. Any thread. Returns after the worker has joined.
  void shutdown() noexcept;

  [[nodiscard]] Expected<Feed> feed_open(const FeedOptions& options);
  [[nodiscard]] Expected<ImageFrame> get_image(const GetImageOptions& options);
  [[nodiscard]] ControllerStatus status() const;
};

}  // namespace venimapping::camera
```

1. The controller is pinned. It is not copyable and not movable, like `CameraGateway` (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:29-32`).
2. `create` takes references. The composition root keeps the gateway and the frame source alive until the controller is destroyed (ic4).
3. `WorkerInit` lets the composition root bind the gateway thread without a ROS type in this header. The root passes `[&gw] { return gw.bind_to_current_thread(); }`.
4. `feed_open`, `get_image`, `status`, and `shutdown` are safe from any thread. A request that comes before `start` waits in the worker queue. A request after `shutdown` returns `kFeedClosed`.
5. A `Feed` can outlive the controller. It then acts as a closed subscription (ic2 rule 7), and its lease release does nothing.
6. `status()` is how a consumer sees an outage, a stall, or a wedge. `take` stays empty in those states (d22, R14).

### Threads

The controller follows ic4. It adds no thread beyond the worker.

| Thread | Runs in the controller | Never does |
|---|---|---|
| Controller worker | The request queue, all gateway calls, all `FrameSource` calls, the 100 ms tick | `take` or `try_take` |
| Caller of `feed_open` or `get_image` | Posts a request, waits on a future. In `get_image`, it also runs `take` on the get image subscription | Gateway calls, `FrameSource` calls |
| Any thread | `Feed::close`, `status`, `shutdown` | Blocks on a gateway call |

1. The worker is the only gateway caller (d5 item 2, d16). Every stream and feature call is therefore serial. A second start or a feature write cannot race a stop.
2. The worker waits on one condition variable with a timeout to the next tick. A request wakes it at once.
3. `[A]` Each in-process gateway call takes a few milliseconds. The CLI value of 586.6 ms per call includes process start and discovery (c1 §3.5 item 4), so it does not apply. The feed probe records the in-process value.

### Leases and the stream lifecycle

Each open `Feed` and each outstanding `get_image` holds one lease (d16). The worker keeps the count.

1. When the count goes from 0 to 1, the worker runs the start sequence in the next subsection.
2. When the count goes from 1 to 0 and `linger` is 0, the worker calls `close_admission()` and then `stream_stop()` (ic3 item 4.3).
3. If `linger` is more than 0, the worker keeps the stream and admission open for that time. A new lease in that time uses the running stream. At the end, step 2 runs (d25).
4. In phase 1, the controller allows one open feed and one outstanding get image. A second request of the same kind returns `kRequestBusy` with no gateway call (d13 item 4).
5. A lease request in `kWedged` returns `kStreamWedged` with no gateway call (d19 item 3).

`feed_open(options)` on the worker:

1. Check the state and the busy rule.
2. Call `FrameSource::subscribe({options.capacity})`. A bad capacity returns `kInvalidArgument` from the data plane (ic2).
3. Take the lease. If the stream already runs with admission open, return the `Feed` at once (d17 item 3).
4. If not, run the start sequence. On success, return the `Feed`. On failure, close the subscription, release the lease, and return the error.

`Feed::close()` calls `FrameSubscription::close()`, which clears the queue and wakes a waiting `take`. It then posts the lease release to the worker and returns. It does not wait for `stream_stop` (ic2).

`[A]` `feed_open` has no caller deadline in phase 1. Each gateway call has the gateway timeout, so the wait is bounded by the sum of the call timeouts and the 1000 ms match limit. See `draft-notes.md`.

### Start sequence

The worker runs these steps before each `stream_start` that it makes. The steps implement d17, d18, d19, and ic3 item 4.1.

1. Read back the profile. See the next subsection.
2. If a value differs, write the profile values and read back again (d18 items 5 and 6).
3. If `PixelFormat` is not in `profile.allowed_formats`, return `kFormatNotStreamable`. Make no `stream_start` call (d19 item 1). This check comes before the mismatch check, because a wrong format wedges the driver (c1 §3.1 item 2).
4. If another value still differs, return `kProfileMismatch` (d18 item 6).
5. Poll `FrameSource::matched_publishers()` every 10 ms. If it stays 0 for 1000 ms, return `kSubscriptionNotMatched` (d17 item 2).
6. Call `open_admission(significant_bits)`. The value is 8 for `Mono8` and 12 for `Mono12`, from the readback in step 1 (d14). Record the returned epoch and the steady time of the call.
7. Call `stream_start()`.
8. If step 7 fails or times out, run the failure recovery in "Start and stop failure recovery".

`[F]` The first frame arrives about 79 ms before the `stream_start` reply at Mono8 (c1 §3.5 item 2). Admission opens in step 6, so those frames reach the queue. A reader made after the reply misses 3 to 5 frames (c1 §3.5 item 3).

`[F]` The idle subscription stays matched for the life of the `FrameSource` (d25). On a warm system, step 5 ends at the first poll.

### Configuration order and readback

Bring-up loads the phase 1 profile through the driver `settings_file` on each open and reopen (d18 item 1). The controller does not trust the load. `[F]` A failed load only logs an error (`driver:vimbax_camera/src/vimbax_camera_node.cpp:390-400`).

Readback, in this order (d18 item 3):

| Step | Gateway call | Compare with |
|---|---|---|
| 1 | `feature_enum_get("PixelFormat")` | `profile.pixel_format` |
| 2 | `feature_int_get("Width")` | `profile.width` |
| 3 | `feature_int_get("Height")` | `profile.height` |
| 4 | `feature_enum_set("TriggerSelector", "FrameStart")` | Write only |
| 5 | `feature_enum_get("TriggerMode")` | `profile.trigger_mode` |
| 6 | `feature_bool_get("AcquisitionFrameRateEnable")` | `profile.frame_rate_enable` |
| 7 | `feature_float_get("AcquisitionFrameRate")` | `profile.frame_rate_hz`, within 0.001 |
| 8 | `feature_float_get("ExposureTime")` | `profile.exposure_time_us`, within 0.001 |

1. `[F]` `TriggerMode` applies to the current `TriggerSelector`, and `camera_status()` moves the selector (facts 1.5.7, c2 §3.3 item 5). Step 4 makes the read in step 5 target `FrameStart`.
2. `[F]` `TriggerSelector` is writable during acquisition (c2 §3.3 item 7). Step 4 is therefore safe after a driver restart, when the stream already runs.
3. `[A]` The float tolerance is 0.001. c3 read back 30.000001907348633 Hz after a write of 30.0 (c3 §3 item 3).
4. A read that fails returns its error unchanged. The worker then releases the lease.

Corrective writes, in this order, only while the stream is stopped (d18 items 5 and 7):

1. `PixelFormat`, `Width`, `Height`.
2. `TriggerSelector` = `FrameStart`, then `TriggerMode`.
3. `AcquisitionFrameRateEnable`.
4. `AcquisitionFrameRate`.
5. `ExposureTime`.

The worker writes only the values that differ. `[F]` `AcquisitionFrameRate` is read only until `AcquisitionFrameRateEnable` is true (c1 §3.6 item 2, c3 §3 item 2), so the enable comes first. `[F]` `PixelFormat`, `Width`, and `TriggerMode` are read only while streaming (c1 §3.6). A write failure does not stop the sequence. The second readback decides the result.

Phase 1 makes no write of an acquisition value during a stream (d18 item 7). The selector write in readback step 4 is the only write during a stream. It changes no acquisition value.

### Get image

`get_image(options)` follows d23, d24, d26, and d28.

On the caller thread:

1. Compute `deadline = steady_now + options.deadline`.
2. Post the request to the worker. Wait on its future until `deadline`.
3. If the future gives an error, return it.
4. If the future gives the subscription and the value `R`, call `take(deadline - now)` in a loop. Skip each frame with `receive_seq <= R`. Return the first other frame.
5. If the deadline passes in step 2 or step 4, return `kDeadlinePassed`.
6. In each case, close the subscription and post the lease release before the return.

On the worker:

1. Check the state and the busy rule.
2. Read `R = frames.stats().frames_received`.
3. Call `subscribe({1})` and take the lease (d10 item 3, d28).
4. If the stream runs with admission open, give the subscription and `R` to the caller.
5. If not, run the start sequence. Then give the subscription and `R` to the caller.

Freshness (d24):

1. The get image queue opens after the request. Each frame in it was pushed after the queue opened.
2. `[A]` `receive_seq` equals `frames_received` after its increment, so `R` is the sequence of the last message that existed at the request. A message that a callback held before the fan-out lock can still reach the new queue. Step 4 on the caller thread skips it.
3. The queue has capacity 1 and drops the oldest frame. If several frames arrive before the caller takes, the caller gets the newest one. Each frame in the queue meets R6, "received after the request".
4. `[F]` A frame received after the request can have been exposed before it (facts A68). Phase 1 accepts this (R6). L4 asks Logan.

Deadline and stop (d26):

1. The deadline covers the lease, the readback, the format check, the match, `stream_start`, and the first frame.
2. The `stream_stop` after delivery is outside it. A cold call returns before the stop ends.
3. If the caller leaves at the deadline, the worker finishes its pending gateway call. It then sees that the caller left, closes the subscription, and releases the lease itself.
4. A failed stop goes to the failure recovery. The worker is serial, so the next request waits until the recovery ends (d26 item 6).

Expected times at the 30 Hz profile:

| Case | Time | Source |
|---|---|---|
| Warm, a feed or a linger keeps the stream running | At most about one frame period, 33 ms | d28 |
| Cold, idle and matched | 8 readback calls, then about 110 ms to the `stream_start` reply. The first frame arrives about 30 ms after the driver starts to handle the call. | c1 §3.5 items 1 and 2 |
| Cold stop, after the return | At least 100 ms on the driver | facts 1.4.6 |

Phase 1 has no software trigger (d23, d27). The `TriggerSoftware` path and `kTriggerNoFrame` wait for phase 2.

### Start and stop failure recovery

This subsection implements d19.

1. If `stream_start` or `stream_stop` fails or times out, the worker calls `stream_stop()` one time to reconcile.
2. If the first failure was -3, the camera is not reachable. The worker skips the reconciliation stop and goes to the outage rules.
3. If the reconciliation stop succeeds, the worker returns the first error unchanged. The state becomes `kIdle`, and the lease is released.
4. If the reconciliation stop returns -15, fails another way, or times out, the state becomes `kWedged`. The request that started the recovery returns `kStreamWedged`.

In `kWedged`:

1. The worker calls `close_admission()`. Open feeds stay open, and `take` returns empty.
2. Each lease request returns `kStreamWedged` with no gateway call.
3. The error text tells the operator to restart the driver process. The project does not restart it (d19 item 4).
4. The worker calls `connection_status()` every 250 ms. A result other than `true` marks the driver as gone. The first `true` after that counts as a reconnect or a driver restart.
5. After that, the worker clears `kWedged`. With no users, it calls `stream_stop()` and enters `kIdle`. With users, it follows the reconnect steps in the next subsection (d19 item 5).

`[F]` Each error return in `start_streaming` leaves `kStarting`, and each one in `stop_streaming` leaves `kStopping` (facts 1.4.1, 1.4.2). `[F]` `status.streaming` is false in `kStopping` (`driver:vimbax_camera/src/vimbax_camera.cpp:1508-1513`), so a `status` test misses that wedge. The reconciliation stop catches both states.

`[A]` A disconnect and a driver restart each last more than 250 ms, so the poll sees the "gone" result.

### Silence, outage, and reconnect

This subsection implements d22 and ic3 items 4 and 5. It runs while a lease exists, or a linger runs, and the stream is in free run.

1. On each 100 ms tick, the worker reads `frames.stats().last_admitted`. The silence start is the later of that time and the steady time of the last `open_admission` call.
2. The threshold is `max(250 ms, 5 x frame period)`. The frame period is `1 / profile.frame_rate_hz`. At 30 Hz, five periods are 167 ms, so the threshold is 250 ms.
3. `[F]` At 30 Hz, the longest measured interval was 34 ms (c3 §3 item 4). At 69.7 Hz, it was 16 ms (c1 §3.3 item 2). A 250 ms gap is therefore not normal jitter.
4. At the threshold, the worker calls `close_admission()`, which clears the queues. It then calls `connection_status()`.

| `connection_status()` result | New state | Worker action |
|---|---|---|
| `false`, or driver error -3 | `kOutage` | Poll `connection_status()` every 250 ms while a user remains |
| Another error | `kConnectionUnknown` | Same poll |
| `true` | `kStalled` | One stop and start cycle |

`[F]` No ROS event reports a disconnect, and each camera service returns -3 while the camera is unavailable (facts 1.9.2, 1.9.5).

In `kOutage` and `kConnectionUnknown`, feeds stay open and `take` returns empty (R14, L9). A `get_image` waits until its deadline and returns `kDeadlinePassed`. `status()` shows the state.

When the poll returns `true`:

1. `[F]` The driver reopens the camera, loads `settings_file`, and then restarts a stream that was active or starting at the disconnect (facts 1.9.6, 1.9.7). The driver ignores the restart result.
2. The worker reads back the profile.
3. If all values match, the worker calls `open_admission()`. The source admits only frames with `host_stamp_ns` greater than the new boundary (d22 item 6, ic3).
4. If a value differs, the worker calls `stream_stop()`, writes the profile, and reads back. It then runs the start sequence from step 3. That sequence opens admission before `stream_start`.
5. If no frame is admitted within one more threshold, the worker calls `stream_start()` one time. A failure goes to the failure recovery (d22 item 7).
6. On the first admitted frame, the state becomes `kStreaming`.

In `kStalled`:

1. The worker calls `stream_stop()`, then runs the start sequence. A failure goes to the failure recovery (d22 item 8).
2. If silence continues for one more threshold, the state stays `kStalled`. The worker makes no more calls.
3. An admitted frame returns the state to `kStreaming`. Admission is open after the cycle, so a late frame still counts.

A stream with no user (d22 item 9):

1. On each tick with no lease and no linger, the worker compares `frames_received` with its value at the last tick.
2. If it rose, a stream runs with no user, for example after a reconnect. The worker calls `stream_stop()`.
3. This check needs no gateway call while the camera is idle.

New epochs come only from `open_admission` calls (d11). The worker calls it in the start sequence and after a reconnect. No stamp rule starts an epoch (d20).

### Shutdown

`shutdown()` follows ic4, stop order step 1.

1. Mark the controller as shutting down. New requests return `kFeedClosed`.
2. Close each open subscription. A waiting `take` returns `kFeedClosed` at once.
3. Call `close_admission()`.
4. If the stream runs, call `stream_stop()`. The executor still spins, so the reply arrives.
5. Join the worker. The state becomes `kShutDown`.

The worker and each `Feed` share ownership of the subscription. A `Feed` that is destroyed during shutdown therefore leaves no dangling pointer.

### What this section changes from v1

| v1 choice | v2 choice | Reason |
|---|---|---|
| The policy layer runs on the gateway worker, with no new concurrency (v1 §8) | The same, through the `WorkerInit` hook | The gateway thread contract does not change (d5) |
| `FeedOpen` subscribes and starts, with no match wait (v1 §8.1) | Match wait before each start | A subscription made before `stream_start` does not prove a match (facts A66) |
| Configuration is verified by readback, with no fixed source (v1 §8.3) | `settings_file` applies the profile, and the controller reads back and corrects | Only `settings_file` applies values before the driver restart after a reopen (d18) |
| `GetImage` has a stream sample and a software trigger strategy (v1 §8.2) | Stream sample only | R6 needs "received after the request", and a trigger stops a feed (d23) |
| A take timeout makes the consumer check the connection (v1 §8.4) | The worker checks silence on a tick and opens a new epoch after recovery | Consumers do not call the gateway, and a reconnect restarts the stream with no project call (d22) |
| Close always stops the stream (v1 §8.1) | The last lease release stops it | Get image and a feed share one stream (d16, d28) |
