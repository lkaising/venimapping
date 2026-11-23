## Claude draft notes

The Claude sections follow the register in each place. This file lists where I disagree with the register or where the register is not exact, with evidence. It also lists the interface details that the data-plane section must match.

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption. `[Q]` is an open question.

### Disagreements and gaps in the register

#### N1. d24 and ic8 guarantee 5 promise the first frame, but the queue keeps the newest

1. `[F]` d10 item 3 gives get image capacity 1 with drop oldest. d24 names "the first frame that the fan-out gives to the get image subscription" as the answer.
2. `[F]` The first Mono8 frame arrives about 79 ms before the `stream_start` reply (c1 §3.5 item 2). At 69.7 Hz, about 5 frames arrive in that time, so the first one is evicted before the caller can take it.
3. `[F]` ic3 item 3.1 assigns `receive_seq` before the fan-out lock. A callback can hold a message from before the request and push it after `subscribe` returns. The Codex notes list the same gap.
4. What the control-plane section does: the worker reads `R = frames_received` before `subscribe`. The caller skips each frame with `receive_seq <= R`. The answer is the newest admitted frame in the queue at the take. Each such frame meets R6.
5. Proposed register text for d24: "The answer is a frame that the fan-out pushed to the get image subscription after it opened, with `receive_seq` greater than `frames_received` at the request."

#### N2. d18 item 7 forbids feature writes during a stream, but d18 item 3 needs one after a reconnect

1. `[F]` d18 item 3 writes `TriggerSelector` before it reads `TriggerMode`. d22 item 5 runs that readback after a reconnect, when the driver has already restarted the stream (facts 1.9.7).
2. `[F]` `TriggerSelector` is writable during acquisition (c2 §3.3 item 7).
3. What the control-plane section does: it allows the selector write during a stream and no other write.
4. Proposed register text for d18 item 7: "Phase 1 writes no acquisition value during a stream. The `TriggerSelector` write before a `TriggerMode` read is allowed."

#### N3. ic5 names one layer per code, but two codes come from both layers

1. `kFeedClosed`: the control-plane section returns it from `feed_open` and `get_image` after `shutdown()`. No other code fits "the acquisition stack is closed".
2. `kInvalidArgument`: `AcquisitionController::create` returns it for a bad option, for example a frame rate of 0 in the profile. `feed_open` passes it through from `subscribe`.
3. `kFormatNotStreamable`: `create` also returns it if `allowed_formats` holds a format that is not on the driver gate. This finds a bad profile file at start and not at the first request.
4. ic5 item 1 stays true: the data plane returns only codes 1, 7, 10, and 11. The error-vocabulary section adds rows for the control-plane uses.

#### N4. `feed_open` has no caller deadline

1. `[F]` d26 gives `get_image` a deadline. No entry gives `feed_open` one.
2. `[A]` The cold path makes up to 8 readback calls, 8 writes, 8 more reads, the match wait, a start, and a reconciliation stop. With a 2000 ms gateway timeout and a camera that does not answer, `feed_open` can block for about 50 s.
3. What the control-plane section does: no deadline in phase 1, with this risk stated.
4. Proposal: add `FeedOptions::deadline`, default 5000 ms, with the d26 future mechanism. It returns `kDeadlinePassed`. This is one field and one ic5 row change.

#### N5. The register gives no mechanism for two detections

1. d19 item 5 says "a detected reconnect clears `kWedged`". The register does not say how the worker detects it while it makes no service call for requests.
   - What the control-plane section does: in `kWedged`, the worker polls `connection_status()` every 250 ms. A result other than `true` and then `true` counts as a reconnect or a driver restart.
   - `[A]` A disconnect and a driver restart each last more than 250 ms.
2. d22 item 9 stops a stream that a reconnect restarted with zero users. The worker does not poll while idle.
   - What the control-plane section does: on each tick with no lease, the worker compares `frames_received` with its value at the last tick. A rise means a stream runs with no user, and the worker calls `stream_stop()`.
   - `[F]` The source keeps its subscription for its whole life (d25), so frames reach the callback while admission is closed.

#### N6. ic6 bring-up test 2 is wider than its check

1. ic6 item 3.2 fails "if a topic other than `image_raw` and `camera_info` carries images". `camera_info` subtopics and other driver topics exist under the namespace.
2. `[F]` Each extra image topic from a plugin is a subtopic of `image_raw` (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:142-147`).
3. What the bring-up section does: it fails if a topic name starts with `<namespace>/image_raw/`. This finds each plugin topic and does not depend on a list of message types.

#### N7. The settings file pins more than the profile

1. `[F]` The driver saves and loads the remote device, local device, and stream modules (`driver:vimbax_camera/src/vimbax_camera.cpp:1358-1367`). The file therefore sets every saved feature, not only the eight profile values.
2. `[F]` A failed load only logs an error (`driver:vimbax_camera/src/vimbax_camera_node.cpp:394-399`).
3. I accept d18, because only the file applies values before the driver restart after a reopen (`driver:vimbax_camera/src/vimbax_camera_node.cpp:561-566`). The readback covers the silent load failure.
4. Residual concern: a change outside the profile, for example a stream module value, enters through the XML file with no readback. Review the file diff in each change to `camera_settings.xml`.

#### N8. The controller worker thread start

1. ic4 says the composition root starts the controller worker and the controller shutdown joins it. ic4 also says the worker calls `bind_to_current_thread()` first. The controller is ROS-free and holds only `CameraGateway&`, which has no bind method (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:27-142`).
2. What the control-plane section does: `AcquisitionController::start(WorkerInit)` starts the worker. The worker runs the hook first. The composition root passes a lambda that calls `VimbaXCameraGateway::bind_to_current_thread()`.
3. This meets both ic4 rules with no ROS type in the controller header.

#### N9. Points where I keep a dissent but follow the register

| Entry | Register | My view | Why I follow the register |
|---|---|---|---|
| d10 | Default capacity 1 | Default 2 | R9 gives newer frames priority, and a capacity is a subscribe option. The cost to change is one constant. |
| d22 | 250 ms floor | Was 500 ms | c3 gives a longest interval of 34 ms at 30 Hz (c3 §3 item 4). 250 ms is more than 7 periods. I withdraw this dissent. |
| d5 | One node in phase 1 | Second node from the start | Step 9a measures it and changes only the composition root. |

### Interface details that the data-plane section must match

| Id | Detail | Used by |
|---|---|---|
| M1 | `receive_seq` starts at 1. The callback sets `receive_seq = ++frames_received` in one atomic step. `stats().frames_received` is therefore the sequence of the last message that reached the callback. | Get image freshness (N1), `Fanout.SequenceFromOne` |
| M2 | `stats()` does not wait for a callback that holds the fan-out lock longer than the lock section. The worker calls it every 100 ms. | Silence tick, the no-user check (N5) |
| M3 | `subscribe` is allowed while admission is open and while the executor runs callbacks. | Warm get image, feed open on a running stream |
| M4 | `FrameSubscription::close()` is safe from any thread, also while another thread waits in `take`, and also after the `FrameSource` is gone. | `Feed::close`, controller shutdown |
| M5 | `close_admission()` leaves each subscription open. A later `open_admission()` delivers to the same queues. | Outage and reconnect, the feed stays open (d22) |
| M6 | `matched_publishers()` is safe from the worker while the executor thread spins. | Match wait (d17) |
| M7 | `FrameFanout` takes a clock object named `FrameFanoutClock` with `realtime_ns()` and `steady_now()`. It has public methods `subscribe`, `open_admission`, `close_admission`, `stats`, and `on_message`. `matched_publishers` stays in the adapter. | `FakeFrameSource` |
| M8 | `FrameFanout` and its header are reachable from the test targets through the private include path `src/`. | `FakeFrameSource`, `test_frame_fanout` |
| M9 | `venimapping_camera_frame_api` is installed and exported in the step that adds it, so `venimapping_camera_acquisition` can link it. | Step 5 |
| M10 | String accessors on `ImageFrame` return `const std::string&`. I agree with the Codex note on ic1. | Consumers, tests |
| M11 | `kInvalidArgument` from `subscribe` has a text that names the capacity. `feed_open` passes it unchanged. | Error vocabulary |
| M12 | `VimbaXFrameSource::create` accepts any `rclcpp::Node&`, so step 9a can pass a second node with no adapter change. | Step 9a |

### Camera request

None. The open questions in these sections are the device stamp spread, the gateway time under load, and the match time. The feed probe measures them in steps 8 and 9. A short check cannot measure them, and the register rejected the same stamp request (register, "Camera requests").
