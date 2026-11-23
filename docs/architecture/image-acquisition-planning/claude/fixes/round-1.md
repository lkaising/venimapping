# Round 1 fixes to the Claude sections

Round 1. Checkpoint `d4d786b`. Claude answers the issues i10, i11, and i13 to i27 in task `fix-claude-r1`.

Planning paths are relative to `docs/architecture/image-acquisition-planning/`. Project code citations are `path:line` from the worktree root. `driver:` is from the driver root. `ros:` is from the ROS source root. `vimbax:` is from `/opt/vimbax`.

The fixes use the accepted data-plane fixes for i1 to i9 (`claude/rechecks/round-1.md`). In particular, i26 uses the i3 ownership model, and i22 uses the i9 clock names and the i2 duration fields.

## Summary

| Id | Result | Sections changed |
|---|---|---|
| i10 | Fixed | control-plane, testing |
| i11 | Fixed | control-plane |
| i13 | Fixed | control-plane, testing |
| i14 | Fixed | control-plane, error-vocabulary, testing |
| i15 | Fixed | control-plane, error-vocabulary, testing |
| i16 | Fixed | control-plane, testing |
| i17 | Fixed | control-plane, testing |
| i18 | Fixed | control-plane, error-vocabulary, testing |
| i19 | Fixed | bring-up, testing, implementation-sequence |
| i20 | Fixed | testing, implementation-sequence |
| i21 | Fixed | testing, implementation-sequence |
| i22 | Fixed | testing, source tree |
| i23 | Fixed | error-vocabulary |
| i24 | Fixed | implementation-sequence, source tree |
| i25 | Fixed | bring-up |
| i26 | Fixed | control-plane, testing, source tree |
| i27 | Fixed | control-plane, error-vocabulary, testing |

Result: 17 Fixed, 0 Rejected. Each issue was correct on the evidence.

## i10. Fixed

The reconnect fallback start now goes through the start sequence, and each `open_admission` call has a bit depth.

What changed:

1. Reconnect step 4 keeps the driver restart. It runs the match wait and then calls `open_admission(significant_bits)` with the bit depth of the `PixelFormat` that it read. A failed match keeps the poll state.
2. Reconnect step 6, the fallback, calls `close_admission()` and then runs the full start sequence: readback, confirmed stop before any write, final format check, match wait, a new epoch, and `stream_start`.
3. `Controller.ReconnectNoRestart` now asserts the call order `close_admission`, 8 readback calls, the match wait, `open_admission(8)`, `stream_start`, and epoch 3 on the next frame. `Controller.ReconnectNewEpoch` asserts `open_admission(8)` after the match wait.

Evidence: `[F]` The data plane needs the bit depth on each `open_admission` (`codex/sections/data-plane.md:92`, `:116`). d19 item 5 needs a readback and a match wait before admission resumes after a wedge (`register.md:391`). d22 item 7 gives one start after one more threshold (`register.md:485`).

## i11. Fixed

The section adopts the coordinator proposal for the narrow selector exception.

What changed:

1. "Configuration order and readback" has a new list for the selector write during a stream. It states the amended d18 item 7: "Phase 1 writes no acquisition value during a stream. The `TriggerSelector` write before a `TriggerMode` read is allowed."
2. The list cites the c2 evidence and states why a confirmed stop before each reconnect readback is the wrong choice.
3. Admission stays closed until the reconnect readback matches, so no frame with an unverified profile reaches a queue.

Evidence: `[F]` The driver restarts the stream from its graph thread after a reopen (`driver:vimbax_camera/src/vimbax_camera_node.cpp:556-568`, `:579-593`). `[F]` The camera accepted `TriggerSelector` writes while it streamed (`claude/camera/c2.md:130`). `[F]` Runner `status` calls moved the selector many times during both c2 streams, and `TriggerMode` under `FrameStart` did not change (`claude/camera/c2.md:187`). A stop before each reconnect readback would always discard the restart that d22 item 5 keeps (`register.md:483`).

Register amendment for `integrate-2`: d18 item 7 (`register.md:368`) gets the text above.

## i13. Fixed

Each state now has a rule for new requests, and each corrective write needs a confirmed stop.

What changed:

1. New subsection "Stream states and new requests" with one row per state. `kOutage`, `kConnectionUnknown`, and `kStalled` attach the request with no gateway call. `feed_open` returns the `Feed` at once in an outage. `get_image` waits for a frame until its deadline.
2. The worker keeps a "stop confirmed" fact. A successful `stream_stop` sets it. A `stream_start`, a reconnect, or a rise seen by the no-user check clears it.
3. Start sequence step 2.1 calls `stream_stop()` before the first corrective write if the stop is not confirmed. This applies on each path that writes, also after a reconnect.
4. New state `kFaulted` for a recovery start that failed with leases still open. A new request in `kFaulted` is the retry point.
5. New tests: `Controller.RequestDuringOutage` with a feed open, `Controller.WriteNeedsConfirmedStop`, and `Controller.FaultedRetry`. `Controller.ReconnectProfileChanged` asserts that no write comes before the stop.

Evidence: `[F]` The driver can restart the stream with no project call after a reopen (`driver:vimbax_camera/src/vimbax_camera_node.cpp:561-566`, `:590-593`). d18 item 5 needs a stopped stream before writes (`register.md:366`). d22 item 4 keeps the feed open and polls in an outage (`register.md:482`).

## i14. Fixed

Each request now has one absolute deadline and one shared outcome. The worker checks both before each stage.

What changed:

1. New subsection "Requests and deadlines". The request state has `deadline` and `outcome` (`kPending`, `kDelivered`, `kAbandoned`). Only one transition leaves `kPending`, and the side that makes it owns the cleanup.
2. The worker checks at dequeue, before each readback, before the writes, before each 10 ms match poll, before `open_admission`, and before `stream_start`.
3. If the caller left, the worker destroys the `Feed` that it built. The destructor closes the subscription and posts the lease release. After delivery, the caller owns both.
4. The `take` result decides a late frame. A frame that `take` returns is the answer. A recheck after `take` would discard a valid frame and change no deadline bound.
5. New tests `Controller.ExpiredInQueue` and `Controller.ExpiredDuringMatch`.
6. The error-vocabulary section has a "Deadline stages" table.

Evidence: `[F]` The gateway sets one deadline per call and removes the pending request at that deadline (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:187-201`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:79-94`). A started call therefore runs to its own timeout, and the request check points are the only place to stop. d26 items 1 and 5 give one steady deadline and a worker that finishes a pending call (`register.md:543-547`).

## i15. Fixed

The section now gives a result for each lifecycle point and a shutdown that runs on the worker.

What changed:

1. New subsection "Lifecycle and shutdown" with a table for requests before `start`, after an init failure, during shutdown, and after shutdown.
2. Before `start`, requests wait in the queue with their deadline. After an init failure, the worker completes each queued request with `kFeedClosed`, and `start` joins the worker and returns the init error.
3. `shutdown()` sets a flag, wakes the worker, and joins it. The worker makes each gateway call of the shutdown, because only the bound thread may call the gateway. The draft had the shutdown thread call `stream_stop()`, which breaks the gateway thread rule.
4. The destructor runs `shutdown()`. A `shutdown()` call on the worker thread, which can only come from `WorkerInit`, sets the flag and returns with no join.
5. New tests: `QueuedBeforeStart`, `InitFailure`, `ShutdownFromInit`, and `DestroyWithPendingRequest`. `Controller.Shutdown` also wakes a waiting `get_image` and checks that each call is on the worker thread.

Evidence: `[F]` Gateway calls must come from the bound thread (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-47`, `:63-64`). ic4 stop order step 1 makes the controller shutdown close each feed, stop the stream, and join the worker (`register.md:783`). ic2 rules 3 and 7 need a waiting `take` to return `kFeedClosed` (`register.md:707`, `:711`).

## i16. Fixed

The final readback now decides the format check and the bit depth, and each feature call names its module.

What changed:

1. Start sequence step 3 defines the final readback: the second one if writes ran, else the first. Steps 4 and 7 use the final `PixelFormat`.
2. The readback table and the write list pass `FeatureModule::kRemoteDevice` on each call. "Inputs from the code" item 2 states the argument.
3. `FakeCameraGateway` fails the test on any other module. New tests `Controller.RemoteDeviceModule` and `Controller.FormatCorrectionBits`. The second test corrects Mono12 to Mono8 and checks `significant_bits` 8 on the first frame.

Evidence: `[F]` Each feature call takes a `FeatureModule` (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:59-110`). The camera features are under `kRemoteDevice` (`src/venimapping_camera/include/venimapping_camera/types/feature_module.hpp:15-21`). d18 item 6 makes the second readback decide (`register.md:367`).

## i17. Fixed

A failed start now closes admission at once, and each failed start or stop goes through d19.

What changed:

1. Start sequence step 9 calls `close_admission()` before the failure recovery. It clears each queue, so a feed that stays open gets no frame from the failed epoch.
2. Failure recovery item 1 lists each path that uses it: the start sequence, the last release, the no-user stop, the stall cycle, the reconnect paths, and the wedge confirmation stop.
3. Corrective writes need a confirmed stop (see i13). After a failed start, the d19 reconciliation stop gives that confirmed stop before the next start.
4. New tests `Controller.StartFailClearsQueue` and `Controller.NoUserStopFails`. The first injects a frame inside the failing `stream_start` and checks the empty queue and the `frames_cleared` rise.

Evidence: `[F]` The driver starts its frame processing thread before `CaptureStart` and `AcquisitionStart`, which can still fail (`driver:vimbax_camera/src/vimbax_camera.cpp:458-510`). `[F]` `close_admission` clears each queue and counts `frames_cleared` (`codex/sections/data-plane.md:116`). d19 item 2 covers each failed start or stop (`register.md:388`).

## i18. Fixed

The first error and the reconciliation result are now separate, and a poll error alone never clears `kWedged`.

What changed:

1. `ControllerStatus` has `last_error` for the first error and `last_reconciliation` for the reconciliation stop error.
2. With a successful reconciliation stop, the caller gets the first error. With a failed one, the caller gets `kStreamWedged`, and its text names both errors.
3. The error table now states that -15 reaches a caller only with a successful reconciliation stop. The driver is then stopped, so a retry is safe.
4. In `kWedged`, a change signal is a poll result other than `true`, followed by `true`. At a change signal, the worker makes one confirmation `stream_stop()`. Only a successful stop clears `kWedged`. A -15 keeps it.
5. New tests `Controller.FirstErrorMinus15` and `Controller.WedgePollErrorKeepsWedge`. `Controller.WedgeCleared` now expects the confirmation stop.

Evidence: `[F]` A start or stop in `kStarting` or `kStopping` returns -15, and no service resets that state (`driver:vimbax_camera/src/vimbax_camera.cpp:516-519`, `:582-585`). `[F]` A new camera object starts in `kStopped` (`driver:vimbax_camera/include/vimbax_camera/vimbax_camera.hpp:317`), so a reopen can accept the later stop. `[F]` The `connected` service reports only `camera_ != nullptr` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1520-1527`). `[F]` A gateway timeout can happen on a live driver (`src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:85-93`). The stop result is the only direct evidence of the driver stream state.

## i19. Fixed

The rig check now proves that the installed values applied.

What changed:

1. New part A in the bring-up rig check: write `ExposureTime` 10000.0 and `AcquisitionFrameRate` 20.0, restart the driver, and fail on a `Loading settings from file` log line.
2. Part B reads `settings_file` and checks the installed path and the file. It reads the live `image_raw.enable_pub_plugins` value. It requires one publisher on `image_raw`. It reads back the profile with no corrective write. It bounds the first-frame wait at 2000 ms.
3. The N6 prefix rule for plugin topics stays as step 5.
4. The step 1 exit check uses the same checks through the CLI, because the probe comes in step 8. The step 8 exit check runs part A and then `mode:=bringup`.

Evidence: `[F]` A failed load only logs an error (`driver:vimbax_camera/src/vimbax_camera_node.cpp:390-400`). `[F]` `image_transport` declares the plugin filter on the driver node with all plugins as the default (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:127-128`). A readback after a reopen from known different values fails if the load did not apply. A check of values that already match cannot see that.

## i20. Fixed

Step 9 now restores host stamps before the wedge check, and the wedge check keeps one controller across the restart.

What changed:

1. Tier 4 has an order column. Check 3 runs the stamp run with `use_ros_time:=false`. Check 4 relaunches the driver with the default arguments and reads `use_ros_time` as `True`. The wedge check is check 5.
2. The wedge check writes `PixelFormat` `Mono8` with the CLI while the driver stays wedged and reads it back. If the read is not `Mono8`, the check stops, and the tier 1 scripted gateway tests are the evidence.
3. New probe mode `wedge` keeps one controller alive. It retries `feed_open` every 2 s across the driver restart.
4. Implementation step 9 lists the same order.

Evidence: `[F]` The format refusal returns before `CaptureStart` (`driver:vimbax_camera/src/vimbax_camera.cpp:427-431`, `:484`). `[F]` The driver feature setter does not check the stream state (`driver:vimbax_camera/src/vimbax_camera.cpp:964-976`). `[F]` With device stamps, the data plane discards each frame for stamp basis (`codex/sections/data-plane.md:127`). Without the Mono8 write, the controller would correct the format by a write and hide the wedge order.

## i21. Fixed

The outside reader now uses a RELIABLE reader that exists, and the stamp run has gap rules.

What changed:

1. The outside reader is `ros2 topic echo --qos-reliability reliable --qos-depth 10 --field header.stamp`. It is a separate process and a slow reader.
2. The `stamps` mode makes a RELIABLE, KEEP_LAST 10 reader with `MessageInfo` and waits for a match for at most 1000 ms before the start.
3. New gap rules match each device gap with a driver `N frames missing` line by size and by time, within 50 ms before the `source_timestamp` of the frame after the gap. An unmatched device gap is a reader gap.
4. Condition 2 is inconclusive if the 69.7 Hz run has no driver gap, or if a reader gap occurs.

Evidence: `[F]` Jazzy `ros2 topic hz` has only `--window`, `--filter`, and `--wall-time` (`ros:ros2/ros2cli/ros2topic/ros2topic/verb/hz.py:64-83`). `[F]` `ros2 topic echo` adds the QoS arguments (`ros:ros2/ros2cli/ros2topic/ros2topic/verb/echo.py:60`, `ros:ros2/ros2cli/ros2topic/ros2topic/api/__init__.py:223-256`). `[F]` The driver logs the SDK frame id gap before it publishes (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1603`). `[F]` The default console line has a wall-clock time (`ros:ros2/rcutils/src/logging.c:89`).

## i22. Fixed

The tests now have a hold point, an address check, a fake stamp rule, and named timer endpoints.

What changed:

1. New `TestClock`. `steady_now()` reads the real steady clock and can hold one call on one thread. `realtime_ns()` is manual. The hold point is the first `steady_now()` read in `on_message`, which is between sequence assignment and the fan-out lock.
2. `Controller.InFlightFrameSkipped` and the new `Fanout.InFlightPushAfterLink` use the hold. `FakeFrameSource` gives `subscriptions_opened()` and `subscription_stats(i)`, so the test can see that the held frame reached the get image queue.
3. `FakeFrameSource::inject` with no stamp advances the realtime value by 1 ms before it stamps the frame. The stamp is then strictly greater than each earlier boundary.
4. `Adapter.NoPixelCopy` uses intra-process communication and compares `frame.pixels().data()` with the address of the published buffer.
5. The match time starts when `VimbaXFrameSource::create` returns and ends at the first 10 ms poll with a match. The callback time uses `callback_ns_max` and `callback_ns_total`. A test that checks the duration does not use the hold.

Evidence: `[F]` `on_message` assigns the sequence, then reads `steady_now()`, then takes the lock (`codex/sections/data-plane.md:124-128`). `[F]` The data plane names `FrameFanoutClock` and the duration fields (`codex/sections/data-plane.md:68-69`, `:118`). `[F]` rclcpp intra-process gives a published `unique_ptr` to const subscriptions with no copy when no subscription needs ownership (`ros:ros2/rclcpp/rclcpp/include/rclcpp/experimental/intra_process_manager.hpp:243-248`). The controller compares `last_admitted` with its own steady clock, so `TestClock` must read the real steady clock.

## i23. Fixed

The error vocabulary rows now match the behavior.

What changed:

1. `kDeadlinePassed` covers `feed_open` and `get_image`. A new "Deadline stages" table defines the code for the queue, the readback and writes, the match wait, `stream_start`, and the frame wait.
2. A new list states how the second readback decides the corrective write result. A write error does not pass through. It goes to `status().last_error`, and a remaining difference names it in the `kFormatNotStreamable` or `kProfileMismatch` text.
3. The `transport_lost` row now says "the total count of the RMW `message_lost` event". A new fact states that a history overwrite of an unread sample does not raise it.

Evidence: `[F]` Cyclone DDS fills the event from `dds_get_sample_lost_status` (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3943-3955`). `[F]` A full reader history replaces the oldest sample with no sample lost status (`ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`). `[F]` A setter that times out can still apply (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:24-26`).

## i24. Fixed

Step 5 now installs and exports the acquisition target, and a new section gives the CMake join rule.

What changed:

1. New "CMake layout" in the implementation sequence. Each library block has its own `install(TARGETS <target> EXPORT export_${PROJECT_NAME} ...)` call. The shared install call and `ament_export_targets` do not change.
2. Step 5 installs and exports `venimapping_camera_acquisition`. Its exit check 4 builds `test/installed_consumer`, a separate project that links `venimapping_camera::venimapping_camera_acquisition`.
3. Steps 4 and 5 each add one labeled block. The step that merges second rebases, and the only conflict is the insertion point.
4. The source tree lists the two installed-consumer files.

Evidence: `[F]` The package installs and exports only the targets that its `install(TARGETS ...)` call names (`src/venimapping_camera/CMakeLists.txt:65-74`). CMake accepts several `install(TARGETS ... EXPORT)` calls with one export set, so each step can add its own call.

## i25. Fixed

The bring-up section now states the settings file scope and the limit of the readback.

What changed:

1. The section states the persistence type `VmbFeaturePersistNoLUT`, the module flags `RemoteDevice | LocalDevice | Streams`, and the 10 load iterations.
2. It states that the file holds no system or interface feature. `[A]` The SDK saves each readable feature of the three modules. Review the saved file for its content.
3. It describes the readback as a check of the seven listed values and the selector write only.
4. The rig check uses the driver load result: part A fails on the `Loading settings from file` log line.

Evidence: `[F]` The driver uses one persist setting for save and load (`driver:vimbax_camera/src/vimbax_camera.cpp:1358-1367`). `[F]` `VmbFeaturePersistNoLUT` saves all features except look-up tables (`vimbax:api/include/VmbC/VmbCTypeDefinitions.h:473-475`). `[F]` The load loops through the file up to `maxIterations` times (`vimbax:doc/VimbaX_Documentation/cAPIManual.html:1470-1479`).

## i26. Fixed

The section keeps the ic2 rule. `Feed` owns its subscription alone, and the worker closes it through a shared link.

What changed:

1. The shared ownership claim is gone. `Feed` holds `std::unique_ptr<FrameSubscription>` and `std::shared_ptr<detail::LeaseLink>`.
2. `LeaseLink` holds a mutex, a non-owning subscription pointer, and the shared request queue. `Feed::close()` closes the subscription and sets the pointer to null under the mutex. Shutdown closes each subscription whose pointer is not null under the same mutex.
3. The get image path uses the same `Feed` type inside the controller. Each lease has one owner at a time.
4. A release posted after the controller is gone goes to a closed queue and does nothing.
5. New test `Controller.FeedDestroyDuringShutdown`. `Controller.FeedOutlivesController` stays.

Evidence: `[F]` ic2 `Feed` item 1 gives `Feed` one `std::unique_ptr<FrameSubscription>` (`register.md:741`). `[F]` After the i3 fix, `close()` is idempotent and safe from any thread, also after the source is gone (`codex/sections/data-plane.md:104-106`). ic2 needs no change.

## i27. Fixed

The section adopts the N4 proposal.

What changed:

1. `FeedOptions::deadline`, default 5000 ms. `feed_open` uses the same request state and check points as `get_image` (i14).
2. The `kDeadlinePassed` row names `feed_open`. The "Deadline stages" table covers both calls.
3. New test `Controller.FeedOpenDeadline`.

Evidence: `[A]` The in-process cold path is less than 500 ms at a few milliseconds per call. Without a deadline, about 25 gateway calls at a 2000 ms timeout give about 50 s (`claude/draft-notes.md` N4). d26 covers only `get_image` (`register.md:543`).

## Register text that these fixes need

These amendments make the register match the fixed sections. `integrate-2` owns them.

1. d18 item 7 (`register.md:368`): the i11 text.
2. d19 item 5 (`register.md:391`): a change signal and then a successful confirmation `stream_stop` clear `kWedged`. A poll error alone does not (i18).
3. d22 item 7 (`register.md:485`): the fallback calls `close_admission` and runs the start sequence (i10).
4. d22 item 5 (`register.md:483`): the stop before the writes is part of the start sequence and makes a confirmed stop (i13).
5. d26 (`register.md:543-548`): add `FeedOptions::deadline`, default 5000 ms, with the same mechanism (i27). Item 2 also covers the queue wait (i14).
6. ic2 `Feed` (`register.md:739-743`): add the `LeaseLink` close path. Sole ownership does not change (i26).
7. ic3 item 4.3 (`register.md:759`): add `close_admission` after a failed `stream_start` (i17).
8. ic4 stop order step 1 (`register.md:783`): the worker makes each gateway call of the shutdown (i15).
9. ic5 (`register.md:791-808`): `kDeadlinePassed` adds `feed_open`. `kFeedClosed` adds the init failure and requests queued at shutdown. `kInvalidArgument` adds a second `start` call. Item 2 adds the corrective write rule (i23).
10. ic6 item 3 (`register.md:825-828`): the bring-up tests add part A, the `settings_file` read, the filter read, the publisher count, and the 2000 ms first-frame limit (i19).
