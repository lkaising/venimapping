## Testing

Tests come in four tiers. Each tier needs more of the system than the one before it. Each test names the old behavior that makes it fail and the new behavior that makes it pass (ic7).

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption. `[Q]` is an open question.

| Tier | Needs | Runs in | Target or tool |
|---|---|---|---|
| 1. Unit, no ROS | A compiler and GoogleTest | `colcon test`, each build | `test_acquisition_error`, `test_image_frame`, `test_frame_fanout`, `test_acquisition_controller` |
| 2. ROS, no driver | rclcpp and Cyclone DDS | `colcon test`, each build | `test_vimbax_frame_source`, `test_camera_config.py` |
| 3. Driver and camera | The rig, with the driver launched | Manual, before a merge that changes acquisition | `camera_feed_probe` modes |
| 4. Short hardware checks | The rig and an operator | Manual, once per release of the acquisition code | Unplug, wedge, and load checks |

### What exists today

1. `[F]` `package.xml` declares `ament_cmake_gtest`, but the build defines no test target (`src/venimapping_camera/package.xml:18`, `src/venimapping_camera/CMakeLists.txt:18-77`).
2. `[F]` `camera_gateway_probe` is the only executable. It checks a live driver and is marked temporary (`src/venimapping_camera/CMakeLists.txt:50-56`).
3. `[F]` No project code receives pixels (facts 1.1.1). For each tier 1 and tier 2 test of new code, the old behavior is therefore "the type or the call does not exist, so the test does not build".

Where a test checks a rule that differs from v1 or from a direct gateway client, the table names that old behavior. That is the behavior that the test must catch.

### Test files

All test files are in `src/venimapping_camera/test/`, except the bring-up test.

| File | Purpose |
|---|---|
| `fakes/fake_frame_source.hpp`, `.cpp` | `FakeFrameSource` over a real `FrameFanout` (ic7 item 5) |
| `fakes/fake_camera_gateway.hpp`, `.cpp` | `FakeCameraGateway`, a scripted `CameraGateway` |
| `acquisition_error_test.cpp` | Tier 1, error domain |
| `image_frame_test.cpp` | Tier 1, `ImageFrame` |
| `frame_fanout_test.cpp` | Tier 1, queues, admission, counters |
| `acquisition_controller_test.cpp` | Tier 1, controller with both fakes |
| `vimbax_frame_source_test.cpp` | Tier 2, adapter over a test publisher |
| `src/venimapping_bringup/test/test_camera_config.py` | Tier 2, bring-up files (see the bring-up section) |

### Fakes

`FakeFrameSource` implements `FrameSource` over the private `FrameFanout`, so the fake and the adapter share one admission code path (ic7 item 5).

```cpp
class FakeFrameSource final : public FrameSource {
 public:
  explicit FakeFrameSource(FrameFanoutClock& clock);
  // Builds Mono8 fields and calls FrameFanout::on_message.
  // host_stamp_ns defaults to clock.realtime_ns().
  void inject(std::uint32_t width, std::uint32_t height,
              std::optional<std::int64_t> host_stamp_ns = std::nullopt);
  void set_matched_publishers(std::size_t n);
  // FrameSource overrides forward to the FrameFanout.
};
```

`FakeCameraGateway` implements all 30 `CameraGateway` methods.

1. It keeps a feature map with the phase 1 profile values and a stream state: stopped, active, or wedged.
2. While active, a write to `PixelFormat`, `Width`, `Height`, or `TriggerMode` fails, as on the camera (c1 §3.6).
3. `TriggerMode` has one value per `TriggerSelector`. The fake keeps the current selector, so a read without a selector write reads the wrong entry (c2 §3.3).
4. `script(method, result)` sets the next result of one method. `delay(method, duration)` makes one call block.
5. `on_stream_start(callback)` runs a callback inside `stream_start`. A test uses it to inject frames before the reply (c1 §3.5 item 2).
6. `calls()` returns the call log as strings, for example `enum_set TriggerSelector FrameStart`.
7. `camera_status()` fails the test if a controller calls it.

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

These tests check the data-plane contract in ic2, ic3, and ic8. A fake clock sets `realtime_ns()` and `steady_now()`.

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Fanout.SequenceFromOne` | The first `receive_seq` is 1. Each later one is 1 more. `frames_received` equals the last sequence. A discarded message also takes a number. | v1 sequence per subscription (v1 §15.1) | Sequence per source, also for discards (d11) |
| `Fanout.ClosedAdmissionDiscards` | Before `open_admission`, a message counts in `discarded_admission`, and `take` returns empty | No admission in v1 | Passes |
| `Fanout.BoundaryDiscards` | A stamp equal to the boundary is discarded. A stamp 1 ns later is admitted. | No boundary | Strictly greater (d20 item 5) |
| `Fanout.StampBasisDiscards` | A stamp 12673 s, like the camera clock in c1 §3.4, counts in `discarded_stamp_basis` | Device stamps pass | Discarded (ic3 item 3.4) |
| `Fanout.EpochAndBits` | Frames after `open_admission(8)` carry epoch 1 and `significant_bits` 8. A second call gives epoch 2. | No epoch, no bit depth | Passes (d11, d14) |
| `Fanout.DropOldest` | Capacity 2, three frames. `take` gives frames 2 and 3. `queue_evictions` is 1. | v1 default capacity 4 (v1 §15.2) | Default 1, drop oldest (d10) |
| `Fanout.CapacityRange` | Capacity 0 and 5 return `kInvalidArgument`. 1 and 4 succeed. | No range | Passes |
| `Fanout.CloseWakesTake` | A thread waits in `take(10 s)`. `close()` from another thread makes it return `kFeedClosed` within 50 ms. | No type | Passes (ic8 guarantee 2) |
| `Fanout.CloseAdmissionClears` | Two queued frames. `close_admission()` empties the queue and adds 2 to `frames_cleared`. The subscription stays open. | No admission | Passes |
| `Fanout.WrongThread` | A `take` from a second thread returns `kWrongThread` | No check | Passes |
| `Fanout.SubscribeAfterPush` | A frame pushed before `subscribe` does not reach the new queue. The next one does. | No type | Passes (d24) |
| `Fanout.SourceGone` | Destroy the source. `take` on the subscription returns `kFeedClosed`. | No type | Passes (ic2 rule 7) |

### Tier 1: `AcquisitionController`

Each test uses `FakeCameraGateway` and `FakeFrameSource`. A test asserts on `calls()`, on the result, and on `status()`.

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Controller.ColdFeedOrder` | Call log: 8 readback calls, then `stream_start`. `open_admission` comes before `stream_start`. | v1 §8.1 starts with no match wait and no readback | Readback, match, admission, start (d17, d18) |
| `Controller.SelectorBeforeMode` | `enum_set TriggerSelector FrameStart` comes just before each `enum_get TriggerMode`. No `camera_status` call. | A read without the selector reads the wrong selector (c2 §3.3) | Passes |
| `Controller.KeepsFramesBeforeReply` | `on_stream_start` injects 3 frames before the reply. With capacity 4, the feed gets all 3. | A reader made after the reply misses them (c1 §3.5 item 3) | Passes |
| `Controller.MatchTimeout` | Matched publishers 0. `feed_open` returns `kSubscriptionNotMatched` after 1000 ms, with no `stream_start` call. The lease count is 0. | v1 starts at once | Passes (d17) |
| `Controller.FormatRefusal` | The fake keeps `PixelFormat` at Mono10 and fails its write. Result `kFormatNotStreamable`. No `stream_start` call. | A direct client calls start, gets -18, and wedges the driver (facts 1.4.1) | Passes (d19 item 1) |
| `Controller.CorrectiveWriteOrder` | The fake starts with the enable false and the rate 69.71556. The log shows the enable write before the rate write. Then a second readback and a start. | The gateway does no readback (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:24-26`) | Passes (d18 item 5) |
| `Controller.ProfileMismatch` | The fake ignores the `ExposureTime` write. Result `kProfileMismatch`. No start. | No readback | Passes (d18 item 6) |
| `Controller.FloatTolerance` | Rate reads 30.000001907348633. No write. | No readback | Passes (d18 item 4) |
| `Controller.LeaseCount` | Open a feed, then a warm get image. One `stream_start`. Close the feed while the get image waits. No stop. After the get image returns, `close_admission` and then `stream_stop`. | v1 close always stops (v1 §8.1) | Last release stops (d16) |
| `Controller.Busy` | A second `feed_open` while one is open returns `kRequestBusy` with no gateway call. Same for a second `get_image`. | No limit | Passes (d13) |
| `Controller.WarmFreshness` | Inject frame A, then call `get_image`. The result is a later frame, with `receive_seq` greater than A. | v1 drains, then takes (v1 §8.2) | Passes (d24) |
| `Controller.InFlightFrameSkipped` | The test holds a frame with a sequence at or below `R` and delivers it after `subscribe`. `get_image` skips it. | No rule | Passes (d24) |
| `Controller.DeadlinePassed` | `stream_start` blocks 3 s. `get_image` returns `kDeadlinePassed` after 2000 ms, within 50 ms. Later, the worker calls `stream_stop` and the lease count is 0. | No deadline | Passes (d26) |
| `Controller.StopOutsideDeadline` | `stream_stop` blocks 500 ms. A cold `get_image` returns before the stop ends. | No rule | Passes (d26 item 3) |
| `Controller.StartFailReconciled` | `stream_start` returns -1. The reconciliation stop succeeds. The result is the driver error -1, domain `kDriver`. State `kIdle`. | No reconciliation | Passes (d19 item 3) |
| `Controller.WedgeOnStartTimeout` | `stream_start` times out. The reconciliation stop returns -15. State `kWedged`. The next `feed_open` returns `kStreamWedged` with no new gateway call. | v1 treats -15 as a race (facts X1) | Passes (d19) |
| `Controller.WedgeOnStopFailure` | The last release. `stream_stop` fails, and the reconciliation stop returns -15. State `kWedged`. | No reconciliation | Passes (d19) |
| `Controller.WedgeCleared` | In `kWedged`, `connection_status` gives `false`, then `true`. State `kIdle`. The next `feed_open` succeeds. | No wedge state | Passes (d19 item 5) |
| `Controller.SilenceToOutage` | Stop injecting frames. `connection_status` gives `false`. State `kOutage` within 400 ms. `frames_cleared` rises. `take` returns empty, not an error. | v1 leaves the check to the consumer (v1 §8.4) | Passes (d22 items 1 to 4) |
| `Controller.ConnectionUnknown` | Same, but `connection_status` returns a gateway timeout. State `kConnectionUnknown`. | No state | Passes (d22 item 4) |
| `Controller.ReconnectNewEpoch` | After `kOutage`, `connection_status` gives `true`. Readback matches. An old-stamp frame is discarded. A new frame has epoch 2. State `kStreaming`. | No epoch | Passes (d22 items 5 and 6) |
| `Controller.ReconnectProfileChanged` | After a reconnect, `ExposureTime` differs. Log: `stream_stop`, writes, readback, `stream_start`. | No readback | Passes (d22 item 5) |
| `Controller.ReconnectNoRestart` | After a reconnect, no frame arrives. One `stream_start` after one more threshold. | No rule | Passes (d22 item 7) |
| `Controller.Stall` | `connection_status` gives `true` with no frames. One stop and one start. No more calls in the next 1 s. State `kStalled`. | No rule | Passes (d22 item 8) |
| `Controller.NoUserStreamStopped` | No lease. Inject 3 frames. The worker calls `stream_stop` within 200 ms. | A reconnect restart runs with no user (facts 1.9.7) | Passes (d22 item 9) |
| `Controller.Linger` | Linger 500 ms. Release, then a get image after 100 ms. One `stream_start` in total. | No linger | Passes (d25) |
| `Controller.Shutdown` | A thread waits in `Feed::take`. `shutdown()` makes it return `kFeedClosed`. Log ends with `stream_stop`. A later `feed_open` returns `kFeedClosed`. | No controller | Passes (ic4) |
| `Controller.FeedOutlivesController` | Destroy the controller, then close the `Feed`. No crash under AddressSanitizer. | No controller | Passes |

### Tier 2: adapter with ROS, no driver

`vimbax_frame_source_test.cpp` makes a node and a `SingleThreadedExecutor` on a test namespace, for example `/acq_test_<pid>`. A test publisher uses RELIABLE, KEEP_LAST 10, VOLATILE, like the driver (`driver:vimbax_camera/src/vimbax_camera_node.cpp:354-357`). No camera and no driver are needed (ic7 item 7).

| Test | Checks | Old behavior | New behavior |
|---|---|---|---|
| `Adapter.TopicName` | Namespace `"/acq_test/"` gives the topic `/acq_test/image_raw` | No project subscriber (facts 1.1.1) | Passes (d8) |
| `Adapter.QosMatches` | `matched_publishers()` reaches 1 within 2 s with the RELIABLE publisher | No project subscriber (facts 1.1.1) | Passes (d9, d17) |
| `Adapter.QosIsBestEffort` | The graph shows the reader with BEST_EFFORT, KEEP_LAST 2 | A default reader is RELIABLE | Passes (d9) |
| `Adapter.Conversion` | A 4 x 2 `mono8` message with a host stamp. The frame has the same width, height, step, encoding, `is_bigendian`, `tf_frame`, stamp in ns, and bytes. | No project frame | Passes (d3) |
| `Adapter.SequenceAcrossDiscards` | One message before `open_admission`, two after. Sequences 1, 2, 3. Admitted frames carry 2 and 3. | No sequence | Passes (d11) |
| `Adapter.StampBasis` | A message with stamp 12673 s. `discarded_stamp_basis` is 1. | Device stamps pass | Passes (ic3) |
| `Adapter.NoPixelCopy` | The frame span points into the received message data | v1 also keeps the message (v1 §6.1). The test guards the rule. | Passes (d4) |
| `Adapter.TransportLostPresent` | With Cyclone DDS, `transport_lost` has a value | No counter | Passes (d12) |

### Tier 3: driver and camera, `camera_feed_probe`

`camera_feed_probe` is a temporary executable, like `camera_gateway_probe`. It is the phase 1 composition root (ic4). It loads `acquisition_profile.yaml` and takes the parameter `mode`.

| Mode | Steps | Pass condition | Old behavior |
|---|---|---|---|
| `bringup` | The bring-up check in the bring-up section | All five steps pass | `use_ros_time` false and a camera-clock stamp fail it |
| `feed` | Open a feed for 30 s at the profile. Record the rate, the counters, the callback time, and the match time (T12). | 29 to 31 Hz. `discarded_*` all 0. `transport_lost` 0. `queue_evictions` less than 1 % of `frames_delivered`. | No feed exists. The CLI reader showed 30.010 Hz (c3 §3 item 4), which is the reference. |
| `load` | Same as `feed` with `profile.acquisition_frame_rate:=69.71556` for 30 s, then 10 s at 30 Hz | 69 to 70.5 Hz. The camera ends at the 30 Hz profile. | No feed exists. The reference is 69.721 Hz (c1 §3.3). |
| `rtt` | 50 `feature_enum_get PixelFormat` calls while stopped, then 50 while streaming at 69.7 Hz. Report the median and the 95th percentile. | Report only. If the streaming median is more than 5 ms above the stopped median, d5 moves the image subscription to a second node. | Not measured |
| `get_image` | 10 cold calls 2 s apart, then 10 warm calls with a feed open | Each returns a frame. Each `receive_seq` is above the value at the request. Cold times under 2 s. Warm times under 67 ms. | Not possible with the gateway alone |
| `stamps` | Needs the driver with `use_ros_time:=false`. No controller. The gateway starts the stream at 30 Hz, then at 69.7 Hz, 30 s each. A raw subscription with `rclcpp::MessageInfo` records header stamp deltas and source timestamp deltas. | Report only. The two d20 conditions: delta spread within 0.5 period with no loss, and agreement with the driver "frames missing" log under load. | Not measured (d12 item 3, d20 item 6) |

1. The probe prints the RMW name and the two `rmem` values (bring-up host check).
2. The probe restores the 30 Hz profile at the end of each mode that changes it.
3. `[Q]` The `stamps` mode needs load to test the second d20 condition. The probe can add a second subscriber with a slow consumer. The method stays open until the first run.

### Tier 4: short hardware checks

Each check takes less than 5 minutes. An operator runs it.

| Check | Steps | Pass condition | Old behavior |
|---|---|---|---|
| Unplug | 1. Start `camera_feed_probe` with `mode:=feed` and 120 s. 2. After 20 s, pull the PoE cable for 10 s. 3. Plug it in. | `status()` goes to `kOutage` within 400 ms of the last frame. After the reconnect, frames arrive with epoch 2. The feed stays open. | v1 assumed that the driver does not restart the stream (facts A28). With no controller, nothing reports the outage. |
| Wedge | 1. Stop the stream. 2. Write `PixelFormat` `Mono10` with the CLI. 3. Call `stream_start` with the CLI. It fails and leaves `kStarting`. 4. Run `mode:=feed`. 5. Restart the driver. | Step 4 gives `kStreamWedged`. After step 5, `status()` leaves `kWedged`, and a new feed works at Mono8. | The driver stays wedged, and each start returns -15 (facts 1.4.3) |
| Settings load | 1. Start the driver with `settings_file:=/nonexistent.xml`. 2. Change `ExposureTime` with the CLI. 3. Run `mode:=feed`. | The controller corrects `ExposureTime` and streams at 30 Hz | The driver only logs the failed load (`driver:vimbax_camera/src/vimbax_camera_node.cpp:394-399`) |
| Outside reader | Run `ros2 topic hz` with `--qos-reliability reliable` during `mode:=load` | Report `transport_lost`, the driver "frames missing" log, and the probe rate | Not measured. Tests T9. |

The wedge check leaves the driver wedged until step 5. Run it last.

### Coverage of register entries

| Entry | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| d5 | | | `rtt` | |
| d9 | | `QosIsBestEffort` | `load` | Outside reader |
| d10, d13 | `DropOldest`, `Busy` | | | |
| d11, d24 | `SequenceFromOne`, `WarmFreshness` | `SequenceAcrossDiscards` | `get_image` | |
| d12, d20 | `StampBasisDiscards` | `StampBasis` | `bringup`, `stamps` | |
| d17 | `ColdFeedOrder`, `MatchTimeout` | `QosMatches` | `feed` | |
| d18 | `CorrectiveWriteOrder`, `ProfileMismatch` | | `bringup` | Settings load |
| d19 | `Wedge*`, `StartFailReconciled` | | | Wedge |
| d22 | `SilenceToOutage`, `Reconnect*`, `Stall` | | | Unplug |
| d26 | `DeadlinePassed`, `StopOutsideDeadline` | | `get_image` | |
