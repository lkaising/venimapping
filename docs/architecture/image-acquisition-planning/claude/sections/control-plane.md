## Control plane

The control plane is the `AcquisitionController` class. It decides when the driver stream starts and stops, which camera values it expects, and what a feed or a get image call sees during a failure. It is ROS-free. It uses two ports and owns neither of them: `CameraGateway` for driver services and `FrameSource` for frames (d2, d16).

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption that is cheap to reverse. `[Q]` is an open question. Register ids are in lower case, for example `d17`. Citations of the form `path:line` are from the project worktree root. `driver:path:line` is from the driver root. `ros:path:line` is from the ROS source root.

### Inputs from the code

1. `[F]` `CameraGateway` already has every call that the controller needs: `connection_status`, `stream_start`, `stream_stop`, and the enum, int, bool, and float feature getters and setters (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:35-110`). The controller adds no gateway method (d2).
2. `[F]` Each feature getter and setter takes a `FeatureModule` argument (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:59-110`). The camera features are under `FeatureModule::kRemoteDevice` (`src/venimapping_camera/include/venimapping_camera/types/feature_module.hpp:15-21`).
3. `[F]` The gateway does no readback, and a setter that times out can still apply (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:24-26`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:49`).
4. `[F]` Gateway calls block. They must come from the thread that called `bind_to_current_thread()`, and that thread must not spin the node (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-47`, `:63-64`).
5. `[F]` The gateway sets one deadline for each call when the call starts. At the deadline, it removes the pending request and returns a `kGateway` timeout (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:187-201`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:79-94`). A call is therefore bounded, but the controller cannot cancel it.
6. `[F]` `camera_status()` leaves `TriggerSelector` on its last value (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:69-71`). The controller never calls it in phase 1.
7. `[F]` With `autostream: 0`, only a `stream_start` call and the reconnect restart start the stream (`src/venimapping_bringup/config/camera.yaml:12`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:588-593`).
8. `[F]` A start while active and a stop while stopped succeed with no effect. A start or a stop in `kStarting` or `kStopping` returns -15, and no service resets that state (`driver:vimbax_camera/src/vimbax_camera.cpp:516-519`, `:582-585`).
9. `[F]` The driver starts its frame processing thread before `CaptureStart` and `AcquisitionStart`, which can still fail (`driver:vimbax_camera/src/vimbax_camera.cpp:458-510`).
10. `[F]` The `connected` service returns `camera_ != nullptr` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1520-1527`). A new camera object starts in `kStopped` (`driver:vimbax_camera/include/vimbax_camera/vimbax_camera.hpp:317`).
11. `[F]` `take` returns a queued frame at once. A timeout of 0 or less acts as `try_take` (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:100`).
12. `[F]` `ImageFrame` has no steady-clock receipt time. Its only time field is `host_stamp_ns`, the driver stamp (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:15-26`). A consumer therefore cannot see when a frame entered its queue.

### Public interface

Header `include/venimapping_camera/acquisition_controller.hpp`, target `venimapping_camera_acquisition` (d1, ic0, ic8). The sketch gives names and signatures. The header carries the full comments.

```cpp
namespace venimapping::camera {

namespace detail { class LeaseLink; }       // private, src/acquisition_support/lease_link.hpp

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
  std::chrono::milliseconds deadline{5000}; // caller deadline for feed_open
};

struct GetImageOptions {
  std::chrono::milliseconds deadline{2000}; // d26
};

enum class StreamState : std::uint8_t {
  kIdle, kStreaming, kOutage, kConnectionUnknown, kStalled, kFaulted, kWedged, kShutDown,
};

struct ControllerStatus {
  StreamState state;
  std::uint32_t leases;
  std::uint32_t epoch;                          // last EpochStart::epoch, 0 before the first
  std::optional<Error> last_error;              // first error of the last failed operation
  std::optional<Error> last_reconciliation;     // error of the last reconciliation or confirmation stop
};

class Feed final {                          // move-only, ic2
 public:
  Feed(Feed&&) noexcept;                    // the source becomes empty
  Feed& operator=(Feed&&) noexcept;         // closes this Feed first, then takes the source
  ~Feed();                                  // runs close()
  [[nodiscard]] Expected<std::optional<ImageFrame>> take(std::chrono::milliseconds timeout);
  [[nodiscard]] Expected<std::optional<ImageFrame>> try_take();
  void close() noexcept;                    // releases the lease at most once
  [[nodiscard]] FrameSubscriptionStats stats() const;

 private:
  std::unique_ptr<FrameSubscription> subscription_;   // sole owner, ic2 Feed item 1
  std::shared_ptr<detail::LeaseLink> link_;           // lease release and shutdown close
};

class AcquisitionController final {
 public:
  using WorkerInit = std::function<Expected<void>()>;

  // Fails with kInvalidArgument for a bad option, and with kFormatNotStreamable
  // if an allowed format is not on the driver gate. Starts no thread.
  [[nodiscard]] static Expected<std::unique_ptr<AcquisitionController>> create(
      CameraGateway& gateway, FrameSource& frames, ControllerOptions options);

  // Starts the worker. The worker runs init first. Returns the init result,
  // kInvalidArgument for a second call, or kFeedClosed after shutdown started.
  // A failed or shut-down start returns only after the worker has exited.
  [[nodiscard]] Expected<void> start(WorkerInit init);

  // Idempotent. Any thread. On the worker thread it only requests the stop.
  // Elsewhere it returns after the worker has exited, or at once if no worker started.
  void shutdown() noexcept;
  ~AcquisitionController();                 // runs shutdown()

  [[nodiscard]] Expected<Feed> feed_open(const FeedOptions& options);
  [[nodiscard]] Expected<ImageFrame> get_image(const GetImageOptions& options);
  [[nodiscard]] ControllerStatus status() const;
};

}  // namespace venimapping::camera
```

1. The controller is pinned. It is not copyable and not movable, like `CameraGateway` (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:29-32`).
2. `create` takes references. The composition root keeps the gateway and the frame source alive until the controller is destroyed (ic4).
3. `WorkerInit` lets the composition root bind the gateway thread without a ROS type in this header. The root passes `[&gw] { return gw.bind_to_current_thread(); }` (i29).
4. `feed_open`, `get_image`, `status`, and `shutdown` are safe from any thread. "Lifecycle and shutdown" gives the rules for `start` and `shutdown`.
5. `Feed` keeps the ic2 rule: it owns its `FrameSubscription` alone. The `LeaseLink` gives the worker a safe close path. See "Subscription ownership".
6. A `Feed` can outlive the controller. It then acts as a closed subscription (ic2 rule 7), and its lease release does nothing.
7. `status()` is how a consumer sees an outage, a stall, a fault, or a wedge. `take` stays empty in those states (d22, R14).

### Threads

The controller follows ic4. It adds no thread beyond the worker.

| Thread | Runs in the controller | Never does |
|---|---|---|
| Controller worker | The request queue, all gateway calls, all `FrameSource` calls, the 100 ms tick, the shutdown steps | `take` or `try_take`, a join of its own thread, a wait for `kStopped` |
| Caller of `feed_open` or `get_image` | Posts a request and waits on its request state until the deadline. In `get_image`, it also runs `take` on the get image subscription | Gateway calls, `FrameSource` calls |
| Any other thread | `Feed::close`, `status`, `start`, `shutdown` | A gateway call |

1. The worker is the only gateway caller (d5 item 2, d16). Every stream and feature call is therefore serial. A second start or a feature write cannot race a stop.
2. The worker waits on one condition variable with a timeout to the next tick. A request wakes it at once.
3. `shutdown()` waits for the worker to exit. The worker finishes its pending gateway call first, so the wait is bounded by about three gateway timeouts: the pending call, the stop, and one reconciliation stop.
4. `[A]` Each in-process gateway call takes a few milliseconds. The CLI value of 586.6 ms per call includes process start and discovery (c1 §3.5 item 4), so it does not apply. The feed probe records the in-process value.

### Requests and deadlines

Each `feed_open` and each `get_image` makes one request state. The caller and the worker share it through a `std::shared_ptr`.

| Field | Meaning |
|---|---|
| `deadline` | One absolute steady-clock time: the call time plus `FeedOptions::deadline` or `GetImageOptions::deadline` |
| `outcome` | `kPending`, `kDelivered`, or `kAbandoned`. One mutex guards it, and one condition variable signals it |
| `result` | The `Feed` and, for get image, the value `R`. Or an error |

1. Only one transition leaves `kPending`. The side that makes it owns the cleanup.
2. The worker delivers with `kPending` to `kDelivered`. After that, the caller owns the `Feed` and its lease.
3. The caller abandons at the deadline with `kPending` to `kAbandoned`, and returns `kDeadlinePassed`.
4. The worker abandons a request whose deadline has passed when it checks. The caller then wakes and returns `kDeadlinePassed`.
5. If the worker cannot deliver because the request is `kAbandoned`, it destroys the `Feed` that it built. The `Feed` destructor closes the subscription and posts the lease release. The worker handles that release in its next loop.

A check point reads the outcome and the steady clock under the outcome mutex. If the outcome is `kAbandoned`, or the deadline has passed, the request stops there. The worker makes a check point at each of these places:

1. When it takes the request from the queue. An expired request gets no `subscribe` and no gateway call.
2. Before each gateway call that the request causes. This covers each of the 8 readback calls, each corrective write, the confirmed stop of start step 2.1, and `stream_start`.
3. Before each 10 ms match poll.
4. Before `open_admission`.
5. At delivery. The worker makes the `kDelivered` transition only if the deadline has not passed, in the same locked section as the check.

When a check point stops a request:

1. The worker makes no further call for that request.
2. If the stop comes after `open_admission` and before `stream_start`, the worker calls `close_admission()` at once. This clears each queue, so no frame of the unstarted epoch stays in a queue. The epoch number is used up. The next `open_admission` returns the next number.
3. The worker then destroys the `Feed`, and the release rules in "Leases and the stream lifecycle" run. They stop the stream if no other lease exists and the stop is not confirmed.
4. The state does not change because of the stop. A start sequence in `kIdle` ends in `kIdle`, and one in `kFaulted` ends in `kFaulted`.

A gateway call that has started always runs to its end, because the gateway has no cancel (input 5). With a check before each call, the worker is free within one gateway timeout after the deadline. After a `stream_start` that started, the worker runs the release rules. If `stream_start` failed, the failure recovery runs first (d19).

A start sequence that runs for a recovery with no request has no deadline and no check point.

`[A]` `FeedOptions::deadline` is 5000 ms. The in-process cold path is 8 reads, up to 8 writes, 8 more reads, the match wait, and `stream_start`. At a few milliseconds per call, this is less than 500 ms. With a 2000 ms gateway timeout and a camera that does not answer, the path without a deadline is about 50 s (N4). What depends on it: the `FeedOpenDeadline` test and the `kDeadlinePassed` row.

### Lifecycle and shutdown

The controller keeps a lifecycle value: `kCreated`, `kStarting`, `kRunning`, `kStopping`, or `kStopped`. One lifecycle mutex guards the value, the shutdown flag, the `std::thread` object of the worker, the worker thread id, and the init result. One lifecycle condition variable on that mutex signals each change. The request queue has its own mutex. A thread that holds both takes the lifecycle mutex first. `status().state` is `kShutDown` in `kStopping` and `kStopped`.

| Lifecycle point | New request | Queued request |
|---|---|---|
| `kCreated`, after `create` and before `start` | Waits in the queue | Runs after `start`. If its deadline passes first, the caller returns `kDeadlinePassed` |
| `kStarting`, and `WorkerInit` fails | `kFeedClosed` at once | The worker completes it with `kFeedClosed` |
| `kRunning` | Normal rules | Normal rules |
| `shutdown()` before `start` | `kFeedClosed` at once | The `shutdown()` caller completes it with `kFeedClosed` |
| `shutdown()` after `start` | `kFeedClosed` at once | The worker completes it with `kFeedClosed` |
| `kStopped` | `kFeedClosed` at once | None |

Lifecycle transitions. No other transition exists:

| From | To | Thread | When |
|---|---|---|---|
| `kCreated` | `kStarting` | `start` | It makes the worker thread and records its id, in one locked section |
| `kCreated` | `kStopped` | `shutdown()` | No worker exists |
| `kStarting` | `kRunning` | `start` | `init` succeeded, and the value is still `kStarting` |
| `kStarting` | `kStopping` | `start` | `init` failed |
| `kStarting`, `kRunning` | `kStopping` | `shutdown()`, on any thread, also the worker | It sets the shutdown flag in the same locked section |
| `kStopping` | `kStopped` | The join owner | After its join returns |

Join rules:

1. The join owner is the thread that moves the `std::thread` object out of the controller under the lifecycle mutex. Only one thread can do that, so only one thread joins.
2. The worker never becomes the join owner. A thread compares its id with the recorded worker id first. The id stays recorded after another thread moves the object out.
3. After its join returns, the join owner locks the lifecycle mutex, sets `kStopped`, and notifies all waiters. No other thread leaves `kStopping`.
4. A thread that did not get the object waits on the lifecycle condition variable until the value is `kStopped`. The wait uses that predicate, so a notify before the wait is not lost.
5. So `kStopped` means that the worker has exited, or that no worker was made. A `start` or `shutdown()` that waits for the worker returns only after `kStopped`.
6. The worker never joins and never waits for `kStopped`.

The stop wait is the step that `start` and `shutdown()` share. Under the lifecycle mutex, if the object is still in the controller, move it out. Then unlock, join, lock, set `kStopped`, and notify all. If the object is gone, wait for `kStopped`.

The stop request is a flag in the request queue. A thread sets it under the queue mutex and notifies the worker. The worker waits with a predicate that includes the flag, so no wake is lost. At the top of each loop, the worker checks the flag. If it is set, the worker runs the shutdown steps.

`start(init)`:

1. Under the lifecycle mutex: in `kCreated`, set `kStarting`, make the worker thread, and record its id. In `kStarting` or `kRunning`, return `kInvalidArgument`. In `kStopping` or `kStopped`, return `kFeedClosed`. Neither error case makes a thread.
2. Wait on the lifecycle condition variable for the init result. The worker runs `init` first, records the result under the lifecycle mutex, and notifies.
3. If `init` failed, the worker makes no gateway call, because the gateway is not bound. In one locked section of the queue mutex, it closes the queue and completes each queued request with `kFeedClosed`. Then it exits.
4. After an `init` failure, `start` sets `kStopping` if the value is still `kStarting`. It runs the stop wait and returns the init error.
5. If `init` succeeded and the value is still `kStarting`, `start` sets `kRunning` and returns success. The check and the set are in one locked section, so no `shutdown()` falls between them.
6. If `init` succeeded and the value is `kStopping`, a `shutdown()` came during `init`. The worker sees the stop request at the top of its first loop and runs the shutdown steps. `start` runs the stop wait and returns `kFeedClosed`.

`shutdown()`:

1. If the calling thread is the worker, which is only possible inside `WorkerInit`: in `kStarting`, set the shutdown flag and `kStopping`, and post the stop request. Return in each case. No join and no wait.
2. In `kCreated`: no worker exists. Set `kStopped` under the lifecycle mutex. Then close the request queue and complete each queued request with `kFeedClosed`, on the calling thread. No queued request holds a `Feed` or a lease, because only the worker calls `subscribe`. No gateway call runs.
3. In `kStarting` or `kRunning`: set the shutdown flag and `kStopping`. Post the stop request. Run the stop wait. The value change and the move of the object are in one locked section.
4. In `kStopping`: run the stop wait. The object can still be in the controller, for example after a `shutdown()` from `WorkerInit`.
5. In `kStopped`: return.

The two overlap cases that the rules close:

1. `init` fails while a `shutdown()` on thread B owns the join. `start` finds no object and waits for `kStopped`. B sets `kStopped` after its join. A third `shutdown()` also waits. No call returns before the worker exits.
2. `WorkerInit` calls `shutdown()`, and `init` then succeeds. The value is `kStopping`, and the object is still in the controller. `start` or a `shutdown()` on another thread takes it, joins, and sets `kStopped`. The other one waits for `kStopped`.

The worker shutdown steps, in ic4 stop order step 1. The worker does each gateway step, because only it may call the gateway (input 4):

1. Stop the request that runs at its next check point. Complete it and each queued request with `kFeedClosed`.
2. Close each live subscription through its `LeaseLink`. A waiting `take` in a `Feed` or in a `get_image` caller returns `kFeedClosed` at once.
3. Call `close_admission()`.
4. If the stop is not confirmed, call `stream_stop()`. If it fails, make one reconciliation stop (d19 item 2). Record each error in `status()`. Do not enter `kWedged`.
5. Mark the request queue as closed. Exit.

Rules for the thread that runs shutdown:

1. The destructor runs `shutdown()`. A request state is shared, so a caller that waits during destruction wakes with `kFeedClosed` and uses no freed memory.
2. The controller must not be destroyed on the worker thread, or while another thread runs `start`. Each is a program error, and a debug assertion catches the first.
3. `[A]` `WorkerInit` returns in bounded time. The phase 1 hook only binds the gateway thread. A `start` or a `shutdown()` that waits for the worker waits for `init` too.

### Subscription ownership

`Feed` owns its `std::unique_ptr<FrameSubscription>` alone, as ic2 `Feed` item 1 states. The worker never owns a subscription that it has delivered.

`detail::LeaseLink` is a small shared block. The `Feed` and the worker each hold a `std::shared_ptr` to it. It holds:

1. A mutex.
2. A non-owning `FrameSubscription*`, set when the worker builds the `Feed`.
3. A `released` flag, false at the start.
4. A `std::shared_ptr` to the worker request queue, which has a closed flag. This lets a release outlive the controller.
5. The lease kind: feed or get image.

The link is the lease identity. The worker keeps the live leases as a set of links. `status().leases` is the size of that set.

Rules:

1. `Feed::close()` on an empty `Feed` does nothing. A `Feed` is empty after a move from it.
2. Otherwise, `Feed::close()` locks the link. If `released` is true, it unlocks and returns. Else it calls `FrameSubscription::close()` if the pointer is not null, sets the pointer to null, and sets `released`. It unlocks and posts one release that names the link. It does not wait for `stream_stop` (ic2 `Feed` item 3).
3. Rule 2 posts at most one release for each link, also after an explicit close and a later destructor, and also for two concurrent `close()` calls.
4. The worker removes the named link from the set. A release whose link is not in the set does nothing. So one lease can never remove another lease.
5. The `Feed` destructor runs `close()` before it destroys the `unique_ptr`. The pointer in the link is therefore null before the subscription object goes away.
6. A move construction takes both pointers. The source becomes empty. The subscription object does not move, so the pointer in the link stays valid.
7. A move assignment into a `Feed` from itself does nothing. Otherwise it runs `close()` on the destination, destroys the destination subscription, and then takes both pointers of the source. The old lease is released once, and the old link holds a null pointer before its subscription goes away.
8. On an empty `Feed`, `take` and `try_take` return `kFeedClosed`, and `stats` returns zeros.
9. Shutdown step 2 locks each link in the set. If the pointer is not null, it calls `close()` through it and sets it to null. It does not set `released`. The later `Feed::close()` posts its release to the closed queue.
10. A release posted to a closed queue does nothing. A `Feed` that outlives the controller therefore releases safely.
11. `[F]` `FrameSubscription::close()` is idempotent and safe from any thread, also after the source is gone (ic2 rules 5 and 7, `docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:104-106`).

The get image path uses the same `Feed` type inside the controller, with capacity 1. The caller holds it during its take loop and destroys it before the return. So both lease kinds have one owner at a time, and ic2 needs no change.

### Stream states and new requests

The worker keeps one more fact besides the state: whether the stop is confirmed. A stop is confirmed after a successful `stream_stop` reply. It stops being confirmed at each `stream_start` call, at each reconnect, and when the no-user check sees frames.

| State | Driver stream and admission | Rule for a new `feed_open` or `get_image` |
|---|---|---|
| `kIdle` | No lease. Stop confirmed or not. Admission closed | Run the start sequence |
| `kStreaming` | Running. Admission open. Includes a linger with no lease | Attach |
| `kOutage`, `kConnectionUnknown` | Unknown. Admission closed, or open and waiting for the first frame after a reconnect | Attach. `feed_open` returns the `Feed` at once. `get_image` waits for a frame until its deadline |
| `kStalled` | The one stop and start cycle ran. Admission open. No frames | Attach |
| `kFaulted` | Leases exist. A recovery start sequence failed before `stream_start`, or failed at `stream_start` with a successful reconciliation stop. Admission closed | Run the start sequence. This is the retry point. A failure goes to the request, and the state stays `kFaulted` |
| `kWedged` | Unknown. Admission closed | `kStreamWedged` with no gateway call (d19 item 3) |
| `kShutDown` | | `kFeedClosed` |

"Attach" means: read `R` for a get image, call `subscribe`, take the lease, and deliver. It makes no gateway call. The request then waits on its queue with the other leases.

1. Attach in `kOutage` and `kConnectionUnknown` follows d22 item 4: the feed stays open, and `take` returns empty. An open feed and a new feed see the same thing. `status()` shows the state.
2. Attach in `kStalled` follows d22 item 8: continued silence gets no more action. Each request does not start a new cycle, because that would repeat stop and start calls on a stalled driver.
3. The worker is serial. A request that arrives during a reconnect step or a d19 recovery waits in the queue. Its deadline still runs.
4. In phase 1, the controller allows one open feed and one outstanding get image. A second request of the same kind returns `kRequestBusy` with no gateway call (d13 item 4).

### Leases and the stream lifecycle

Each open `Feed` and each outstanding `get_image` holds one lease (d16). The worker keeps the set of links.

1. When the set goes from empty to one lease in `kIdle`, the worker runs the start sequence.
2. When the set becomes empty and `linger` is 0, the worker calls `close_admission()`. If the stop is not confirmed, it then calls `stream_stop()`. A failed stop goes to the failure recovery. On success, the state becomes `kIdle`.
3. If `linger` is more than 0, the worker keeps the stream and admission open for that time. A new lease in that time attaches. At the end, step 2 runs (d25).
4. Last release in `kOutage` or `kConnectionUnknown`: the worker calls `close_admission()`, stops the poll, and enters `kIdle`. It makes no stream call, because the camera may be unreachable. The stop stays unconfirmed. The no-user check catches a later driver restart (d22 item 9).
5. Last release in `kFaulted`: step 2 runs. If the stop is already confirmed, the worker makes no gateway call. The state becomes `kIdle`.
6. Last release in `kWedged`: no gateway call. The state stays `kWedged`.

`feed_open(options)` on the worker:

1. Apply the check points and the state rule.
2. Call `FrameSource::subscribe({options.capacity})`. A bad capacity returns `kInvalidArgument` from the data plane (ic2).
3. Build the `Feed` and add its link to the set.
4. Attach, or run the start sequence. On success, deliver the `Feed`. On failure, destroy the `Feed` and give the error to the request.

### Start sequence

The worker runs these steps before each `stream_start` that it makes. The steps implement d17, d18, d19, and ic3 item 4.1. Each feature call uses `FeatureModule::kRemoteDevice`. For a request, the check points in "Requests and deadlines" run before each call.

1. Read back the profile. See "Configuration order and readback".
2. If a value differs:
   1. If the stop is not confirmed, call `stream_stop()`. A failure goes to the failure recovery. This keeps each corrective write on a stopped stream (d18 items 5 and 7).
   2. Write the values that differ, in the d18 order.
   3. Read back again.
3. Call the last readback the final readback. It is the second readback if step 2 ran, else the first.
4. If the final `PixelFormat` is not in `profile.allowed_formats`, return `kFormatNotStreamable`. Make no `stream_start` call (d19 item 1). This check comes before the mismatch check, because a wrong format wedges the driver (c1 §3.1 item 2).
5. If another value in the final readback still differs, return `kProfileMismatch` (d18 item 6).
6. Poll `FrameSource::matched_publishers()` every 10 ms. If it stays 0 for 1000 ms, return `kSubscriptionNotMatched` (d17 item 2).
7. Call `open_admission(significant_bits)`. The value is 8 for `Mono8` and 12 for `Mono12`, from the final `PixelFormat` (d14). Record the returned epoch and the steady time of the call.
8. Call `stream_start()`. The stop is no longer confirmed.
9. If step 8 fails or times out, call `close_admission()` at once. It clears each queue. Then run the failure recovery.

`[F]` The first frame arrives about 79 ms before the `stream_start` reply at Mono8 (c1 §3.5 item 2). Admission opens in step 7, so those frames reach the queue. A reader made after the reply misses 3 to 5 frames (c1 §3.5 item 3).

`[F]` The idle subscription stays matched for the life of the `FrameSource` (d25). On a warm system, step 6 ends at the first poll.

A start sequence that fails at step 4, 5, or 6 made no `stream_start` call. The worker returns the error to the request that caused the sequence. If the sequence ran for a recovery with no request, the worker records the error in `status().last_error` and enters `kFaulted`. Admission stays closed.

### Frames from an epoch whose start is pending

Between step 7 and the `stream_start` result, epoch E is pending. An open feed can take frames of E in that interval, because `take` returns a queued frame at once (input 11).

The rule for a feed that stays open:

1. Each frame of E passed the final readback and the format check for E, because steps 1 to 6 come before step 7. Its `stream_epoch` is E, and its `significant_bits` come from the final `PixelFormat`.
2. A frame of E is a camera image at the verified profile. It stays valid if the start of E fails later. A frame can only exist if the camera acquired it, for example when `stream_start` timed out but the driver started.
3. If the start of E fails, step 9 calls `close_admission()`. This removes each frame of E that the consumer did not take yet.
4. No frame admitted after step 9 carries epoch E, because each later `open_admission` increments the epoch (ic3 item 1).
5. So a consumer sees some frames of E, then empty results, then frames of a later epoch. `status()` shows the failure as `kFaulted`, `kIdle`, or `kWedged`, and `last_error` holds the start error.

The rule for get image:

1. A get image whose request caused the start gets no frame of a failed epoch. The worker delivers its `Feed` only after `stream_start` succeeds.
2. A get image that attached in `kOutage`, `kConnectionUnknown`, or `kStalled` takes frames like a feed. It can return a frame of an epoch whose recovery start fails later. Feed rule 2 applies to that frame.

The section keeps admission open before `stream_start`. Admission after the reply would lose 3 to 5 frames of each cold start (c1 §3.5 item 3). A held state until the reply would need a new data-plane state, and it would only delay valid frames.

### Configuration order and readback

Bring-up loads the phase 1 profile through the driver `settings_file` on each open and reopen (d18 item 1). The controller does not trust the load. `[F]` A failed load only logs an error (`driver:vimbax_camera/src/vimbax_camera_node.cpp:390-400`).

Readback, in this order (d18 item 3). Each call passes `FeatureModule::kRemoteDevice`:

| Step | Gateway call | Compare with |
|---|---|---|
| 1 | `feature_enum_get("PixelFormat", kRemoteDevice)` | `profile.pixel_format` |
| 2 | `feature_int_get("Width", kRemoteDevice)` | `profile.width` |
| 3 | `feature_int_get("Height", kRemoteDevice)` | `profile.height` |
| 4 | `feature_enum_set("TriggerSelector", "FrameStart", kRemoteDevice)` | Write only |
| 5 | `feature_enum_get("TriggerMode", kRemoteDevice)` | `profile.trigger_mode` |
| 6 | `feature_bool_get("AcquisitionFrameRateEnable", kRemoteDevice)` | `profile.frame_rate_enable` |
| 7 | `feature_float_get("AcquisitionFrameRate", kRemoteDevice)` | `profile.frame_rate_hz`, within 0.001 |
| 8 | `feature_float_get("ExposureTime", kRemoteDevice)` | `profile.exposure_time_us`, within 0.001 |

1. `[F]` `TriggerMode` applies to the current `TriggerSelector`, and `camera_status()` moves the selector (facts 1.5.7, c2 §3.3 item 5). Step 4 makes the read in step 5 target `FrameStart`.
2. `[A]` The float tolerance is 0.001. c3 read back 30.000001907348633 Hz after a write of 30.0 (c3 §3 item 3).
3. A read that fails returns its error unchanged. The worker then destroys the request `Feed`, which releases the lease. In a recovery with no request, the error goes to `status().last_error`. The reconnect path then follows its step 3. Other recoveries enter `kFaulted`.
4. For a request, a check point runs before each of the 8 calls. A request that expires after step 2 makes no call for step 3.

The selector write during a stream (i11):

1. After a reconnect, the driver can restart the stream before the readback (`driver:vimbax_camera/src/vimbax_camera_node.cpp:556-568`, `:579-593`). So readback step 4 can run during a stream.
2. `[F]` `TriggerSelector` is writable during acquisition. The camera accepted the selector write while it streamed (c2 §3.3 item 7).
3. `[F]` During both c2 streams, the runner `status` calls moved the selector many times. `TriggerMode` under `FrameStart` did not change (c2 §5 item 9).
4. The section therefore uses the amended d18 item 7: "Phase 1 writes no acquisition value during a stream. The `TriggerSelector` write before a `TriggerMode` read is allowed."
5. A confirmed stop before each reconnect readback would always discard the driver restart that d22 item 5 keeps. Admission stays closed until the readback matches, so no frame with an unverified profile reaches a queue.

Corrective writes, in this order, only after a confirmed stop (d18 items 5 and 7). Each write passes `FeatureModule::kRemoteDevice`:

1. `PixelFormat`, `Width`, `Height`.
2. `TriggerSelector` = `FrameStart`, then `TriggerMode`.
3. `AcquisitionFrameRateEnable`.
4. `AcquisitionFrameRate`.
5. `ExposureTime`.

The worker writes only the values that differ. `[F]` `AcquisitionFrameRate` is read only until `AcquisitionFrameRateEnable` is true (c1 §3.6 item 2, c3 §3 item 2), so the enable comes first. `[F]` `PixelFormat`, `Width`, and `TriggerMode` are read only while streaming (c1 §3.6).

Write results:

1. A write error does not stop the sequence. The second readback decides the result, because a setter that times out can still apply (input 3).
2. The worker keeps the first write error in `status().last_error`. It does not return it.
3. If the second readback matches, the sequence continues with no error.
4. If a value still differs, the result is `kFormatNotStreamable` or `kProfileMismatch`. The text names the value and the write error.
5. If a read in the second readback fails, that read error returns unchanged.
6. A request that expires between two writes makes no further write. The next start sequence reads back and corrects the rest.

### Get image

`get_image(options)` follows d23, d24, d26, and d28.

On the caller thread:

1. Make the request state with `deadline = steady_now + options.deadline`. Post it to the worker.
2. Wait on the request state until it leaves `kPending` or the deadline passes.
3. At the deadline, try the transition to `kAbandoned`. If it succeeds, return `kDeadlinePassed`.
4. If the worker delivered an error, return it.
5. If the worker delivered the `Feed` and `R`, run the take loop below.
6. Destroy the `Feed` before each return. This closes the subscription and posts the lease release.

The take loop:

1. Read the steady clock. If the deadline has passed, return `kDeadlinePassed`. Make no `take` call.
2. Call `take(deadline - now)`. The timeout is more than 0, so the call can wait.
3. If `take` returns `kFeedClosed`, return `kFeedClosed`. If it returns empty, go to step 1.
4. If `take` returns a frame, read the steady clock again. If the deadline has passed, drop the frame and return `kDeadlinePassed`.
5. If the frame has `receive_seq <= R`, skip it and go to step 1.
6. Else return the frame.

Deadline at frame acceptance (d26 item 4):

1. The acceptance check in step 4 decides the result. A call that accepts a frame accepted it at or before the deadline. A call that reaches step 4 after the deadline returns `kDeadlinePassed`.
2. The check is exact only at acceptance, because a consumer cannot see when a frame entered its queue (input 12).
3. The cost is one dropped frame when a frame arrives just before the deadline and the caller wakes just after it. The window is the wake-up time of the caller thread.
4. The caller can retry. A warm retry gets a new frame within about one frame period, 33 ms at 30 Hz (d28).

On the worker:

1. Apply the check points and the state rule.
2. Read `R = frames.stats().frames_received`.
3. Call `subscribe({1})`, build the `Feed`, and add its link to the set (d10 item 3, d28).
4. Attach, or run the start sequence. Then deliver the `Feed` and `R` with the delivery check point.

Freshness (d24, as amended in i12):

1. The answer is a frame that the fan-out pushed to the get image subscription after it opened, with `receive_seq` greater than `frames_received` at the request.
2. `[F]` `receive_seq = frames_received.fetch_add(1) + 1`, and `stats().frames_received` loads the same atomic (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:124`, `:132`). So `R` is the last sequence that existed at the request.
3. `[F]` A callback can take its sequence before `subscribe` and push after the queue link (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:134`). Take loop step 5 skips that frame.
4. The queue has capacity 1 and drops the oldest frame. If several frames arrive before the caller takes, the caller gets the newest one. Each one meets R6, "received after the request".
5. `[F]` A frame received after the request can have been exposed before it (facts A68). Phase 1 accepts this (R6). L4 asks Logan.

Deadline and stop (d26):

1. The deadline covers the queue wait, the lease, the readback, the writes, the format check, the match, `stream_start`, and the acceptance of the first frame.
2. The `stream_stop` after delivery is outside it. A cold call returns before the stop ends.
3. A failed stop goes to the failure recovery. The worker is serial, so the next request waits until the recovery ends (d26 item 6).

Expected times at the 30 Hz profile:

| Case | Time | Source |
|---|---|---|
| Warm, a feed or a linger keeps the stream running | At most about one frame period, 33 ms | d28 |
| Cold, idle and matched | 8 readback calls, then about 110 ms to the `stream_start` reply. The first frame arrives about 30 ms after the driver starts to handle the call. | c1 §3.5 items 1 and 2 |
| Cold stop, after the return | At least 100 ms on the driver | facts 1.4.6 |

Phase 1 has no software trigger (d23, d27). The `TriggerSoftware` path and `kTriggerNoFrame` wait for phase 2.

### Start and stop failure recovery

This subsection implements d19. The worker keeps two results apart: the first error, from the call that failed, and the reconciliation result.

1. If a `stream_start` or a `stream_stop` fails or times out, the worker calls `close_admission()` and records the first error in `status().last_error`. This covers the start sequence, the last release, the no-user stop, the stall cycle, and the reconnect paths. It does not cover the confirmation stop in `kWedged`, which has its own rule below.
2. If the first error is -3, the camera is not reachable. The worker skips the reconciliation stop and goes to the outage rules.
3. Else, the worker calls `stream_stop()` one time to reconcile.
4. If the reconciliation stop succeeds, the stop is confirmed. `status().last_reconciliation` is empty. The request that caused the recovery gets the first error unchanged. The state becomes `kIdle` with no lease, or `kFaulted` with a lease.
5. If the reconciliation stop returns -15, fails another way, or times out, the worker records that error in `status().last_reconciliation`. The state becomes `kWedged`. The request gets `kStreamWedged`. Its text names the first error and the reconciliation error.

`[F]` Each error return in `start_streaming` leaves `kStarting`, and each one in `stop_streaming` leaves `kStopping` (facts 1.4.1, 1.4.2). `[F]` `status.streaming` is false in `kStopping` (`driver:vimbax_camera/src/vimbax_camera.cpp:1508-1513`), so a `status` test misses that wedge. The reconciliation stop catches both states.

A first error of -15 with a successful reconciliation stop means that the driver left the transitional state between the two calls. For example, a reconnect made a new camera object in `kStopped` (input 10). The stream is now stopped, so the request gets -15, and a retry is safe.

In `kWedged`:

1. Admission is closed. Open feeds stay open, and `take` returns empty.
2. Each lease request returns `kStreamWedged` with no gateway call.
3. The error text tells the operator to restart the driver process. The project does not restart it (d19 item 4).
4. The worker calls `connection_status()` every 250 ms, with or without leases.
5. A change signal is a poll result other than `true`, followed by `true`. The result other than `true` can be `false`, -3, or a gateway error.
6. At each change signal, the worker makes exactly one confirmation `stream_stop()`. This stop is not part of the failure recovery. It causes no reconciliation stop, no outage state, and no second stop.
7. If the confirmation stop succeeds, the driver stream is stopped on the current camera object. The worker clears `kWedged`, and the stop is confirmed.
8. If the confirmation stop fails in any way, the state stays `kWedged`. This covers -15, -3, another driver error, a gateway error, and a timeout. The worker records the error in `status().last_reconciliation` and waits for the next change signal. `last_error` keeps the error that caused the wedge.
9. After the clear, with no lease, the state becomes `kIdle`. With leases, the worker runs the start sequence, which reads back and waits for a match before `open_admission` (d19 item 5). A failure there goes to the failure recovery, or to `kFaulted` for steps 4 to 6 of the sequence.

A poll error alone never clears `kWedged`. A gateway timeout on a live driver followed by `true` gives a change signal, but the confirmation stop then returns -15 on the live wedge. Only a successful stop clears the state. This is direct evidence, because no service resets a wedge (input 8).

`[A]` A disconnect and a driver restart each last more than 250 ms, so the poll sees a result other than `true`. If a restart is faster, the wedge stays until the next change signal. The cost is a longer `kWedged`, not a wrong clear.

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

When the poll returns `true`, the reconnect path runs. The stop is not confirmed, because the driver can restart the stream.

1. `[F]` The driver reopens the camera, loads `settings_file`, and then restarts a stream that was active or starting at the disconnect (facts 1.9.6, 1.9.7). The driver ignores the restart result.
2. The worker reads back the profile. Admission stays closed.
3. If a read fails with -3, the state becomes `kOutage`. If it fails another way, the state becomes `kConnectionUnknown`. The poll continues.
4. If all values match, the worker keeps the driver restart. It runs the match wait, then calls `open_admission(significant_bits)` with the bit depth of the `PixelFormat` that it read. The source admits only frames with `host_stamp_ns` greater than the new boundary (d22 item 6, ic3). If the match wait fails, the worker records `kSubscriptionNotMatched` in `status().last_error` and stays in the poll state. The next `true` poll runs this path again.
5. If a value differs, the worker runs the start sequence. Its step 2.1 makes the confirmed stop before any write. A failed stop goes to the failure recovery.
6. If no frame is admitted within one more threshold after step 4, the worker calls `close_admission()` and runs the start sequence one time (d22 item 7). That sequence reads back, waits for the match, opens a new epoch, and calls `stream_start`. A failure goes to the failure recovery, or to `kFaulted` for steps 4 to 6 of the sequence.
7. On the first admitted frame, the state becomes `kStreaming`.
8. If silence continues after step 6, the silence rule runs again from the new `open_admission` time.

In `kStalled`:

1. The worker calls `close_admission()` and `stream_stop()`. A failed stop goes to the failure recovery. A successful stop is confirmed.
2. The worker runs the start sequence. A failure goes to the failure recovery, or to `kFaulted`.
3. If silence continues for one more threshold, the state stays `kStalled`. The worker makes no more calls (d22 item 8).
4. An admitted frame returns the state to `kStreaming`. Admission is open after the cycle, so a late frame still counts.

A stream with no user (d22 item 9):

1. After each confirmed stop, the worker reads `frames_received` as the baseline.
2. On each tick with no lease and no linger, the worker compares `frames_received` with the baseline. If it rose, the stop is no longer confirmed.
3. A rise means that a stream runs with no user, for example after a reconnect. The worker calls `stream_stop()`.
4. If that stop fails or times out, the failure recovery runs. It can end in `kWedged`.
5. This check needs no gateway call while the camera is idle.

New epochs come only from `open_admission` calls (d11). The worker calls it in the start sequence and in reconnect step 4. No stamp rule starts an epoch (d20).

### What this section changes from v1

| v1 choice | v2 choice | Reason |
|---|---|---|
| The policy layer runs on the gateway worker, with no new concurrency (v1 §8) | The same, through the `WorkerInit` hook | The gateway thread contract does not change (d5) |
| `FeedOpen` subscribes and starts, with no match wait (v1 §8.1) | Match wait before each start | A subscription made before `stream_start` does not prove a match (facts A66) |
| `FeedOpen` has no caller deadline | `FeedOptions::deadline`, default 5000 ms, checked before each gateway call | Without it, a camera that does not answer blocks the caller for about 50 s (N4) |
| Configuration is verified by readback, with no fixed source (v1 §8.3) | `settings_file` applies the profile, and the controller reads back and corrects after a confirmed stop | Only `settings_file` applies values before the driver restart after a reopen (d18) |
| `GetImage` has a stream sample and a software trigger strategy (v1 §8.2) | Stream sample only, accepted only at or before the deadline | R6 needs "received after the request", and a trigger stops a feed (d23) |
| A take timeout makes the consumer check the connection (v1 §8.4) | The worker checks silence on a tick and opens a new epoch after recovery | Consumers do not call the gateway, and a reconnect restarts the stream with no project call (d22) |
| Close always stops the stream (v1 §8.1) | The last release stops it | Get image and a feed share one stream (d16, d28) |
