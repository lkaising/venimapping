## Testing

Tests come in four tiers. Each tier needs more of the system than the one before it. Each test names the old behavior that makes it fail and the new behavior that makes it pass (ic7).

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption. `[Q]` is an open question. `ros:path:line` is from the ROS source root.

| Tier | Needs | Runs in | Target or tool |
|---|---|---|---|
| 1. Unit, no ROS | A compiler and GoogleTest | `colcon test`, each build | `test_acquisition_error`, `test_image_frame`, `test_frame_fanout`, `test_acquisition_controller` |
| 2. ROS, no driver | rclcpp and Cyclone DDS | `colcon test`, each build | `test_vimbax_frame_source`, `test_camera_config.py` |
| 3. Driver and camera | The rig, with the driver launched | Manual, before a merge that changes acquisition | `camera_feed_probe` modes |
| 4. Short hardware checks | The rig and an operator | Manual, once per release of the acquisition code | Unplug, settings load, outside reader, stamp, and wedge checks |

### What exists today

1. `[F]` `package.xml` declares `ament_cmake_gtest`, but the build defines no test target (`src/venimapping_camera/package.xml:18`, `src/venimapping_camera/CMakeLists.txt:18-77`).
2. `[F]` `camera_gateway_probe` is the only executable. It checks a live driver and is marked temporary (`src/venimapping_camera/CMakeLists.txt:50-56`).
3. `[F]` No project code receives pixels (facts 1.1.1). For each tier 1 and tier 2 test of new code, the old behavior is therefore "the type or the call does not exist, so the test does not build".

Where a test checks a rule that differs from v1 or from a direct gateway client, the table names that old behavior. That is the behavior that the test must catch.

### Test files

All test files are in `src/venimapping_camera/test/`, except the bring-up test.

| File | Purpose |
|---|---|
| `fakes/test_clock.hpp`, `.cpp` | `TestClock`, a `FrameFanoutClock` with a manual realtime value and a hold point |
| `fakes/fake_frame_source.hpp`, `.cpp` | `FakeFrameSource` over a real `FrameFanout` (ic7 item 5) |
| `fakes/fake_camera_gateway.hpp`, `.cpp` | `FakeCameraGateway`, a scripted `CameraGateway` |
| `acquisition_error_test.cpp` | Tier 1, error domain |
| `image_frame_test.cpp` | Tier 1, `ImageFrame` |
| `frame_fanout_test.cpp` | Tier 1, queues, admission, counters |
| `acquisition_controller_test.cpp` | Tier 1, controller with both fakes |
| `vimbax_frame_source_test.cpp` | Tier 2, adapter over a test publisher |
| `installed_consumer/CMakeLists.txt`, `main.cpp` | Step 5 exit check. A project outside the package that links the installed targets |
| `src/venimapping_bringup/test/test_camera_config.py` | Tier 2, bring-up files (see the bring-up section) |

### Fakes

`TestClock` implements `FrameFanoutClock` (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:118`).

```cpp
class TestClock final : public frame_support::FrameFanoutClock {
 public:
  // Starts at the real CLOCK_REALTIME value. Changes only through advance().
  std::int64_t realtime_ns() const override;
  // Real std::chrono::steady_clock. Blocks once on the hold thread when armed.
  std::chrono::steady_clock::time_point steady_now() const override;
  void advance(std::chrono::nanoseconds step);
  // The next steady_now() call on thread t blocks until release_hold().
  void arm_hold(std::thread::id t);
  void wait_until_held();
  void release_hold();
};
```

1. `steady_now()` reads the real steady clock. The controller compares `last_admitted` with its own `std::chrono::steady_clock::now()`, so both values must come from one clock.
2. `realtime_ns()` is manual, so the boundary and each stamp have a known order.
3. `[F]` `FrameFanout::on_message` makes its first `steady_now()` read after it assigns `receive_seq` and before it takes the fan-out lock (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:124-128`). The hold point is therefore between sequence and lock.
4. A test that checks `callback_ns_max` must not arm the hold, because the hold time adds to the measured duration.
5. The `Fanout.*` tests use the same class and call `advance` for each step.

`FakeFrameSource` implements `FrameSource` over the private `FrameFanout`, so the fake and the adapter share one admission code path (ic7 item 5).

```cpp
class FakeFrameSource final : public FrameSource {
 public:
  explicit FakeFrameSource(TestClock& clock);   // the clock must outlive the fake
  // Without a stamp: clock.advance(1 ms), then stamp with clock.realtime_ns().
  void inject(std::uint32_t width, std::uint32_t height,
              std::optional<std::int64_t> host_stamp_ns = std::nullopt);
  void set_matched_publishers(std::size_t n);
  [[nodiscard]] std::size_t subscriptions_opened() const;
  // Stats of subscription i, also after it closed.
  [[nodiscard]] FrameSubscriptionStats subscription_stats(std::size_t i) const;
  // FrameSource overrides forward to FrameFanout: subscribe, open_admission,
  // close_admission, stats. matched_publishers returns the set value.
};
```

1. A default `inject` advances the realtime value before it stamps the frame. The stamp is therefore strictly greater than each boundary read before the call (d20 item 5). Without the advance, a stamp equal to the boundary is discarded.
2. `subscribe` wraps each subscription in a thin decorator that keeps its stats after `close()`. A test can then see what reached the get image queue.

`FakeCameraGateway` implements all 30 `CameraGateway` methods.

1. It keeps a feature map with the phase 1 profile values and a stream state: stopped, active, starting, or stopping.
2. While active, a write to `PixelFormat`, `Width`, `Height`, or `TriggerMode` fails, as on the camera (c1 §3.6).
3. In starting or stopping, `stream_start` and `stream_stop` return -15, as in the driver (`driver:vimbax_camera/src/vimbax_camera.cpp:516-519`, `:582-585`).
4. `TriggerMode` has one value per `TriggerSelector`. The fake keeps the current selector, so a read without a selector write reads the wrong entry (c2 §3.3).
5. A feature call with a module other than `FeatureModule::kRemoteDevice` fails the test.
6. `script(method, results)` sets the next results of one method, in order. `delay(method, duration)` makes one call block.
7. `on_stream_start(callback)` runs a callback inside `stream_start`. A test uses it to inject frames before the reply (c1 §3.5 item 2).
8. `calls()` returns the call log as strings, for example `enum_set TriggerSelector FrameStart`.
9. `camera_status()` fails the test if a controller calls it.

`[A]` The controller tests run in real time. The thresholds are 250 ms and the tick is 100 ms, so a silence test takes about 0.5 s. The whole controller suite takes a few seconds. A fake worker clock is not needed in phase 1.

### Tier 1: error domain and frame

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `AcquisitionError.FixedNumbers` | `static_assert` on each `AcquisitionCode` value, 1 to 11, and `kAcquisition == 2` | `ErrorDomain` has two values (`src/venimapping_camera/include/venimapping_camera/types/error.hpp:17-20`). Does not build. | Passes |
| `AcquisitionError.Factory` | `from_acquisition(5, "x")` has domain 2, code 5, text "x". `is_acquisition` matches only that pair. | No factory | Passes |
| `ImageFrame.RejectsBadLayout` | Width 0, height 0, and `step * height` larger than the span return `kInvalidArgument`. One case uses `step` 65536 and `height` 65537, so a 32-bit product overflows. | No type | Passes |
| `ImageFrame.CopySharesOwner` | A copy leaves the owner use count unchanged, and both copies point to the same bytes (ic1 item 2) | No type | Passes |
| `ImageFrame.OutlivesOwnerHandle` | The test drops its owner handle. The frame bytes stay readable. | No type | Passes |

### Tier 1: `FrameFanout`

These tests check the data-plane contract in ic2, ic3, and ic8. Each test uses a `TestClock` and calls `advance` between steps.

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Fanout.SequenceFromOne` | The first `receive_seq` is 1. Each later one is 1 more. `frames_received` equals the last sequence. A discarded message also takes a number. | v1 sequence per subscription (v1 §15.1) | Sequence per source, also for discards (d11) |
| `Fanout.ClosedAdmissionDiscards` | Before `open_admission`, a message counts in `discarded_admission`, and `take` returns empty | No admission in v1 | Passes |
| `Fanout.BoundaryDiscards` | With no `advance`, a stamp equal to the boundary is discarded. A stamp 1 ns later is admitted. | No boundary | Strictly greater (d20 item 5) |
| `Fanout.StampBasisDiscards` | A stamp 12673 s, like the camera clock in c1 §3.4, counts in `discarded_stamp_basis` | Device stamps pass | Discarded (ic3 item 3.4) |
| `Fanout.EpochAndBits` | Frames after `open_admission(8)` carry epoch 1 and `significant_bits` 8. A second call gives epoch 2. | No epoch, no bit depth | Passes (d11, d14) |
| `Fanout.DropOldest` | Capacity 2, three frames. `take` gives frames 2 and 3. `queue_evictions` is 1. | v1 default capacity 4 (v1 §15.2) | Default 1, drop oldest (d10) |
| `Fanout.CapacityRange` | Capacity 0 and 5 return `kInvalidArgument`. 1 and 4 succeed. | No range | Passes |
| `Fanout.CloseWakesTake` | A thread waits in `take(10 s)`. `close()` from another thread makes it return `kFeedClosed` within 50 ms. | No type | Passes (ic8 guarantee 2) |
| `Fanout.CloseAdmissionClears` | Two queued frames. `close_admission()` empties the queue and adds 2 to `frames_cleared`. The subscription stays open. | No admission | Passes |
| `Fanout.WrongThread` | A `take` from a second thread returns `kWrongThread` | No check | Passes |
| `Fanout.SubscribeAfterPush` | A frame pushed before `subscribe` does not reach the new queue. The next one does. | No type | Passes (d24) |
| `Fanout.InFlightPushAfterLink` | Arm the hold on a helper thread. The helper injects, and `wait_until_held` returns. `subscribe`, then `release_hold`. The new queue gets the held frame, and its `receive_seq` is at or below `frames_received` at `subscribe`. | No type | Passes. The queue link decides the push (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:134`) |
| `Fanout.CallbackDuration` | No hold. Inject 10 frames. `callback_ns_total` is more than 0 and at least `callback_ns_max`. | No field | Passes (i2) |
| `Fanout.SourceGone` | Destroy the source. `take` on the subscription returns `kFeedClosed`. A later `close()` returns. | No type | Passes (ic2 rule 7) |

### Tier 1: `AcquisitionController`

Each test uses `FakeCameraGateway` and `FakeFrameSource`. A test asserts on `calls()`, on the result, and on `status()`. Times have a tolerance of 50 ms.

Start sequence and configuration:

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Controller.ColdFeedOrder` | Call log: 8 readback calls, then `stream_start`. The match wait and `open_admission(8)` come before `stream_start`. | v1 §8.1 starts with no match wait and no readback | Readback, match, admission, start (d17, d18) |
| `Controller.SelectorBeforeMode` | `enum_set TriggerSelector FrameStart` comes just before each `enum_get TriggerMode`. No `camera_status` call. | A read without the selector reads the wrong selector (c2 §3.3) | Passes |
| `Controller.RemoteDeviceModule` | Run a cold feed with one correction. The fake sees each feature call with `kRemoteDevice`. | The draft omitted the module (i16) | Passes |
| `Controller.KeepsFramesBeforeReply` | `on_stream_start` injects 3 frames before the reply. With capacity 4, the feed gets all 3. | A reader made after the reply misses them (c1 §3.5 item 3) | Passes |
| `Controller.MatchTimeout` | Matched publishers 0. `feed_open` returns `kSubscriptionNotMatched` after 1000 ms, with no `open_admission` and no `stream_start`. The lease count is 0. | v1 starts at once | Passes (d17) |
| `Controller.FormatRefusal` | The fake keeps `PixelFormat` at Mono10 and fails its write. Result `kFormatNotStreamable`. No `stream_start` call. | A direct client calls start, gets -18, and wedges the driver (facts 1.4.1) | Passes (d19 item 1) |
| `Controller.FormatCorrectionBits` | The fake starts at Mono12 with the stream stopped. The log shows the `PixelFormat` write, the second readback, and `open_admission(8)`. The first frame has `significant_bits` 8. | Bit depth from the first readback labels Mono8 as 12 bits (i16) | Bit depth from the final readback (d14) |
| `Controller.WriteNeedsConfirmedStop` | New controller, so the stop is not confirmed. `ExposureTime` differs. The log shows `stream_stop` before the first write. | Writes before a confirmed stop (i13) | Passes (d18 items 5 and 7) |
| `Controller.CorrectiveWriteOrder` | The fake starts with the enable false and the rate 69.71556. The log shows the enable write before the rate write. Then a second readback and a start. | The gateway does no readback (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:24-26`) | Passes (d18 item 5) |
| `Controller.WriteErrorReadbackDecides` | The `ExposureTime` write returns a gateway timeout, but the fake applies it. The second readback matches. The feed opens. `status().last_error` holds the timeout. | Pass-through would fail the feed | Passes (d18 item 6) |
| `Controller.ProfileMismatch` | The fake ignores the `ExposureTime` write. Result `kProfileMismatch`. No start. | No readback | Passes (d18 item 6) |
| `Controller.FloatTolerance` | Rate reads 30.000001907348633. No write. | No readback | Passes (d18 item 4) |

Leases, get image, and deadlines:

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Controller.LeaseCount` | Open a feed, then a warm get image. One `stream_start`. Close the feed while the get image waits. No stop. After the get image returns, `close_admission` and then `stream_stop`. | v1 close always stops (v1 §8.1) | Last release stops (d16) |
| `Controller.Busy` | A second `feed_open` while one is open returns `kRequestBusy` with no gateway call. Same for a second `get_image`. | No limit | Passes (d13) |
| `Controller.WarmFreshness` | Inject frame A, then call `get_image`. The result is a later frame, with `receive_seq` greater than A. | v1 drains, then takes (v1 §8.2) | Passes (d24) |
| `Controller.InFlightFrameSkipped` | Feed open, so the stream is warm. Arm the hold on a helper thread, inject frame N, and `wait_until_held`. Call `get_image` on a second thread. When `subscriptions_opened` rises, `release_hold`, then inject frame N+1. The result is N+1. `subscription_stats` shows that the get image queue got N. | No rule | Passes (d24, i12) |
| `Controller.DeadlinePassed` | `stream_start` blocks 3 s. `get_image` returns `kDeadlinePassed` at 2000 ms. Later, the worker calls `stream_stop`, and the lease count is 0. | No deadline | Passes (d26) |
| `Controller.ExpiredInQueue` | A `feed_open` holds the worker, because `stream_start` blocks 1 s. A `get_image` with a 300 ms deadline returns `kDeadlinePassed` at 300 ms. After the worker takes it, `subscriptions_opened` does not rise, and the log has no new call. | The worker ran expired requests (i14) | Passes |
| `Controller.ExpiredDuringMatch` | Matched publishers 0. `get_image` with a 300 ms deadline returns `kDeadlinePassed` at 300 ms. The worker makes no more match polls after 310 ms. No `open_admission`, no `stream_start`. Lease count 0. | The worker checked only after a gateway call (i14) | Passes |
| `Controller.FeedOpenDeadline` | `stream_start` blocks 6 s. `feed_open` returns `kDeadlinePassed` at 5000 ms. After `stream_start` ends, the worker calls `close_admission` and `stream_stop`. Lease count 0. | No feed deadline (N4) | Passes (i27) |
| `Controller.StopOutsideDeadline` | `stream_stop` blocks 500 ms. A cold `get_image` returns before the stop ends. | No rule | Passes (d26 item 3) |

Failure recovery:

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Controller.StartFailReconciled` | `stream_start` returns -1. Then `close_admission`, and the reconciliation stop succeeds. The result is the driver error -1, domain `kDriver`. `status().last_reconciliation` is empty. State `kIdle`. | No reconciliation | Passes (d19 item 3) |
| `Controller.StartFailClearsQueue` | A feed is open. Silence gives `kStalled`. In the cycle, `on_stream_start` injects a frame, then `stream_start` returns -1. The reconciliation stop succeeds. The feed queue is empty, `frames_cleared` rose, and `take` returns empty. State `kFaulted`. | Admission stayed open after a failed start (i17) | Passes |
| `Controller.FirstErrorMinus15` | `stream_start` returns -15. The reconciliation stop succeeds. The result is driver -15. State `kIdle`. | The table said -15 never reaches a caller (i18) | Passes |
| `Controller.WedgeOnStartTimeout` | `stream_start` times out. The reconciliation stop returns -15. State `kWedged`. `last_error` is the timeout, and `last_reconciliation` is -15. The next `feed_open` returns `kStreamWedged` with no new gateway call. | v1 treats -15 as a race (facts X1) | Passes (d19) |
| `Controller.WedgeOnStopFailure` | The last release. `stream_stop` fails, and the reconciliation stop returns -15. State `kWedged`. | No reconciliation | Passes (d19) |
| `Controller.NoUserStopFails` | No lease. Inject 3 frames. The no-user `stream_stop` returns -1, and the reconciliation stop returns -15. State `kWedged`. | The no-user stop had no failure path (i17) | Passes (d19, d22 item 9) |
| `Controller.WedgeCleared` | In `kWedged`, `connection_status` gives `false`, then `true`. One confirmation `stream_stop` succeeds. State `kIdle`. The next `feed_open` succeeds. | No wedge state | Passes (d19 item 5) |
| `Controller.WedgePollErrorKeepsWedge` | In `kWedged`, `connection_status` gives a gateway timeout, then `true`. The confirmation stop returns -15. State stays `kWedged`. No `stream_start`. | A poll error cleared a live wedge (i18) | Passes |

Silence, outage, and reconnect:

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Controller.SilenceToOutage` | Stop injecting frames. `connection_status` gives `false`. State `kOutage` within 400 ms. `frames_cleared` rises. `take` returns empty, not an error. | v1 leaves the check to the consumer (v1 §8.4) | Passes (d22 items 1 to 4) |
| `Controller.ConnectionUnknown` | Same, but `connection_status` returns a gateway timeout. State `kConnectionUnknown`. | No state | Passes (d22 item 4) |
| `Controller.RequestDuringOutage` | A feed is open in `kOutage`. A `get_image` with a 500 ms deadline makes no gateway call other than the polls. It returns `kDeadlinePassed`. A second run: the poll gives `true` 200 ms after the request, the readback matches, and the result has epoch 2. | Requests took the start path in an outage (i13) | Passes |
| `Controller.ReconnectNewEpoch` | After `kOutage`, `connection_status` gives `true`. Log: 8 readback calls, the match wait, `open_admission(8)`, and no stream call. An old-stamp frame is discarded. A new frame has epoch 2. State `kStreaming`. | No epoch | Passes (d22 items 5 and 6) |
| `Controller.ReconnectProfileChanged` | After a reconnect, `ExposureTime` differs. Log: readback, `stream_stop`, the write, readback, the match wait, `open_admission`, `stream_start`. No write comes before the stop. | No readback | Passes (d22 item 5) |
| `Controller.ReconnectNoRestart` | After a reconnect, the readback matches, and no frame arrives. After one threshold, the log shows `close_admission`, 8 readback calls, the match wait, `open_admission(8)`, and `stream_start`. A frame injected after the start has epoch 3. | The fallback called `stream_start` with no checks (i10) | Passes (d22 item 7) |
| `Controller.Stall` | `connection_status` gives `true` with no frames. One `stream_stop`, then the start sequence and one `stream_start`. No more calls in the next 1 s. State `kStalled`. | No rule | Passes (d22 item 8) |
| `Controller.FaultedRetry` | A reconnect finds a mismatch, and the fake ignores the write. State `kFaulted`, and the feed stays open. The fake then accepts the write. A `get_image` runs the start sequence and returns a frame. State `kStreaming`. | No retry point | Passes |
| `Controller.NoUserStreamStopped` | No lease. Inject 3 frames. The worker calls `stream_stop` within 200 ms. | A reconnect restart runs with no user (facts 1.9.7) | Passes (d22 item 9) |
| `Controller.Linger` | Linger 500 ms. Release, then a get image after 100 ms. One `stream_start` in total. | No linger | Passes (d25) |

Lifecycle and ownership:

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Controller.QueuedBeforeStart` | A `get_image` posted before `start` waits. `start` runs 200 ms later. The request returns a frame. | No rule (i15) | Passes |
| `Controller.InitFailure` | `WorkerInit` returns a gateway error. A queued `feed_open` returns `kFeedClosed`. `start` returns the init error. A later `get_image` returns `kFeedClosed`. State `kShutDown`. | Queued callers had no result (i15) | Passes |
| `Controller.ShutdownFromInit` | `WorkerInit` calls `shutdown()`. `start` returns within 100 ms with no deadlock. State `kShutDown`. | A worker call would join its own thread (i15) | Passes |
| `Controller.Shutdown` | A thread waits in `Feed::take`, and another waits in a warm `get_image`. `shutdown()` makes both return `kFeedClosed`. The log ends with `close_admission` and `stream_stop`, all on the worker thread. A later `feed_open` returns `kFeedClosed`. | No controller | Passes (ic4) |
| `Controller.DestroyWithPendingRequest` | `stream_start` blocks 1 s. A `get_image` waits. The test destroys the controller. The `get_image` returns `kFeedClosed`. No error under AddressSanitizer. | No destructor rule (i15) | Passes |
| `Controller.FeedOutlivesController` | Destroy the controller, then close the `Feed`. No error under AddressSanitizer. | No controller | Passes (ic2 rule 7, i26) |
| `Controller.FeedDestroyDuringShutdown` | One thread destroys a `Feed` while another runs `shutdown()`, 1000 times. No error under ThreadSanitizer and AddressSanitizer. | The worker shared the subscription (i26) | Passes. The `LeaseLink` lock orders the two closes |

### Tier 2: adapter with ROS, no driver

`vimbax_frame_source_test.cpp` makes a node and a `SingleThreadedExecutor` on a test namespace, for example `/acq_test_<pid>`. A test publisher uses RELIABLE, KEEP_LAST 10, VOLATILE, like the driver (`driver:vimbax_camera/src/vimbax_camera_node.cpp:354-357`). No camera and no driver are needed (ic7 item 7).

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Adapter.TopicName` | Namespace `"/acq_test/"` gives the topic `/acq_test/image_raw` | No project subscriber (facts 1.1.1) | Passes (d8) |
| `Adapter.EmptyNamespace` | Namespace `""` returns `kSourceCreateFailed` | No project subscriber | Passes (i8) |
| `Adapter.QosMatches` | `matched_publishers()` reaches 1 within 2 s with the RELIABLE publisher | No project subscriber (facts 1.1.1) | Passes (d9, d17) |
| `Adapter.QosIsBestEffort` | The graph shows the reader with BEST_EFFORT, KEEP_LAST 2 | A default reader is RELIABLE | Passes (d9) |
| `Adapter.Conversion` | A 4 x 2 `mono8` message with a host stamp. The frame has the same width, height, step, encoding, `is_bigendian`, `tf_frame`, stamp in ns, and bytes. | No project frame | Passes (d3) |
| `Adapter.SequenceAcrossDiscards` | One message before `open_admission`, two after. Sequences 1, 2, 3. Admitted frames carry 2 and 3. | No sequence | Passes (d11) |
| `Adapter.StampBasis` | A message with stamp 12673 s. `discarded_stamp_basis` is 1. | Device stamps pass | Passes (ic3) |
| `Adapter.NoPixelCopy` | A node with intra-process communication on. The test fills a `std::unique_ptr<Image>` and records `msg->data.data()`. It publishes the pointer. `frame.pixels().data()` equals the recorded address, and the span size equals `data.size()`. | v1 also keeps the message (v1 §6.1). The test guards the rule. | Passes (d4) |
| `Adapter.TransportLostPresent` | With Cyclone DDS, `transport_lost` has a value | No counter | Passes (d12) |

1. `[F]` With intra-process communication, rclcpp moves a published `unique_ptr` into one `shared_ptr` when no subscription needs ownership. It gives that pointer to each const subscription with no copy (`ros:ros2/rclcpp/rclcpp/include/rclcpp/experimental/intra_process_manager.hpp:243-248`). The adapter callback takes `std::shared_ptr<const Image>` (ic2 adapter item 3). So the received buffer is the published buffer, and the test can compare addresses.
2. `Adapter.NoPixelCopy` uses its own node. The other tests keep the DDS path.

### Tier 3: driver and camera, `camera_feed_probe`

`camera_feed_probe` is a temporary executable, like `camera_gateway_probe`. It is the phase 1 composition root (ic4). It loads `acquisition_profile.yaml` and takes the parameter `mode`.

| Mode | Steps | Pass condition | Old behavior |
|---|---|---|---|
| `bringup` | Part B of the bring-up rig check, after part A | All nine steps pass | `use_ros_time` false, no `settings_file`, and a camera-clock stamp fail it |
| `feed` | Open a feed for 30 s at the profile. Record the rate, the counters, `callback_ns_max`, `callback_ns_total / frames_received`, and the match time. | 29 to 31 Hz. `discarded_*` all 0. `transport_lost` 0. `queue_evictions` less than 1 % of `frames_delivered`. | No feed exists. The CLI reader showed 30.010 Hz (c3 §3 item 4), which is the reference. |
| `load` | Same as `feed` with `profile.acquisition_frame_rate:=69.71556` for 30 s, then 10 s at 30 Hz | 69 to 70.5 Hz. The camera ends at the 30 Hz profile. | No feed exists. The reference is 69.721 Hz (c1 §3.3). |
| `rtt` | 50 `feature_enum_get PixelFormat` calls while stopped, then 50 while streaming at 69.7 Hz. Report the median and the 95th percentile. | Report only. If the streaming median is more than 5 ms above the stopped median, d5 moves the image subscription to a second node. | Not measured |
| `get_image` | 10 cold calls 2 s apart, then 10 warm calls with a feed open | Each returns a frame. Each `receive_seq` is above the value at the request. Cold times under 2 s. Warm times under 67 ms. | Not possible with the gateway alone |
| `stamps` | Needs the driver with `use_ros_time:=false`. No controller. See "Stamp run" | Report only. The two d20 item 7 conditions, or "inconclusive" | Not measured (d12 item 3, d20 item 6) |
| `wedge` | The probe part of the tier 4 wedge check. The probe keeps one controller alive across a driver restart | See tier 4 | Not possible with the gateway alone |

1. The probe prints the RMW name and the two `rmem` values (bring-up host check).
2. The probe restores the 30 Hz profile at the end of each mode that changes it.
3. The match time starts when `VimbaXFrameSource::create` returns. It ends at the first 10 ms poll with `matched_publishers() >= 1`. The limit is 5 s. This is the T12 value. The match wait inside the start sequence is also logged, and it is near 0 on a warm system.
4. The callback time comes from `callback_ns_max` and `callback_ns_total` in `FrameSourceStats`. The interval runs from the first `steady_now()` read after sequence assignment to the read after the deferred releases (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:125`, `:130`, `:132`).

Stamp run, `mode:=stamps`:

1. The probe makes a raw subscription with `rclcpp::MessageInfo`, RELIABLE, KEEP_LAST 10. It waits for `get_publisher_count() >= 1` for at most 1000 ms before it starts the stream. With no match, it stops and reports.
2. The gateway starts the stream at 30 Hz for 30 s. Then it starts it at 69.7 Hz for 30 s. The probe records the wall time of each `stream_start` reply and each `stream_stop` request.
3. For each message, the probe records the device stamp from `header.stamp` and the `source_timestamp` from `MessageInfo`.
4. The operator writes the driver console output to a file over the same interval. Each line has a wall-clock time (`ros:ros2/rcutils/src/logging.c:89`).

Gap rules, after the run:

1. A device gap is a pair of messages whose device stamp delta is more than 1.5 nominal periods. Its size is the delta divided by the period, rounded, minus 1.
2. A driver gap is a `N frames missing` line between the start reply and the stop request. The driver logs it from the SDK frame id, before it publishes the frame after the gap (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1603`).
3. A device gap matches a driver gap if the sizes are equal and the log time is within 50 ms before the `source_timestamp` of the first message after the gap.
4. A matched device gap is a driver gap. An unmatched device gap is a reader gap, a loss between publish and this reader.
5. A driver gap with no matched device gap is a miss of the device stamp counter.

Result rules:

1. Condition 1 of d20 item 7: the 30 Hz run has no device gap and no driver gap, and the delta spread stays within 0.5 period.
2. Condition 2: in the 69.7 Hz run, each driver gap has a matched device gap, and no reader gap occurs.
3. If the 69.7 Hz run has no driver gap, condition 2 is inconclusive. It does not pass.
4. If a reader gap occurs, condition 2 is inconclusive, because a reader gap can hide a driver gap.

`[Q]` The 69.7 Hz run may give no driver gap. The tier 4 outside reader runs at the same time to add load. If no gap occurs in two runs, the report states "inconclusive", and L1 stays open.

### Tier 4: short hardware checks

Each check takes less than 5 minutes. An operator runs them in the order of the table. The driver uses the default launch arguments, so host stamps are on, except in the stamp check.

| Order | Check | Steps | Pass condition | Old behavior |
|---|---|---|---|---|
| 1 | Unplug | 1. Start `camera_feed_probe` with `mode:=feed` and 120 s. 2. After 20 s, pull the PoE cable for 10 s. 3. Plug it in. | `status()` goes to `kOutage` within 400 ms of the last frame. After the reconnect, frames arrive with epoch 2. The feed stays open. | v1 assumed that the driver does not restart the stream (facts A28). With no controller, nothing reports the outage. |
| 2 | Settings load | 1. Start the driver with `settings_file:=/nonexistent.xml`. 2. Change `ExposureTime` with the CLI. 3. Run `mode:=feed`. | The driver log has the `Loading settings from file` error. The controller stops, corrects `ExposureTime`, and streams at 30 Hz | The driver only logs the failed load (`driver:vimbax_camera/src/vimbax_camera_node.cpp:394-399`) |
| 3 | Outside reader and stamp run | 1. Relaunch the driver with `use_ros_time:=false`. 2. Start the outside reader. 3. Run `mode:=stamps`. 4. Stop the outside reader. | Report the stamp results with the gap rules, the driver gap lines, and the outside reader loss lines | Not measured. Tests T9 and d20 item 7. |
| 4 | Host stamps back | 1. Stop the driver. 2. Launch it with the default arguments. 3. Run `ros2 param get /vimbax_camera/vimbax_camera use_ros_time`. | It prints `True` | Without this step, a later feed discards each frame for stamp basis |
| 5 | Wedge | See the steps below | See the steps below | The driver stays wedged, and each start returns -15 (facts 1.4.3) |

The outside reader is a separate RELIABLE reader process:

```sh
ros2 topic echo --qos-reliability reliable --qos-depth 10 \
  --field header.stamp /vimbax_camera/image_raw > outside_reader.log
```

1. `[F]` Jazzy `ros2 topic hz` has only `--window`, `--filter`, and `--wall-time`, and no QoS option (`ros:ros2/ros2cli/ros2topic/ros2topic/verb/hz.py:64-83`). `ros2 topic echo` takes `--qos-reliability` and `--qos-depth` (`ros:ros2/ros2cli/ros2topic/ros2topic/verb/echo.py:60`, `ros:ros2/ros2cli/ros2topic/ros2topic/api/__init__.py:223-256`).
2. `ros2 topic echo` deserializes each full 1337472-byte message in Python before it prints the field. It is therefore a slow RELIABLE reader, which is the T9 case.
3. The outside reader prints a line when it sees lost messages, unless `--no-lost-messages` is set (`ros:ros2/ros2cli/ros2topic/ros2topic/verb/echo.py:94-95`).

Wedge check steps. The scripted gateway tests in tier 1 check the recovery logic (`WedgeOnStartTimeout`, `WedgeCleared`, `WedgePollErrorKeepsWedge`). This check proves only what the fake cannot: the real driver wedge, and the detection of a real driver restart by one live controller.

1. Make sure that the driver runs with host stamps, after check 4.
2. With the CLI and the stream stopped, write `PixelFormat` `Mono10`.
3. Call `stream_start` with the CLI. It returns -18 and leaves `kStarting` (c1 §3.1 item 2).
4. With the CLI, write `PixelFormat` `Mono8`. Read it back.
5. If the read in step 4 is not `Mono8`, stop the check. Record that the rig cannot restore the format while wedged. The tier 1 tests then cover wedge recovery.
6. Start `camera_feed_probe` with `mode:=wedge`. It calls `feed_open` every 2 s and prints `status()` every 1 s.
7. Wait until the probe prints `kWedged`.
8. Restart the driver process with the default arguments. Do not stop the probe.
9. Wait until the probe prints a successful `feed_open`. The probe then reads the feed for 10 s and exits.

Pass condition:

1. The first `feed_open` returns `kStreamWedged`. The log shows readback, match, `open_admission`, `stream_start` with -15, and a reconciliation stop with -15.
2. After step 8, the same controller leaves `kWedged` after one confirmation stop.
3. The next `feed_open` succeeds at Mono8. The feed gives 29 to 31 Hz for 10 s, with an epoch above the epoch before the wedge.

Notes on the wedge check:

1. `[F]` The format refusal returns before `CaptureStart`, so the camera does not acquire (`driver:vimbax_camera/src/vimbax_camera.cpp:427-431`, `:484`). The driver feature setter does not check the stream state (`driver:vimbax_camera/src/vimbax_camera.cpp:964-976`). `[A]` The camera therefore accepts the `PixelFormat` write in step 4. Step 5 handles the case where it does not.
2. Step 4 makes the controller readback match. Without it, the controller would correct Mono10 by a write and hide the order of the wedge path.
3. The wedge check leaves the driver wedged until step 8. It runs last.

### Coverage of register entries

| Entry | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| d5 | | | `rtt` | |
| d9 | | `QosIsBestEffort` | `load` | Outside reader |
| d10, d13 | `DropOldest`, `Busy` | | | |
| d11, d24 | `SequenceFromOne`, `InFlightPushAfterLink`, `WarmFreshness`, `InFlightFrameSkipped` | `SequenceAcrossDiscards` | `get_image` | |
| d12, d20 | `StampBasisDiscards` | `StampBasis` | `bringup`, `stamps` | Stamp run, host stamps back |
| d14 | `EpochAndBits`, `FormatCorrectionBits` | | | |
| d17 | `ColdFeedOrder`, `MatchTimeout`, `ExpiredDuringMatch` | `QosMatches` | `feed` | |
| d18 | `CorrectiveWriteOrder`, `WriteNeedsConfirmedStop`, `WriteErrorReadbackDecides`, `ProfileMismatch` | | `bringup` | Settings load |
| d19 | `Wedge*`, `StartFail*`, `FirstErrorMinus15`, `NoUserStopFails` | | `wedge` | Wedge |
| d22 | `SilenceToOutage`, `RequestDuringOutage`, `Reconnect*`, `Stall`, `FaultedRetry` | | | Unplug |
| d26, i27 | `DeadlinePassed`, `ExpiredInQueue`, `FeedOpenDeadline`, `StopOutsideDeadline` | | `get_image` | |
| ic2, ic4 | `Shutdown`, `DestroyWithPendingRequest`, `FeedOutlivesController`, `FeedDestroyDuringShutdown`, `InitFailure` | | | |
