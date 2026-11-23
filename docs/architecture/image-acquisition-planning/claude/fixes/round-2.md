# Round 2 fixes to the Claude sections

Round 2. Checkpoint `f06a589`. Claude answers the issues i14, i15, i17, i18, i19, i21, i22, i25, i26, and i31 in task `fix-claude-r2`.

Planning paths are relative to `docs/architecture/image-acquisition-planning/`. Line numbers in `claude/sections/` and `claude/source-tree.md` are in the new files of this task. Line numbers in `codex/` and `register.md` are at the checkpoint. Project code citations are `path:line` from the worktree root. `driver:` is from the driver root. `ros:` is from the ROS source root.

## Summary

| Id | Result | Sections changed |
|---|---|---|
| i14 | Fixed | control-plane, error-vocabulary, testing, implementation-sequence |
| i15 | Fixed | control-plane, error-vocabulary, testing, implementation-sequence |
| i17 | Fixed | control-plane, error-vocabulary, testing, implementation-sequence |
| i18 | Fixed | control-plane, error-vocabulary, testing, implementation-sequence |
| i19 | Fixed | bring-up, testing, implementation-sequence |
| i21 | Fixed | testing, implementation-sequence |
| i22 | Fixed | testing, source tree |
| i25 | Fixed | bring-up |
| i26 | Fixed | control-plane, testing, implementation-sequence, source tree |
| i31 | Fixed | testing, implementation-sequence |

Result: 10 Fixed, 0 Rejected. Each issue was correct on the evidence. For i14 item 2, the fix adopts the recheck rule, so no dispute is needed.

## i14. Fixed

The worker now checks before each gateway call of a request. The caller checks the deadline when it accepts a frame.

What changed:

1. Item 1. The check points now include each of the 8 readback calls, each corrective write, the confirmed stop of start step 2.1, `stream_start`, each match poll, and `open_admission` (`claude/sections/control-plane.md:148-154`). The readback and write lists state the same rule (`claude/sections/control-plane.md:324-371`, list items "For a request" and "A request that expires between two writes").
2. Item 1. A check point reads the outcome and the steady clock under the outcome mutex. The delivery transition uses the same locked section, so the worker never delivers after the deadline (`claude/sections/control-plane.md:148`, `:154`).
3. Item 3. "When a check point stops a request" states that an expiry after `open_admission` and before `stream_start` makes the worker call `close_admission()` at once. The epoch number is used up. Then the `Feed` is destroyed and the release rules run (`claude/sections/control-plane.md:156-161`).
4. Item 2. The take loop checks the deadline before each `take` and again after each frame. A frame that `take` returns after the deadline gives `kDeadlinePassed` (`claude/sections/control-plane.md:386-399`). The round 1 sentence "A frame that `take` returns is the answer" is gone.
5. Inputs 11 and 12 state why the check is at acceptance: `take` returns a queued frame at once, and a frame has no steady receipt time (`claude/sections/control-plane.md:19-20`).
6. The error-vocabulary "Deadline stages" table has rows for the expiry before `stream_start`, for delivery, and for frame acceptance. Note 1 states the acceptance rule.
7. New tests `Controller.ExpiredDuringReadback`, `Controller.ExpiredBeforeStart`, and `Controller.FrameAfterDeadlineRejected` (`claude/sections/testing.md:173-174`, `:197-207`). `FakeFrameSource` gets `on_open_admission` and the take hold for these tests.

Evidence:

1. `[F]` The gateway sets one deadline for each call and cannot cancel it (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:187-201`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:79-94`). With a check only before each whole readback, an expired request runs up to 7 more calls, each up to its own timeout. A check before each call frees the worker within one gateway timeout after the deadline.
2. `[F]` A timeout of 0 or less acts as `try_take` (`codex/sections/data-plane.md:100`). So the round 1 loop could return a frame that entered the queue after the deadline.
3. `[F]` d26 item 4 reads "A passed deadline returns `kDeadlinePassed`" (`register.md:546`). The round 1 rule did not meet it in the case of item 2.
4. `[F]` `ImageFrame` has no steady receipt time (`codex/sections/data-plane.md:15-26`). The caller therefore cannot accept a frame "that arrived before the deadline". The acceptance time is the only exact check.
5. The cost of the new rule is one dropped frame in the wake-up window of the caller thread. A warm retry gets a frame in about 33 ms (d28). The round 1 argument that a recheck "would discard a valid frame" is true, but that frame is not worth a contract exception.

## i15. Fixed

Shutdown before `start` now completes the queue on the calling thread, and one rule decides which thread joins.

What changed:

1. New lifecycle value `kCreated`, `kStarting`, `kRunning`, `kStopping`, `kStopped` under one lifecycle mutex. The mutex also guards the shutdown flag and the `std::thread` object (`claude/sections/control-plane.md:171`).
2. Shutdown in `kCreated` sets `kStopped`, closes the request queue, and completes each queued request with `kFeedClosed` on the calling thread. No gateway call runs. No queued request holds a `Feed` or a lease, because only the worker calls `subscribe` (`claude/sections/control-plane.md:192-198`, item 2).
3. Join rule: only the thread that moves the `std::thread` object out under the lifecycle mutex joins. Other `shutdown()` callers wait for `kStopped` (`claude/sections/control-plane.md:182`).
4. `start` returns `kInvalidArgument` in `kStarting` or `kRunning`, and `kFeedClosed` in `kStopping` or `kStopped`. If shutdown begins during `init`, `start` returns `kFeedClosed` (`claude/sections/control-plane.md:184-190`).
5. After an init failure, the worker makes no gateway call, because the gateway is not bound.
6. The error-vocabulary rows for `kFeedClosed` add `start` and shutdown before `start`. The `kInvalidArgument` row names a second `start` while the worker starts or runs.
7. New tests `Controller.ShutdownBeforeStart` and `Controller.StartShutdownOverlap` (`claude/sections/testing.md:258-259`).

Evidence:

1. `[F]` The round 1 table let requests wait in the queue before `start`, and only the worker completed the queue (checkpoint `claude/sections/control-plane.md:159`, `:171-177`). With no worker, a caller waited until its deadline.
2. `[F]` Gateway calls must come from the bound thread (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-47`, `:63-64`). The shutdown path before `start` makes no gateway call, so it can run on the calling thread.
3. `std::thread::join` on a thread that is not joinable throws `std::system_error`. In the `noexcept` `shutdown()`, that ends the process. One owner of the thread object removes the case.

## i17. Fixed

The section now defines what an open feed sees from an epoch whose start is pending, and it drops the false promise.

What changed:

1. The sentence "a feed that stays open never gets a frame from a failed epoch" is gone.
2. New subsection "Frames from an epoch whose start is pending" (`claude/sections/control-plane.md:305-322`). A consumer can take frames of epoch E before the start result. Each such frame passed the final readback and the format check for E. If the start fails, `close_admission()` removes the frames that the consumer did not take, and no later frame carries E.
3. The rule for get image: a request that caused the start gets no frame of a failed epoch, because the worker delivers its `Feed` only after `stream_start` succeeds. A get image that attached in an outage or a stall follows the feed rule.
4. The subsection states why admission stays open before `stream_start`.
5. The error-vocabulary table "Results that are not errors" has a row for a frame of an epoch whose start failed later.
6. New test `Controller.ConsumerDuringFailingStart`. The take hook proves that the consumer took F before `stream_start` returned -1 (`claude/sections/testing.md:225-234`).

Evidence:

1. `[F]` The first frame arrives about 79 ms before the `stream_start` reply (c1 §3.5 item 2). `take` returns a queued frame at once (`codex/sections/data-plane.md:100`). So the round 1 promise was false.
2. `[F]` Admission after the reply loses 3 to 5 frames of each cold start (c1 §3.5 item 3). A held state until the reply needs a new data-plane state.
3. `[F]` A frame exists only if the camera acquired it. The driver runs frame processing before the acquisition command (`driver:vimbax_camera/src/vimbax_camera.cpp:458-510`). A frame of a failed start is therefore a real image at the verified profile.
4. `[F]` `open_admission` increments the epoch (`register.md:747`). So no frame after the failure carries the failed epoch.

## i18. Fixed

The confirmation stop is now one stop for each change signal, outside the failure recovery.

What changed:

1. Failure recovery item 1 no longer lists the confirmation stop. It states that the confirmation stop has its own rule (`claude/sections/control-plane.md:437`).
2. `kWedged` item 6: at each change signal, the worker makes exactly one confirmation `stream_stop()`. It causes no reconciliation stop, no outage state, and no second stop (`claude/sections/control-plane.md:454`).
3. `kWedged` item 8: any failure keeps `kWedged`. This covers -15, -3, another driver error, a gateway error, and a timeout. The error goes to `last_reconciliation`, and `last_error` keeps the cause of the wedge (`claude/sections/control-plane.md:456`).
4. Error-vocabulary item 5 under "Errors that pass through the controller": a confirmation stop error never reaches a caller.
5. `Controller.WedgePollErrorKeepsWedge` asserts exactly one `stream_stop` after the change signal and a continued poll. New test `Controller.WedgeConfirmMinus3` asserts that a -3 keeps `kWedged`, not `kOutage` (`claude/sections/testing.md:222-223`).

Evidence: `[F]` The checkpoint text sent the confirmation stop through recovery items 2 and 3, which give `kOutage` on -3 and another stop on other errors (checkpoint `claude/sections/control-plane.md:369-373`). The wedge rule kept `kWedged` (checkpoint `:388`). `[F]` The `connected` service reports only `camera_ != nullptr` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1520-1527`). A -3 at the confirmation stop is not evidence that the wedge cleared, so `kWedged` stays.

## i19. Fixed

Part A now reads back its writes before the reopen, and each log check matches the message anywhere in the line.

What changed:

1. Part A steps 8 and 9 read back `ExposureTime` and `AcquisitionFrameRate` with the CLI before the driver stops. A difference of more than 0.001 stops the check (`claude/sections/bring-up.md:184-198`).
2. Part A steps 1 to 3 are a control launch with `settings_file:=/nonexistent.xml`. The same `grep` must find the failed-load line. This proves that the check can fail.
3. Each log check is `grep -F 'Loading settings from file' <file>`, which matches anywhere in the line. Step 12 checks both `driver_a.log` and `driver_b.log`.
4. New list "The failed-load line" gives the message, the two prefixes, and the stderr route (`claude/sections/bring-up.md:95-100`). "What exists today" item 6 states the launch `output` default.
5. Implementation step 1 exit check 3 uses part A steps 1 to 13 and the same `grep` (`claude/sections/implementation-sequence.md:64`). Tier 4 check 2 uses the same `grep` (`claude/sections/testing.md:348`).

Evidence:

1. `[F]` The driver logs `Loading settings from file %s failed with error %d (%s)` through `RCLCPP_ERROR` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:395-398`). A search of the driver source finds that text at this one place only, so the `grep` cannot match a success line.
2. `[F]` The default console format is `[{severity}] [{time}] [{name}]: {message}` (`ros:ros2/rcutils/src/logging.c:88-89`). Console output goes to stderr by default (`ros:ros2/rcutils/src/logging.c:659-670`).
3. `[F]` With the default `output` of `log`, `launch` sends stderr to the screen (`ros:ros2/launch/launch/launch/actions/execute_process.py:217-219`). It puts `[<process name>] ` before each line (`ros:ros2/launch/launch/launch/actions/execute_local.py:91`). The project launch `Node` sets no `output` (`src/venimapping_bringup/launch/camera.launch.py:35-41`).
4. So no console line starts with the message, and the round 1 check could not fail. A readback before the reopen makes sure that part B step 6 fails if the file did not apply.

## i21. Fixed

The gap rules now use one source-time interval for each rate, and each line belongs to at most one pair.

What changed:

1. New list "Facts for the gap rules" (`claude/sections/testing.md:313-318`).
2. The probe records each message from the `stream_start` request until 1 s after the `stream_stop` reply.
3. For each rate, the interval I runs from the first to the last `source_timestamp` that the probe received. Driver gap lines count if their log time is in I. Stamp pairs are in I by definition (`claude/sections/testing.md:320-329`).
4. A line belongs to the pair whose interval from `a.source_timestamp` to `b.source_timestamp` holds its log time. Pair intervals touch only at end points, so each line matches at most one gap.
5. Gap rule 9 lists the ambiguous cases: a line on a shared end point, more than one line in a pair, a size that differs, and a line in the run but outside I. An ambiguous item makes the condition inconclusive.
6. Implementation step 9 records an ambiguous result as inconclusive, with the item that caused it.

Evidence:

1. `[F]` The driver logs the gap in the callback of the frame after the gap, before it publishes that frame (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1603`, `:1631`). The line time is therefore between the source timestamps of the two messages of the pair.
2. `[F]` `stream_stop` clears the last frame id (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1659`), so no line spans two runs.
3. `[F]` The console time comes from `rcutils_system_time_now` (`ros:ros2/rcutils/src/logging.c:1205`), which is `CLOCK_REALTIME`. `[A]` The DDS `source_timestamp` is `CLOCK_REALTIME` at the write on the same host. Gap fact 4 makes the run inconclusive if the two clocks do not agree.
4. `[F]` The round 1 rule counted lines only after the start reply, but the first frame comes about 79 ms before the reply (c1 §3.5 item 2). The new interval starts at the first message.

## i22. Fixed

The test now waits for proof that the caller took and skipped N before it injects N+1.

What changed:

1. The `FakeFrameSource` subscription decorator counts each `take` call and records the `receive_seq` of each frame that it returned. `wait_for_take_calls(i, n, limit)` waits with a time limit (`claude/sections/testing.md:96-100`).
2. `Controller.InFlightFrameSkipped` waits for a second `take` call on the get image subscription, with a 1000 ms limit, and checks `taken_seqs(1) == {N}`. Only then does it inject N+1 (`claude/sections/testing.md:184-195`).
3. With the skip removed, the caller returns N and makes no second call, so the wait fails.
4. The source tree describes the new decorator hooks.

Evidence: `[F]` The get image queue has capacity 1 and drops the oldest frame (`codex/sections/data-plane.md:98`). With the round 1 order, N+1 could evict N before the first `take`, and the test passed with no skip. The second `take` starts only after the caller handled N, so N+1 cannot reach the queue before that point.

## i25. Fixed

The bring-up section applies the i19 log check fix to the settings file scope.

What changed:

1. "Camera settings file" item 6 no longer says that the line starts with `Loading settings from file`. The new list "The failed-load line" replaces it (`claude/sections/bring-up.md:95-100`).
2. The rig check uses the failed-load line through the control launch and the `grep` that matches anywhere in the line. This makes the driver load result a check that can fail.

Evidence: the i19 evidence.

## i26. Fixed

Each lease now releases once, and a move assignment closes the destination first.

What changed:

1. `LeaseLink` has a `released` flag. `Feed::close()` sets it under the link mutex and posts a release only if it was false (`claude/sections/control-plane.md:213-241`, rules 2 and 3).
2. The link is the lease identity. The worker keeps a set of links and removes a link once. A release whose link is not in the set does nothing, so one lease can never remove another (rule 4).
3. Move assignment from itself does nothing. Otherwise it runs `close()` on the destination, destroys its subscription, and then takes the source pointers (rule 7).
4. An empty `Feed` returns `kFeedClosed` from `take` and `try_take` (rule 8).
5. Shutdown sets the pointer to null but not `released`, so the later `Feed::close()` posts its release to the closed queue (rule 9).
6. New tests `Controller.FeedCloseThenDestroy` and `Controller.FeedMoveAssignIntoLive` (`claude/sections/testing.md:265-266`).

Evidence: `[F]` The round 1 `close()` posted a release on each call, and the destructor called it again (checkpoint `claude/sections/control-plane.md:198-199`). `[F]` Rule 4 covered only a move construction, and the move assignment operator replaced a live `unique_ptr` (checkpoint `:69`, `:201`). `[F]` `FrameSubscription::close()` is idempotent (`codex/sections/data-plane.md:104`), so a close through the link and a later `Feed::close()` are safe.

## i31. Fixed

Each step 5 test now uses `feed_open` only. The tests that need `get_image` move to step 6.

What changed:

1. The controller test tables have a step column (`claude/sections/testing.md:146`).
2. `QueuedBeforeStart`, `InitFailure`, `Shutdown`, and `DestroyWithPendingRequest` now use `feed_open` and stay in step 5.
3. The get image part of `Controller.Shutdown` moves to the new step 6 test `Controller.ShutdownWakesGetImage`.
4. The new tests follow the same rule. `ExpiredDuringReadback`, `ExpiredBeforeStart`, `ShutdownBeforeStart`, `StartShutdownOverlap`, and `FeedMoveAssignIntoLive` are step 5. `FrameAfterDeadlineRejected` and `FeedCloseThenDestroy` are step 6. `ConsumerDuringFailingStart` and `WedgeConfirmMinus3` are step 7.
5. The implementation sequence states the rule in "Order and dependencies" item 4. It lists the step 5 cases in four groups (`claude/sections/implementation-sequence.md:27`, `:149`, `:170`, `:182`).

Evidence: `[F]` The step 5 header has no `get_image` (checkpoint `claude/sections/implementation-sequence.md:142`). `[F]` The four round 1 tests called `get_image` (checkpoint `claude/sections/testing.md:197-201`). The new step 5 forms call only `feed_open`, `start`, `shutdown`, and the `Feed` methods.

## Register text that these fixes need

These amendments make the register match the fixed sections. `integrate-3` owns them.

1. d26 item 2: the deadline also covers the acceptance of the first frame. The worker checks the outcome and the deadline before each gateway call that the request causes (i14).
2. d26 item 4: "A passed deadline returns `kDeadlinePassed`. The caller checks the deadline after each frame that `take` returns, and drops a frame that it took after the deadline." (i14)
3. d26: `FeedOptions::deadline` adds the queue wait part that i33 item 4 left open (i14, i27).
4. d19 item 5: "A change signal and then a successful confirmation `stream_stop` clear `kWedged`. The worker makes one confirmation stop for each change signal. Any failure of it keeps `kWedged`." (i18, replaces the waiting fix-claude-r1 item 2)
5. ic2 `Feed`: add the `LeaseLink` with the `released` flag, the lease set by link, the move assignment rule, and `kFeedClosed` from an empty `Feed`. Sole ownership does not change (i26, replaces the waiting fix-claude-r1 item 6).
6. ic3 item 4.3: add `close_admission` when a request expires after `open_admission` and before `stream_start` (i14).
7. ic3: add the rule for frames of an epoch whose start is pending, from `claude/sections/control-plane.md:305-322` (i17).
8. ic4 stop order step 1: add shutdown before `start`, which completes the queue on the calling thread with no gateway call, and the join rule (i15).
9. ic5: `kFeedClosed` adds `start` after shutdown started and shutdown before `start`. `kInvalidArgument` names a second `start` while the worker starts or runs (i15).
10. ic6 item 3: the bring-up tests add the part A control launch, the readback before the reopen, and the `grep -F` match anywhere in the line (i19, i25, replaces the waiting fix-claude-r1 item 10).
