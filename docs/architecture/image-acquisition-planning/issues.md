# Issues for the image acquisition design

Round 1. Checkpoint `8d2c760`. The coordinator wrote this file in task `integrate-1`.

## How to read this file

1. Each issue has an id, `i1` to `i30`. An id is never reused.
2. Status values:
   - Open. The owner must fix the section or reject the issue with evidence. The other planner rechecks.
   - Closed. Both planners agree, or the evidence settles the issue.
   - For Logan. Only a decision from Logan can settle the issue.
3. Severity values come from the reviews: Blocking, Major, and Minor.
4. Sources:
   - `r-claude-N` is finding N in `claude/review-of-codex.md`.
   - `r-codex-N` is finding N in `codex/review-of-claude.md`.
   - "mismatch N" is item N in the interface mismatch list of the named review.
   - `N1` to `N9` are entries in `claude/draft-notes.md`. "Codex note" is an entry in `codex/draft-notes.md`.
   - "Verdicts" are the two files `claude/disputes/d20-verdict.md` and `codex/disputes/d20-verdict.md`.
5. Paths are relative to `docs/architecture/image-acquisition-planning/`, except `path:line` citations of project code, which are relative to the worktree root.
6. Where one finding appears in both reviews, this file keeps one issue and lists both sources.

## Neutrality check

The coordinator runs on Claude. The Codex review has 17 findings against the Claude sections, four of them Blocking. The Claude review has 8 findings against the Codex section, none Blocking. The coordinator checked these review claims against the code and accepted each one:

1. `r-codex-7`. Each `CameraGateway` feature call takes a `FeatureModule` argument (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:59-110`). The control-plane readback table omits it.
2. `r-codex-12`. Jazzy `ros2 topic hz` has only `--window`, `--filter`, and `--wall-time` (`ros:ros2/ros2cli/ros2topic/ros2topic/verb/hz.py:64-83`). It has no QoS option.
3. `r-codex-15`. The package installs and exports only the targets that its `install(TARGETS ...)` line names (`src/venimapping_camera/CMakeLists.txt:65-74`).
4. `r-claude-8`. The gateway rejects an empty namespace (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:21-25`).

No finding was softened or dropped. Two Blocking findings against the Claude sections stay Open (i10, i26). One Blocking finding (i11) stays Open, so that the Codex recheck can accept or reopen the coordinator proposal. One (i12) is Closed, because both reviews recommend the same register change.

## Summary

| Id | Source | Owner | Sections | Severity | Status | History |
|---|---|---|---|---|---|---|
| i1 | r-claude-1, r-codex mismatch 2 | codex | data-plane | Major | Open | Round 1: opened from both reviews. |
| i2 | r-claude-2, r-codex-13 (part) | codex | data-plane | Major | Open | Round 1: opened from both reviews. |
| i3 | r-claude-3, r-codex mismatch 3 | codex | data-plane | Major | Open | Round 1: opened. i26 depends on it. |
| i4 | r-claude-4, r-codex-3 (part), Codex note on d24 | codex | data-plane | Minor | Open | Round 1: opened after the i12 ruling. |
| i5 | r-claude-5 | codex | data-plane | Minor | Open | Round 1: opened. |
| i6 | r-claude-6, Codex note on ic1, M10 | codex | data-plane | Minor | Open | Round 1: opened. Both planners agree on the fix. |
| i7 | r-claude-7, Codex note on ic1 and ic3 | codex | data-plane | Minor | Open | Round 1: opened. |
| i8 | r-claude-8 | codex | data-plane | Minor | Open | Round 1: opened. |
| i9 | r-claude mismatch 4, r-codex mismatch 4, M7 | codex | data-plane | Minor | Open | Round 1: opened. |
| i10 | r-codex-1, r-claude mismatch 7 | claude | control-plane, testing | Blocking | Open | Round 1: opened from both reviews. |
| i11 | r-codex-2, N2, Codex note on d18 and d22, r-claude mismatch 8 | claude | control-plane | Blocking | Open | Round 1: coordinator proposes the narrow selector exception. Codex rechecks. |
| i12 | r-codex-3 (register part), N1, r-claude-4, Codex note on d24 | coordinator | register d24 | Blocking | Closed | Round 1: closed. Both reviews recommend the N1 text, and R6 allows it. |
| i13 | r-codex-4 | claude | control-plane, testing | Major | Open | Round 1: opened. |
| i14 | r-codex-5 | claude | control-plane, testing | Major | Open | Round 1: opened. |
| i15 | r-codex-6 | claude | control-plane, testing | Major | Open | Round 1: opened. |
| i16 | r-codex-7 | claude | control-plane, testing | Major | Open | Round 1: opened. Coordinator confirmed the module argument. |
| i17 | r-codex-8 | claude | control-plane, testing | Major | Open | Round 1: opened. |
| i18 | r-codex-9 | claude | control-plane, error-vocabulary, testing | Major | Open | Round 1: opened. |
| i19 | r-codex-10, N6 | claude | bring-up, implementation-sequence | Major | Open | Round 1: opened. The N6 narrowing stays. |
| i20 | r-codex-11 | claude | testing, implementation-sequence | Major | Open | Round 1: opened. |
| i21 | r-codex-12 | claude | testing, implementation-sequence | Major | Open | Round 1: opened. Coordinator confirmed the `hz` options. |
| i22 | r-codex-13 | claude | testing | Major | Open | Round 1: opened. The callback field part is i2. |
| i23 | r-codex-14 | claude | error-vocabulary | Major | Open | Round 1: opened. |
| i24 | r-codex-15 | claude | implementation-sequence | Major | Open | Round 1: opened. Coordinator confirmed the install list. |
| i25 | r-codex-16, N7 | claude | bring-up | Minor | Open | Round 1: opened. |
| i26 | r-codex-17, r-claude mismatch 6 | claude | control-plane, testing | Blocking | Open | Round 1: opened from both reviews. Needs the i3 model. |
| i27 | N4 | claude | control-plane, error-vocabulary, testing | Minor | Open | Round 1: opened from the Claude draft notes. |
| i28 | N3, r-claude mismatch 10, r-codex mismatch 5 | coordinator | register ic5 | Minor | Closed | Round 1: closed. Both reviews accept the extra rows. |
| i29 | N8 | coordinator | register ic4 | Minor | Closed | Round 1: closed. Neither review objects to `start(WorkerInit)`. |
| i30 | Verdicts, register d20 | Logan | data-plane, bring-up, testing | Major | For Logan | Round 1: the two d20 verdicts disagree. Register question L1. |

Counts after round 1: 26 Open, 3 Closed, 1 For Logan. This round closed 3 issues.

## Issues on the data-plane section (owner codex)

### i1. `receive_seq` and `frames_received` need one atomic increment

- Location: `codex/sections/data-plane.md:106`, `:113`.
- Finding: Step 1 increments `frames_received` and assigns `receive_seq` as two operations. The section gives no first value. It does not state that `receive_seq` equals `frames_received` after the increment. The control-plane freshness rule reads `R = stats().frames_received` and skips each frame with `receive_seq <= R` (`claude/sections/control-plane.md:194`, `:201`, `:209`). That rule needs one atomic increment. A plain counter that `stats()` reads is also a data race.
- Evidence: register ic3 item 3.1, ic8 guarantee 4. `claude/sections/testing.md:82`, `:140` expect the first value 1. `claude/draft-notes.md` M1.
- Expected change: State `receive_seq = frames_received.fetch_add(1) + 1`. The first value is 1. `stats().frames_received` loads the same atomic.

### i2. No stats field for the callback duration

- Location: `codex/sections/data-plane.md:56-66`, `:137`.
- Finding: The section says that the feed probe measures the callback time. The callback is private, and `FrameSourceStats` has no duration field. ic7 item 8 and ic8 guarantee 10 need the value.
- Evidence: `claude/sections/testing.md:152-153` record it in the `feed` and `load` modes. `codex/review-of-claude.md` r-codex-13 asks for the same field.
- Expected change: Add a duration field to `FrameSourceStats`, for example `callback_ns_max` and `callback_ns_total`. State which clock reads bound it.

### i3. No ownership model for a subscription that outlives its source

- Location: `codex/sections/data-plane.md:94`. `codex/source-tree.md:10-11`.
- Finding: The section says that a subscription can outlive its source and that source destruction closes it. It gives no ownership model. If `FrameFanout` owns the queues, a `close()` after source destruction uses freed memory. The source tree does not say how the source holds `FrameFanout`. `FakeFrameSource` must copy that choice.
- Evidence: register ic2 rule 7, ic7 item 5. `claude/sections/testing.md:93`, `:128`.
- Expected change: State the model. The Claude review proposes one queue block per subscription, held through a shared pointer, with weak references in `FrameFanout`. Any model that makes `close()` safe after source destruction meets the issue. i26 depends on this answer.

### i4. The data-plane text must state the d24 cutoff

- Location: `codex/sections/data-plane.md:113`. `codex/draft-notes.md:6-7`.
- Finding: Line 113 says that the shared lock meets d24 and ic8. A callback can hold a sequence from before the request and push it after `subscribe` returns. The draft note proposes the queue link as the only ordering point.
- Evidence: i12 closes the register question. The amended d24 needs both rules.
- Expected change: State that a new queue can get a frame with a `receive_seq` at or below `frames_received` at the time of `subscribe`. The queue link decides which pushes reach the queue. The control plane skips each frame with `receive_seq <= R`.

### i5. Heap work can happen inside the fan-out lock

- Location: `codex/sections/data-plane.md:90`, `:94`, `:102`, `:135`.
- Finding: An eviction, `close_admission`, and `close` can drop the last reference to a 1337472-byte message under the lock. The message destructor then frees memory in the lock section. `subscribe` also links the queue into a list under the lock. A growable list allocates there. Both conflict with ic8 guarantee 3.
- Evidence: register ic8 guarantee 3. `claude/camera/c1.md:104`.
- Expected change: Move each evicted or cleared frame to a local holder and release it after the unlock. Allocate the list node before the lock, or use an intrusive list.

### i6. String accessors must return a const reference

- Location: `codex/sections/data-plane.md:11`, `:17`, `:19`.
- Finding: The section gives each accessor the field type and `noexcept`. A `std::string` copy can throw `std::bad_alloc` inside a `noexcept` function. Both draft notes propose `const std::string&`, but the section does not state it.
- Evidence: register ic1 sketch. `codex/draft-notes.md:9`. `claude/draft-notes.md` M10.
- Expected change: State that `encoding()` and `tf_frame()` return `const std::string&` into the shared block. Scalars return by value.

### i7. No named seam to set the epoch fields

- Location: `codex/sections/data-plane.md:26`, `:108`, `:111`.
- Finding: Step 3 calls the public `ImageFrame::create`. Step 6 then sets `stream_epoch` and `significant_bits`. The public result is immutable, so step 6 needs a private seam that the section does not name.
- Evidence: register ic1 item 4, ic3 item 3.6, ic8 guarantee 3. `codex/draft-notes.md:8`.
- Expected change: Name the seam, for example a `friend` declaration for `FrameFanout` and a private setter. State the amended ic1 item 4: "immutable after `FrameFanout` publishes it".

### i8. An empty namespace subscribes at the graph root

- Location: `codex/sections/data-plane.md:125`.
- Finding: The section copies the gateway topic rule but not the gateway check for an empty namespace. An empty value gives `/image_raw` at the root, with no error.
- Evidence: `src/venimapping_camera/src/vimbax_camera_gateway.cpp:21-25`.
- Expected change: Return `kSourceCreateFailed` for an empty `camera_namespace`.

### i9. `FrameFanout` clock type and method set are not named

- Location: `codex/source-tree.md:10`. `codex/sections/data-plane.md:104`.
- Finding: `FakeFrameSource` takes `FrameFanoutClock&` and forwards to `subscribe`, `open_admission`, `close_admission`, `stats`, and `on_message`. The data-plane files name no clock type, no method set, and no clock lifetime rule.
- Evidence: `claude/sections/testing.md:44`. `claude/draft-notes.md` M7.
- Expected change: Name the clock type and the public methods of `FrameFanout`. State that the clock must outlive the `FrameFanout`.

## Issues on the Claude sections (owner claude)

### i10. The reconnect fallback start skips the guarded start sequence

- Location: `claude/sections/control-plane.md:270-277`. `claude/sections/testing.md:121-123`.
- Finding: The reconnect fallback calls `stream_start()` with no profile check, no match wait, and no new admission boundary. The branch that keeps the driver restart calls `open_admission()` with no bit depth argument.
- Evidence: register d11 item 3, d17, d22 items 5 to 7, ic3 item 4. `codex/sections/data-plane.md:102`.
- Expected change: Pass the bit depth from the verified format. Route the fallback start through the start sequence. Assert the call order and the new epoch in `ReconnectNoRestart`.

### i11. `TriggerSelector` write during a stream conflicts with d18 item 7

- Location: `claude/sections/control-plane.md:155-183`. `claude/draft-notes.md` N2.
- Finding: The reconnect readback writes `TriggerSelector` while the driver can stream. d18 item 3 needs that write, and d18 item 7 bars all feature writes during a stream.
- Evidence: `driver:vimbax_camera/src/vimbax_camera_node.cpp:556-568`, `:579-593`. `claude/camera/c2.md` §3.3 item 7: the camera accepted the selector write while it streamed. c2 §5 item 9: runner `status` calls moved the selector many times during both streams, and `TriggerMode` under `FrameStart` did not change.
- Coordinator proposal: Approve the narrow exception. Amend d18 item 7 to the N2 text: "Phase 1 writes no acquisition value during a stream. The `TriggerSelector` write before a `TriggerMode` read is allowed." Reason: a confirmed stop before each reconnect readback would always discard the driver restart that d22 item 5 keeps. The control plane already keeps admission closed until the readback matches.
- Expected change: State the amendment in the section and cite the c2 evidence. If the owner rejects the proposal, state a confirmed stop before the readback instead.

### i12. d24 promises the first push, but the capacity-1 queue keeps the newest

- Location: register d24, ic8 guarantee 5. `claude/draft-notes.md` N1. `codex/draft-notes.md:6`.
- Finding: With capacity 1 and drop oldest, the first push can be evicted before the caller takes it. About 5 Mono8 frames at 69.7 Hz arrive before the `stream_start` reply (c1 §3.5).
- Resolution: Closed. The register d24 decision now reads: "The answer is a frame that the fan-out pushed to the get image subscription after it opened, with `receive_seq` greater than `frames_received` at the request." The Claude review (r-claude-4) and the Codex review (r-codex-3, first option) recommend this text if R6 allows any qualifying frame. R6 states that "received after the request" is enough. The data-plane text change is i4. The Codex dissent for a one-shot latch is in v2 section 14.

### i13. Requests during recovery states take the normal start path

- Location: `claude/sections/control-plane.md:123-128`, `:198-204`, `:258-283`.
- Finding: New requests take the start path when admission is closed. In `kOutage`, this permits a start attempt instead of the stated wait. During recovery, it permits corrective writes before a confirmed stop.
- Evidence: register d18 items 5 and 7, d22 items 1 to 8. `claude/sections/control-plane.md:268`. `driver:vimbax_camera/src/vimbax_camera_node.cpp:561-566`, `:590-593`.
- Expected change: Give each recovery state a rule for new requests. Allow corrective writes only after a confirmed stop. Test a request during an outage with another lease active.

### i14. Get image cancellation is checked only after a pending call

- Location: `claude/sections/control-plane.md:134-145`, `:189-218`. `claude/sections/testing.md:112-114`.
- Finding: The worker checks abandonment only after a pending gateway call. A request can expire while queued, or between readback, match, and start. A late frame can also race the deadline.
- Evidence: register d17 item 2, d26. `src/venimapping_camera/src/vimbax_camera_gateway.cpp:179-201`. `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:79-94`.
- Expected change: Give the request a shared cancel state and one absolute deadline. Check both before each stage. State which side closes the subscription and releases the lease. Test expiry before dequeue and during the match wait.

### i15. No completion rule for queued requests at init failure or shutdown

- Location: `claude/sections/control-plane.md:75-96`, `:293-303`. `claude/sections/testing.md:127-128`.
- Finding: Requests queue before `start`, but the section gives no result for them if init fails or shutdown runs. It tests destruction with a live feed but defines no destructor shutdown. A worker call to `shutdown` would join its own thread.
- Evidence: register ic2 rules 3 and 7, ic4 stop order.
- Expected change: Define request results before start, after init failure, and during shutdown. Complete queued requests and wake waits. Specify destructor shutdown and exclude calls from the worker. Test destruction with a pending request.

### i16. Bit depth comes from the first readback, and feature calls omit the module

- Location: `claude/sections/control-plane.md:138-144`, `:155-181`, `:273-275`.
- Finding: Start step 6 takes `significant_bits` from the first readback, but the second readback decides the profile. A Mono12 to Mono8 correction would label Mono8 frames as 12 bits. The readback table also omits the `FeatureModule` argument.
- Evidence: register d14, d18 items 3 to 6. `src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:59-110`. `src/venimapping_camera/include/venimapping_camera/types/feature_module.hpp:15-21`.
- Expected change: Use the final verified `PixelFormat` for the format check and for `significant_bits`. State `FeatureModule::kRemoteDevice` for each call. Test a format correction and check the bit depth of the first frame.

### i17. A failed start leaves admission open, and the no-user stop has no failure path

- Location: `claude/sections/control-plane.md:234-247`, `:274-289`, `:297-301`.
- Finding: A start failure leaves admission open during reconciliation, and a successful reconciliation stop has no close rule. A later epoch can get queued frames. The no-user stop has no failure path.
- Evidence: register d19 items 2 and 3, d22 items 3 to 9, ic3 item 4. `driver:vimbax_camera/src/vimbax_camera.cpp:445-510`: the driver starts frame processing before the acquisition command can fail.
- Expected change: Close admission and clear the queues when a start fails. Send each failed start or stop through d19, also the no-user stop. Require a confirmed stop before a correction or another start. Test a failed start that admitted a frame before the error.

### i18. -15 can reach a caller, and a poll error can clear a live wedge

- Location: `claude/sections/control-plane.md:234-249`, `:260-266`. `claude/sections/error-vocabulary.md:97-109`.
- Finding: The error table says that -15 from a stream call never reaches a caller. Recovery step 3 returns the first error after a successful reconciliation stop, and that error can be -15. In `kWedged`, a gateway error on a poll counts as "driver gone", so a timeout and then `true` can clear a wedge that still exists.
- Evidence: register d19, ic5 item 2. `driver:vimbax_camera/src/vimbax_camera.cpp:513-519`, `:577-585`. `driver:vimbax_camera/src/vimbax_camera_node.cpp:1520-1527`. `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:79-94`.
- Expected change: Keep the first error and the reconciliation result apart. Keep `kWedged` on a poll error. Define the evidence for a reopen or a driver restart. Test an error and then a success on the same driver.

### i19. The bring-up checks do not prove that the installed values applied

- Location: `claude/sections/bring-up.md:151-168`. `claude/sections/implementation-sequence.md:46-53`.
- Finding: The topic check passes when `image_raw` has no publisher. The settings check passes with a missing XML file if the camera already holds the values. Neither check proves that the launch overrides and the file applied.
- Evidence: register d18 items 1 and 8, ic6 item 3. `driver:vimbax_camera/src/vimbax_camera_node.cpp:390-400`.
- Expected change: Require a raw image publisher and read the live plugin filter. Bound the first-frame wait. Read back the `settings_file` parameter. Check the profile after a controlled reopen from a known different value. The N6 prefix rule for plugin topics stays.

### i20. Step 9 leaves the driver on device stamps before the wedge check

- Location: `claude/sections/testing.md:156`, `:168-173`. `claude/sections/implementation-sequence.md:169-182`.
- Finding: Step 9 launches the driver with `use_ros_time:=false` and then runs the wedge check in feed mode, with no step to restore host stamps. Feed mode then discards each frame for stamp basis. The wedge check also needs a gate-listed format before the controller starts, and the same controller across the driver restart.
- Evidence: register d19, d20 items 6 to 8. `claude/camera/c1.md` §3.1. `codex/sections/data-plane.md:104-113`.
- Expected change: Relaunch with host stamps before the wedge check. Restore a gate-listed format while the driver stays wedged, or check wedge recovery with the scripted gateway only. Keep one controller alive across the restart.

### i21. The outside-reader check uses a `ros2 topic hz` option that does not exist

- Location: `claude/sections/testing.md:151-171`. `claude/sections/implementation-sequence.md:161-182`.
- Finding: Jazzy `ros2 topic hz` has no `--qos-reliability` option. The `stamps` mode also has no rule to tell a reader gap from a driver gap.
- Evidence: `ros:ros2/ros2cli/ros2topic/ros2topic/verb/hz.py:64-83`. `driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1603`. `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`.
- Expected change: Use a test reader with explicit RELIABLE QoS. Match the stamp reader before the start. Record stamp gaps and driver log gaps over the same interval. Mark a load result inconclusive if no driver gap occurs.

### i22. Tests lack synchronization points and observation hooks

- Location: `claude/sections/testing.md:39-50`, `:101-103`, `:112`, `:125`, `:142`, `:152-154`.
- Finding: `InFlightFrameSkipped` has no way to hold a callback between sequence assignment and the lock. `Adapter.NoPixelCopy` has no way to see the received buffer address. The fake default stamp equals the boundary when the clock does not move, so `inject` discards the frame. The match timer has no defined start and end.
- Evidence: register ic3 item 3, ic7, ic8 guarantees 4 and 5, P9.
- Expected change: Use a barrier in the injected clock before the fan-out lock. Compare the span with the received buffer in an adapter test. Advance fake time after admission opens. Name the match timer endpoints. The callback duration field is i2.

### i23. Error vocabulary rows are narrower than the behavior

- Location: `claude/sections/error-vocabulary.md:81`, `:99-109`, `:115-119`.
- Finding: The `kDeadlinePassed` row covers only a missing frame, not a request that expires in the queue or in gateway work. The table promises pass-through for writes, but the corrective write sequence lets the second readback decide. The `transport_lost` row says "DDS rejected samples at the reader", which hides the history overwrite limit.
- Evidence: register d12 item 5, d18 items 5 and 6, d26. `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3943-3955`. `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`.
- Expected change: Define `kDeadlinePassed` for each stage. State how the second readback decides the write result. Describe `transport_lost` as the RMW sample-lost event count, and state that a history overwrite does not raise it.

### i24. The acquisition target is not installed or exported

- Location: `claude/source-tree.md:13-28`. `claude/sections/implementation-sequence.md:24-25`, `:111-125`, `:154-159`.
- Finding: Step 5 builds `venimapping_camera_acquisition` and installs its header, but no step installs and exports the library. Steps 4 and 5 run in parallel and both edit `CMakeLists.txt`.
- Evidence: `src/venimapping_camera/CMakeLists.txt:62-75`.
- Expected change: Install and export the acquisition target in step 5. Add an installed-consumer link check. State how the two CMake edits join.

### i25. The settings file scope is not stated

- Location: `claude/sections/bring-up.md:87-88`. `claude/draft-notes.md` N7.
- Finding: The XML file is saved with the no-LUT persistence type for three modules. The module flags do not show that the file holds every feature. Readback checks only the listed values, so it cannot see a load error when the values already match.
- Evidence: `driver:vimbax_camera/src/vimbax_camera.cpp:1308-1328`, `:1331-1367`. `driver:vimbax_camera/src/vimbax_camera_node.cpp:390-400`.
- Expected change: State the module scope and the persistence type. Describe the readback as a check of the listed values only. Use the driver load result in the i19 rig check.

### i26. `Feed` and the worker share a subscription that ic2 gives to `Feed` alone

- Location: `claude/sections/control-plane.md:96`, `:293-303`.
- Finding: The control-plane section shares the subscription between the worker and `Feed`. ic2 item 1 gives `Feed` sole ownership of a `std::unique_ptr<FrameSubscription>`. Shutdown must close a feed safely after the controller and the source are gone.
- Evidence: register ic2 rules and `Feed` items 1 to 3, ic4 stop order. Both reviews raise it.
- Expected change: Choose a model that fits the i3 answer. Either keep sole ownership in `Feed` and give the worker a close path, or state the conversion to `std::shared_ptr` and propose the ic2 change. The codex fix for i3 runs first.

### i27. `feed_open` has no caller deadline

- Location: `claude/sections/control-plane.md:132`. `claude/draft-notes.md` N4.
- Finding: With a 2000 ms gateway timeout and a camera that does not answer, a cold `feed_open` can block for about 50 s. The Claude draft notes state the risk and propose `FeedOptions::deadline`, default 5000 ms.
- Evidence: register d26 covers `get_image` only.
- Expected change: Adopt or reject the proposal. If adopted, use the same mechanism as i14 and add `feed_open` to the `kDeadlinePassed` row.

## Register amendments closed by the coordinator

### i28. Two codes come from both layers

- Source: N3. The Claude review (mismatch 10) and the Codex review (mismatch 5) both accept the extra rows.
- Resolution: Closed. ic5 gains control-plane rows for `kFeedClosed` (a request after `shutdown()`) and `kInvalidArgument` (a bad controller option, or a capacity passed through from `subscribe`). `AcquisitionController::create` can also return `kFormatNotStreamable`. ic5 item 1 does not change: the data plane returns only codes 1, 7, 10, and 11.

### i29. The worker starts through `start(WorkerInit)`

- Source: N8.
- Resolution: Closed. ic4 says that the worker calls `bind_to_current_thread()` first, but the ROS-free controller holds only `CameraGateway&`, which has no bind method (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:27-142`). The composition root passes a hook that calls `VimbaXCameraGateway::bind_to_current_thread()`. Neither review objects. The shutdown rules for the hook are part of i15.

## Issues for Logan

### i30. The d20 dispute verdicts disagree

- Source: `claude/disputes/d20-verdict.md`, `codex/disputes/d20-verdict.md`, register d20.
- Finding: The Claude verdict keeps `use_ros_time: false` and fills `host_stamp_ns` from the DDS source timestamp, with an optional device stamp. The Codex verdict sets `use_ros_time: true` and fills one `host_stamp_ns` from the header.
- Status: For Logan, question L1. The drafts use the Codex verdict as a working assumption. The cost to reverse is low (register d20).

## Tasks emitted in round 1

| Task | Template | Tool | Issues | Depends on |
|---|---|---|---|---|
| `fix-codex-r1` | fix | codex | i1 to i9 | none |
| `recheck-claude-r1` | recheck | claude | i1 to i9 | `fix-codex-r1` |
| `fix-claude-r1` | fix | claude | i10, i11, i13 to i27 | `fix-codex-r1` |
| `recheck-codex-r1` | recheck | codex | i10, i11, i13 to i27 | `fix-claude-r1` |
| `integrate-2` | integrate | claude | all | the four tasks above. It blocks `prose`. |

`fix-claude-r1` waits for `fix-codex-r1`, because i26 needs the ownership model from i3, and i22 needs the clock and method names from i9. No dispute task is emitted. No issue has had a fix and a recheck yet.

## Camera requests

No draft or review task wrote a camera request. The files in `claude/camera-requests/` and `codex/camera-requests/` come from the trace and positions tasks, and earlier rounds settled them. This round accepts no camera check.
