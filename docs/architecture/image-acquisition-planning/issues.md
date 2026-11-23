# Issues for the image acquisition design

Round 3. Checkpoint `fbebe85`. The coordinator wrote this file in task `integrate-3`. Round 1 wrote the first version at checkpoint `8d2c760`. Round 2 wrote the second version at checkpoint `ecba565`.

## How to read this file

1. Each issue has an id, `i1` to `i34`. An id is never reused.
2. Status values:
   - Open. The owner must fix the section or reject the issue with evidence. The other planner rechecks.
   - Closed. Both planners agree, or the evidence settles the issue.
   - For Logan. Only a decision from Logan can settle the issue.
3. Severity values come from the reviews: Blocking, Major, and Minor. A reopened issue keeps its round 1 severity.
4. Sources:
   - `r-claude-N` is finding N in `claude/review-of-codex.md`.
   - `r-codex-N` is finding N in `codex/review-of-claude.md`.
   - "mismatch N" is item N in the interface mismatch list of the named review.
   - `N1` to `N9` are entries in `claude/draft-notes.md`. "Codex note" is an entry in `codex/draft-notes.md`.
   - "Verdicts" are the two files `claude/disputes/d20-verdict.md` and `codex/disputes/d20-verdict.md`.
   - `fix-codex-r1` is `codex/fixes/round-1.md`. `fix-claude-r1` is `claude/fixes/round-1.md`. `fix-claude-r2` is `claude/fixes/round-2.md`.
   - `recheck-claude-r1` is `claude/rechecks/round-1.md`. `recheck-codex-r1` is `codex/rechecks/round-1.md`. `recheck-codex-r2` is `codex/rechecks/round-2.md`.
   - "integrate-2" and "integrate-3" mark a problem that the coordinator found while it built v2.
5. Paths are relative to `docs/architecture/image-acquisition-planning/`, except `path:line` citations of project code, which are relative to the worktree root. Line numbers in the Claude and Codex sections are at checkpoint `fbebe85`, unless an entry names another checkpoint.
6. Where one finding appears in both reviews, this file keeps one issue and lists both sources.

## Neutrality check

The coordinator runs on Claude. In round 3, the Codex recheck accepted 7 of the 10 Claude fixes and reopened 3. The coordinator checked each reopen against the section text and the driver source, and it reread the accepted fixes with the most risk.

Check of the Codex reopens. Each reopen holds:

1. i15 item 1. `start` step 3 "applies the join rule, sets `kStopped`, and returns the init error" (`claude/sections/control-plane.md:188`). The join rule lets only the thread that moved the thread object join (`:182`). A concurrent `shutdown()` in `kStarting` can take the object first (`:196`). `start` then sets `kStopped` while that thread still joins. A third `shutdown()` that waits for `kStopped` (`:197`) can return before the worker exits.
2. i15 item 2. `shutdown()` on the worker thread only sets the flag (`:194`), so the value stays `kStarting`. `start` step 5 applies the join rule and returns `kFeedClosed`, but it sets no `kStopped` (`:190`). If `start` took the object, a `shutdown()` on another thread found no object and waits for `kStopped` (`:196`) with no end.
3. i19. Part A step 12 runs `grep` on `driver_b.log` right after the step 11 launch (`claude/sections/bring-up.md:196-198`). The driver tries the load inside `initialize_camera` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:97`, `:390-399`). It logs `Initialization done!` only after that (`:134`). A `grep` that runs first misses a later failed-load line. Implementation step 1 exit check 3 repeats the same check (`claude/sections/implementation-sequence.md:64`).
4. i25. The settings file scope depends on the i19 load check (`claude/sections/bring-up.md:102`). It has the same timing gap.

Check of the Codex accepts. The coordinator reread the fixed text for i14, i18, i26, and i31:

1. i14. A check point reads the outcome and the steady clock under the outcome mutex before each gateway call (`claude/sections/control-plane.md:148-154`). An expiry between `open_admission` and `stream_start` calls `close_admission()` (`:159`). The take loop checks the deadline after each frame (`:391`).
2. i18. The confirmation stop is outside the general recovery (`claude/sections/control-plane.md:437`, `:454`). Any failure keeps `kWedged` (`:456`).
3. i26. `released` under the link mutex gives one release for each link (`claude/sections/control-plane.md:230-231`). Move assignment closes the destination first (`:235`).
4. i31. Each step 5 case in `claude/sections/implementation-sequence.md:150-153` uses only `feed_open`, `start`, `shutdown`, and `Feed` methods in `claude/sections/testing.md`.

The coordinator found no new defect in the Claude sections or in the data-plane section. No finding was softened or dropped. Each open issue has the same owner, Claude, because Codex owns no open finding.

## Summary

| Id | Source | Owner | Sections | Severity | Status | History |
|---|---|---|---|---|---|---|
| i1 | r-claude-1, r-codex mismatch 2 | codex | data-plane | Major | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i2 | r-claude-2, r-codex-13 (part) | codex | data-plane | Major | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i3 | r-claude-3, r-codex mismatch 3 | codex | data-plane | Major | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i4 | r-claude-4, r-codex-3 (part), Codex note on d24 | codex | data-plane | Minor | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i5 | r-claude-5 | codex | data-plane | Minor | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i6 | r-claude-6, Codex note on ic1, M10 | codex | data-plane | Minor | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i7 | r-claude-7, Codex note on ic1 and ic3 | codex | data-plane | Minor | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i8 | r-claude-8 | codex | data-plane | Minor | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i9 | r-claude mismatch 4, r-codex mismatch 4, M7 | codex | data-plane | Minor | Closed | Round 1: opened. Round 2: fixed, Claude recheck accepted. |
| i10 | r-codex-1, r-claude mismatch 7 | claude | control-plane, testing | Blocking | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i11 | r-codex-2, N2, Codex note on d18 and d22, r-claude mismatch 8 | claude | control-plane | Blocking | Closed | Round 1: coordinator proposal. Round 2: adopted, Codex recheck accepted. |
| i12 | r-codex-3 (register part), N1, r-claude-4, Codex note on d24 | coordinator | register d24 | Blocking | Closed | Round 1: closed with the N1 text. |
| i13 | r-codex-4 | claude | control-plane, testing | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i14 | r-codex-5, recheck-codex-r1 | claude | control-plane, error-vocabulary, testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with the acceptance check, Codex recheck accepted. |
| i15 | r-codex-6, recheck-codex-r1, recheck-codex-r2 | claude | control-plane, testing, implementation-sequence | Major | Open | Round 1: opened. Rounds 2 and 3: fixed, Codex recheck reopened. Coordinator confirmed the join and `kStopped` gap. |
| i16 | r-codex-7 | claude | control-plane, testing | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i17 | r-codex-8, recheck-codex-r1 | claude | control-plane, testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with the pending-epoch rule, Codex recheck accepted. |
| i18 | r-codex-9, recheck-codex-r1 | claude | control-plane, error-vocabulary, testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with one confirmation stop, Codex recheck accepted. |
| i19 | r-codex-10, N6, recheck-codex-r1, recheck-codex-r2 | claude | bring-up, implementation-sequence | Major | Open | Round 1: opened. Rounds 2 and 3: fixed, Codex recheck reopened. Coordinator confirmed the log read timing. |
| i20 | r-codex-11 | claude | testing, implementation-sequence | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i21 | r-codex-12, recheck-codex-r1 | claude | testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with one source-time interval, Codex recheck accepted. |
| i22 | r-codex-13, recheck-codex-r1 | claude | testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with take hooks, Codex recheck accepted. |
| i23 | r-codex-14 | claude | error-vocabulary | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i24 | r-codex-15 | claude | implementation-sequence | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i25 | r-codex-16, N7, recheck-codex-r1, recheck-codex-r2 | claude | bring-up | Minor | Open | Round 1: opened. Rounds 2 and 3: fixed, Codex recheck reopened on the load check that i19 also covers. |
| i26 | r-codex-17, r-claude mismatch 6, recheck-codex-r1 | claude | control-plane, testing | Blocking | Closed | Round 1: opened. Round 2: reopened on double release. Round 3: fixed with the `released` flag, Codex recheck accepted. |
| i27 | N4 | claude | control-plane, error-vocabulary, testing | Minor | Closed | Round 1: opened. Round 2: adopted, Codex recheck accepted. |
| i28 | N3, r-claude mismatch 10, r-codex mismatch 5 | coordinator | register ic5 | Minor | Closed | Round 1: closed. |
| i29 | N8 | coordinator | register ic4 | Minor | Closed | Round 1: closed. |
| i30 | Verdicts, register d20 | Logan | data-plane, bring-up, testing | Major | For Logan | Round 1: verdicts disagree, question L1. Rounds 2 and 3: no change. |
| i31 | integrate-2 | claude | implementation-sequence, testing | Minor | Closed | Round 2: opened by the coordinator. Round 3: fixed, Codex recheck accepted. |
| i32 | recheck-claude-r1 register list | coordinator | register ic1, ic2, ic3, ic7, ic8, d24 | Minor | Closed | Round 2: opened and closed. v2 §4.4 records the text. |
| i33 | fix-claude-r1 register list | coordinator | register d18, d22, d26, ic3, ic4, ic5 | Minor | Closed | Round 2: opened and closed for the accepted fixes. Round 3: i34 adopts two of the three waiting items. |
| i34 | fix-claude-r2 register list | coordinator | register d19, d26, ic2, ic3, ic4, ic5 | Minor | Closed | Round 3: opened and closed for the accepted fixes. Items for i15 and i19 wait. |

Counts after round 3: 3 Open, 30 Closed, 1 For Logan. This round closed 8 issues: i14, i17, i18, i21, i22, i26, i31, and the new register issue i34.

Open issues by severity: no Blocking, two Major (i15, i19), and one Minor (i25). All open issues are on the Claude sections.

## Issues on the data-plane section (owner codex)

All nine issues are Closed. Each fix is in `codex/sections/data-plane.md` at checkpoint `5bb39db`. `recheck-claude-r1` accepted each one. The section did not change in round 3.

### i1. `receive_seq` and `frames_received` need one atomic increment

- Round 1 finding: Step 1 incremented `frames_received` and assigned `receive_seq` as two operations, with no first value. The control-plane freshness rule needs one atomic increment.
- Resolution: Closed in round 2. `receive_seq = frames_received.fetch_add(1) + 1` on a zero-initialized atomic. `stats().frames_received` loads the same atomic (`codex/sections/data-plane.md:124`, `:132`).

### i2. No stats field for the callback duration

- Round 1 finding: The feed probe needs the callback time, but `FrameSourceStats` had no duration field.
- Resolution: Closed in round 2. `callback_ns_max` and `callback_ns_total` are in `FrameSourceStats`. Two `steady_now()` reads bound the interval (`codex/sections/data-plane.md:68-69`, `:125`, `:130`).

### i3. No ownership model for a subscription that outlives its source

- Round 1 finding: A `close()` after source destruction had no safe ownership model.
- Resolution: Closed in round 2. Each source holds `FrameFanout` by value. Each subscription holds shared pointers to its queue block and to the shared state with the lock. The port still returns `std::unique_ptr<FrameSubscription>` (`codex/sections/data-plane.md:89-90`, `:102-106`).

### i4. The data-plane text must state the d24 cutoff

- Round 1 finding: The section did not state that a frame with an earlier sequence can reach a new queue.
- Resolution: Closed in round 2. The queue link decides the pushes. The worker reads `R` before `subscribe` and skips `receive_seq <= R` (`codex/sections/data-plane.md:134-136`).

### i5. Heap work can happen inside the fan-out lock

- Round 1 finding: An eviction or a clear could free a 1337472-byte message under the lock. A growable list could allocate under the lock.
- Resolution: Closed in round 2. Storage and list nodes are allocated before the lock. Four local holders defer each last release until after the unlock (`codex/sections/data-plane.md:104`, `:108`).

### i6. String accessors must return a const reference

- Round 1 finding: A `std::string` copy can throw inside a `noexcept` accessor.
- Resolution: Closed in round 2. `encoding()` and `tf_frame()` return `const std::string&` (`codex/sections/data-plane.md:13`).

### i7. No named seam to set the epoch fields

- Round 1 finding: Step 6 set fields on an immutable public frame with no named seam.
- Resolution: Closed in round 2. `FrameFanout` is a friend of `ImageFrame` and uses the private `stage` factory. The frame is immutable after `FrameFanout` publishes it (`codex/sections/data-plane.md:30`).

### i8. An empty namespace subscribes at the graph root

- Round 1 finding: An empty `camera_namespace` gave `/image_raw` with no error.
- Resolution: Closed in round 2. An empty value returns `kSourceCreateFailed` before the ROS subscription (`codex/sections/data-plane.md:150`).

### i9. `FrameFanout` clock type and method set are not named

- Round 1 finding: The fake forwards to `FrameFanout`, but the clock type, the methods, and the clock lifetime were not named.
- Resolution: Closed in round 2. `FrameFanoutClock`, its two reads, the method set, and the lifetime rule are in `codex/sections/data-plane.md:118-122`. i32 adds the abstract class form to ic7.

## Issues on the Claude sections (owner claude)

### i10. The reconnect fallback start skips the guarded start sequence

- Round 1 finding: The fallback called `stream_start()` with no checks, and one `open_admission()` had no bit depth.
- Resolution: Closed in round 2. The fallback calls `close_admission()` and runs the full start sequence. Each `open_admission` passes the bit depth (`claude/sections/control-plane.md:486-487`). `ReconnectNoRestart` asserts the order and epoch 3 (`claude/sections/testing.md:245`).

### i11. `TriggerSelector` write during a stream conflicts with d18 item 7

- Round 1 finding: The reconnect readback writes the selector while the driver can stream.
- Resolution: Closed in round 2. The section adopts the amended d18 item 7 and cites c2 (`claude/sections/control-plane.md:346-352`). i33 records the register text.

### i12. d24 promises the first push, but the capacity-1 queue keeps the newest

- Resolution: Closed in round 1. The d24 decision reads: "The answer is a frame that the fan-out pushed to the get image subscription after it opened, with `receive_seq` greater than `frames_received` at the request." The Codex dissent for a one-shot latch is in v2 section 14.

### i13. Requests during recovery states take the normal start path

- Round 1 finding: New requests could start a stream in `kOutage` and write before a confirmed stop.
- Resolution: Closed in round 2. The table "Stream states and new requests" gives one rule per state. Corrective writes need a confirmed stop (`claude/sections/control-plane.md:243-262`, `:286-290`).

### i14. Get image cancellation is checked only after a pending call

- Round 1 finding: The worker checked abandonment only after a pending gateway call.
- Round 2 recheck finding: No check ran between the calls of one readback. The take loop could return a frame queued after the deadline. No rule closed admission after an expiry between `open_admission` and `stream_start`.
- Round 3 fix (`fix-claude-r2`): A check point before each gateway call, under the outcome mutex (`claude/sections/control-plane.md:148-154`). `close_admission()` after an expiry before `stream_start` (`:156-161`). The take loop checks the deadline before each `take` and after each frame (`:386-399`). Three new tests (`claude/sections/testing.md:173-174`, `:178`, `:197-208`).
- Resolution: Closed in round 3. `recheck-codex-r2` accepts each item. The fix adopts the acceptance check that the round 2 recheck asked for, so the disagreement on item 2 is settled and needs no dispute.

### i15. No completion rule for queued requests at init failure or shutdown

- Location: `claude/sections/control-plane.md:169-206`. `claude/sections/testing.md:255-259`. `claude/sections/implementation-sequence.md:153`.
- Round 1 finding: Queued requests had no result at init failure or shutdown, and a worker call to `shutdown` would join its own thread.
- Round 2 recheck finding: Shutdown before `start` had no path. No rule decided which thread joins when `start` and `shutdown` overlap.
- Round 3 fix (`fix-claude-r2`): A lifecycle value under one mutex. Shutdown in `kCreated` completes the queue on the calling thread. A join rule: only the thread that moves the thread object out joins. Tests `ShutdownBeforeStart` and `StartShutdownOverlap`. `recheck-codex-r2` accepts the shutdown before `start`.
- Round 3 recheck finding, confirmed by the coordinator:
  1. After an init failure, `start` sets `kStopped` also when a concurrent `shutdown()` took the thread object and still joins (`claude/sections/control-plane.md:182`, `:188`, `:196`). A third `shutdown()` that waits for `kStopped` (`:197`) can return before the worker exits.
  2. If `WorkerInit` calls `shutdown()` and succeeds, `start` step 5 can own the join, but it sets no `kStopped` (`:190`, `:194`). A `shutdown()` on another thread that found no object waits for `kStopped` (`:196`) with no end.
- Expected change:
  1. After the join ends, make the thread that joined set `kStopped` and notify all waiters.
  2. Make each other thread, also `start`, wait for that transition when another thread owns the join.
  3. Test a failed init during a concurrent `shutdown()`.
  4. Test a successful init that calls `shutdown()`, with a second `shutdown()` that waits.
- Note: This is the third round on i15. The fix and the recheck do not disagree. Each recheck found a new gap in the same lifecycle rules. No dispute is needed.

### i16. Bit depth comes from the first readback, and feature calls omit the module

- Resolution: Closed in round 2. The final readback decides the format check and the bit depth. Each feature call passes `FeatureModule::kRemoteDevice` (`claude/sections/control-plane.md:284-295`, `:328-339`). `FormatCorrectionBits` checks 8 bits on the first frame (`claude/sections/testing.md:160`).

### i17. A failed start leaves admission open, and the no-user stop has no failure path

- Round 1 finding: A failed start left admission open, and the no-user stop had no failure path.
- Round 2 recheck finding: The section promised that an open feed never gets a frame from a failed epoch. Admission opens before `stream_start`, so the promise was false.
- Round 3 fix (`fix-claude-r2`): The promise is gone. "Frames from an epoch whose start is pending" defines what a feed and a get image can see (`claude/sections/control-plane.md:305-322`). New test `ConsumerDuringFailingStart` (`claude/sections/testing.md:219`, `:225-234`).
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

### i18. -15 can reach a caller, and a poll error can clear a live wedge

- Round 1 finding: The first error and the reconciliation result were mixed, and a poll error could clear a live wedge.
- Round 2 recheck finding: The confirmation stop was in the general failure recovery, which gave a different state from the wedge rule for the same failure.
- Round 3 fix (`fix-claude-r2`): One confirmation stop for each change signal, outside the failure recovery. Any failure keeps `kWedged` (`claude/sections/control-plane.md:437`, `:447-461`). Tests `WedgePollErrorKeepsWedge` and `WedgeConfirmMinus3` (`claude/sections/testing.md:222-223`).
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

### i19. The bring-up checks do not prove that the installed values applied

- Location: `claude/sections/bring-up.md:176-206`. `claude/sections/implementation-sequence.md:64`.
- Round 1 finding: The topic check and the settings check could pass when the file did not apply.
- Round 2 recheck finding: Part A had no readback before the reopen. The log check matched only at the start of a line, so it could not fail.
- Round 3 fix (`fix-claude-r2`): A readback before the reopen, a control launch with a missing file, and `grep -F` anywhere in the line (`claude/sections/bring-up.md:95-100`, `:184-198`). `recheck-codex-r2` accepts these parts.
- Round 3 recheck finding, confirmed by the coordinator: Part A step 12 runs `grep` on `driver_b.log` right after the step 11 launch (`claude/sections/bring-up.md:196-198`). The driver tries the load inside `initialize_camera` and logs `Initialization done!` only after it (`driver:vimbax_camera/src/vimbax_camera_node.cpp:97`, `:134`, `:390-399`). A `grep` that runs first can miss a later failed-load line. Implementation step 1 exit check 3 has the same gap (`claude/sections/implementation-sequence.md:64`).
- Expected change:
  1. Before each log check, wait for `Initialization done!` in that log, with a time limit.
  2. If the line does not appear by the limit, fail the check.
  3. Apply the same wait in implementation step 1 exit check 3.

### i20. Step 9 leaves the driver on device stamps before the wedge check

- Resolution: Closed in round 2. Tier 4 check 4 relaunches with host stamps and reads `use_ros_time`. The wedge check restores `Mono8` with the CLI and keeps one controller across the restart (`claude/sections/testing.md:343-388`, `claude/sections/implementation-sequence.md:205-210`).

### i21. The outside-reader check uses a `ros2 topic hz` option that does not exist

- Round 1 finding: `ros2 topic hz` has no QoS option, and the stamp run had no rule to tell a reader gap from a driver gap.
- Round 2 recheck finding: Driver gap lines counted only after the start reply, but stamps started at the first frame. One log line could match more than one gap.
- Round 3 fix (`fix-claude-r2`): One source-time interval for each rate. Each line belongs to at most one pair. Ambiguous items make the result inconclusive (`claude/sections/testing.md:306-339`).
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it. Gap fact 4 keeps the clock agreement as a working assumption with an inconclusive outcome.

### i22. Tests lack synchronization points and observation hooks

- Round 1 finding: Several tests had no hold point, no address check, a fake stamp equal to the boundary, and an undefined match timer.
- Round 2 recheck finding: `InFlightFrameSkipped` could pass with the `receive_seq <= R` skip removed, because N+1 could evict N first.
- Round 3 fix (`fix-claude-r2`): Take hooks on each fake subscription. The test waits for a second `take` and checks `taken_seqs(1) == {N}` before it injects N+1 (`claude/sections/testing.md:78-99`, `:184-195`).
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

### i23. Error vocabulary rows are narrower than the behavior

- Resolution: Closed in round 2. A "Deadline stages" table, a corrective write rule, and the `transport_lost` row as the RMW `message_lost` total (`claude/sections/error-vocabulary.md:99-115`, `:134-152`). Round 3 adds the rows for i14.

### i24. The acquisition target is not installed or exported

- Resolution: Closed in round 2. Step 5 installs and exports `venimapping_camera_acquisition` and links an installed consumer. "CMake layout" gives the join rule for steps 4 and 5 (`claude/sections/implementation-sequence.md:29-40`, `:141-158`).

### i25. The settings file scope is not stated

- Location: `claude/sections/bring-up.md:84-104`.
- Round 1 finding: The file scope and the limit of the readback were not stated.
- Round 2 fix: The section states `VmbFeaturePersistNoLUT`, the three module flags, 10 load iterations, and the readback limit. Codex accepts these parts.
- Round 3 recheck finding, confirmed by the coordinator: The remaining load check uses the part A log check. That check can read the log before the driver tries the load (i19).
- Expected change: Apply the i19 wait to the settings file check.

### i26. `Feed` and the worker share a subscription that ic2 gives to `Feed` alone

- Round 1 finding: The section shared the subscription between the worker and `Feed`.
- Round 2 recheck finding: An explicit close and the destructor posted two releases. A move assignment into a live `Feed` replaced its subscription with no close.
- Round 3 fix (`fix-claude-r2`): A `released` flag under the link mutex, a lease set keyed by link, and a move assignment that closes the destination first (`claude/sections/control-plane.md:213-241`). Tests `FeedCloseThenDestroy` and `FeedMoveAssignIntoLive` (`claude/sections/testing.md:265-266`).
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

### i27. `feed_open` has no caller deadline

- Resolution: Closed in round 2. `FeedOptions::deadline`, default 5000 ms, uses the same request state as `get_image` (`claude/sections/control-plane.md:47-50`, `:132-167`). The i14 check points apply to both calls.

### i31. Step 5 exit check needs the step 6 `get_image`

- Source: integrate-2.
- Round 2 finding: Four step 5 tests called `get_image`, which step 6 adds.
- Round 3 fix (`fix-claude-r2`): A step column in the controller test tables. The four tests use `feed_open` only. `ShutdownWakesGetImage` moves to step 6 (`claude/sections/testing.md:148`, `:255-262`, `claude/sections/implementation-sequence.md:27`, `:149-153`).
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

## Register amendments closed by the coordinator

### i12, i28, i29

Closed in round 1. See the round 1 text in v2 section 4.4.

### i32. Register text for the accepted data-plane fixes

- Source: `claude/rechecks/round-1.md`, section "Register text that the fixes need", items 1 to 10.
- Resolution: Closed in round 2. v2 section 4.4 records the text.

### i33. Register text for the accepted Claude round 1 fixes

- Source: `claude/fixes/round-1.md`, section "Register text that these fixes need", items 1 to 10.
- Resolution: Closed in round 2 for the accepted items. v2 section 4.4 records them.
- Waiting items: d19 item 5 and ic2 `Feed` with `LeaseLink` are now adopted through i34, in their round 2 form. ic6 item 3 still waits for i19.

### i34. Register text for the accepted Claude round 2 fixes

- Source: `claude/fixes/round-2.md`, section "Register text that these fixes need", items 1 to 10.
- Resolution: Closed in round 3 for the items whose issues are Closed, and for the accepted part of i15. v2 section 4.4 records the text:
  1. d26 item 2: the deadline also covers the acceptance of the first frame, with a check before each gateway call (item 1, i14).
  2. d26 item 4: the caller checks the deadline after each frame that `take` returns (item 2, i14).
  3. d26: `FeedOptions::deadline` covers the queue wait (item 3, i14, i27).
  4. d19 item 5: one confirmation stop for each change signal. Only a successful one clears `kWedged` (item 4, i18).
  5. ic2 `Feed`: the `LeaseLink` with `released`, the lease set by link, the move assignment rule, and `kFeedClosed` from an empty `Feed` (item 5, i26).
  6. ic3 item 4.3: `close_admission` after an expiry before `stream_start` (item 6, i14).
  7. ic3: the rule for frames of an epoch whose start is pending (item 7, i17).
  8. ic4 stop order step 1: shutdown before `start` on the calling thread (item 8, accepted part of i15).
  9. ic5: the `kFeedClosed` and `kInvalidArgument` rows for `start` (item 9, accepted part of i15).
- Waiting items: the ic4 join rule and the `kStopped` transition (item 8, i15), and ic6 item 3 (item 10, i19 and i25). `integrate-4` adopts them after the fixes.
- Limit: the coordinator did not rewrite `register.md` in this round. v2 section 4.4 is the record until the next register write.

## Issues for Logan

### i30. The d20 dispute verdicts disagree

- Source: `claude/disputes/d20-verdict.md`, `codex/disputes/d20-verdict.md`, register d20.
- Finding: The Claude verdict keeps `use_ros_time: false` and fills `host_stamp_ns` from the DDS source timestamp, with an optional device stamp. The Codex verdict sets `use_ros_time: true` and fills one `host_stamp_ns` from the header.
- Status: For Logan, question L1. The sections use the Codex verdict as a working assumption. The cost to reverse is low (register d20). Rounds 2 and 3 changed nothing.

## Notes for the prose pass

These notes change no substance, so they are not issues.

1. The data-plane section cites `claude/sections/testing.md:149-154` for the `rtt` mode (`codex/sections/data-plane.md:166`). The Claude round 2 and round 3 fixes moved that text. The `rtt` row is now at `claude/sections/testing.md:296`.

## Tasks emitted in round 1

| Task | Template | Tool | Issues | Depends on |
|---|---|---|---|---|
| `fix-codex-r1` | fix | codex | i1 to i9 | none |
| `recheck-claude-r1` | recheck | claude | i1 to i9 | `fix-codex-r1` |
| `fix-claude-r1` | fix | claude | i10, i11, i13 to i27 | `fix-codex-r1` |
| `recheck-codex-r1` | recheck | codex | i10, i11, i13 to i27 | `fix-claude-r1` |
| `integrate-2` | integrate | claude | all | the four tasks above. It blocks `prose`. |

## Tasks emitted in round 2

| Task | Template | Tool | Issues | Depends on |
|---|---|---|---|---|
| `fix-claude-r2` | fix | claude | i14, i15, i17, i18, i19, i21, i22, i25, i26, i31 | none |
| `recheck-codex-r2` | recheck | codex | the same | `fix-claude-r2` |
| `integrate-3` | integrate | claude | all | the two tasks above. It blocks `prose`. |

## Tasks emitted in round 3

| Task | Template | Tool | Issues | Sections | Depends on |
|---|---|---|---|---|---|
| `fix-claude-r3` | fix | claude | i15, i19, i25 | control-plane, bring-up, testing, implementation-sequence | none |
| `recheck-codex-r3` | recheck | codex | i15, i19, i25 | the same | `fix-claude-r3` |
| `integrate-4` | integrate | claude | all | | the two tasks above. It blocks `prose`. |

1. Codex owns no open issue, so this round emits no Codex fix and no Claude recheck.
2. No dispute task. The i14 disagreement is settled. For i15, i19, and i25, the fix accepted each finding, and the recheck found a gap that remains. No planner rejects a finding, so no disagreement exists to dispute.
3. i30 stays with Logan. A dispute already ran on d20.

## Camera requests

No draft, review, fix, or recheck task wrote a camera request. The files in `claude/camera-requests/` and `codex/camera-requests/` come from the trace and positions tasks, and c1 to c3 answered them. This round accepts no camera check. The i19 order of the load and the `Initialization done!` line comes from the driver source, so a camera check would only confirm it.
