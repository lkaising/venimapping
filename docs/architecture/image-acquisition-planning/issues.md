# Issues for the image acquisition design

Round 5. Checkpoint `6a6dfb2`. The coordinator wrote this file in task `integrate-5`. Round 1 wrote the first version at checkpoint `8d2c760`. Round 2 wrote the second version at checkpoint `ecba565`. Round 3 wrote the third version at checkpoint `fbebe85`. Round 4 wrote the fourth version at checkpoint `d423658`.

## How to read this file

1. Each issue has an id, `i1` to `i36`. An id is never reused.
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
   - `fix-codex-r1` is `codex/fixes/round-1.md`. `fix-claude-rN` is `claude/fixes/round-N.md`, for N from 1 to 4.
   - `recheck-claude-r1` is `claude/rechecks/round-1.md`. `recheck-codex-rN` is `codex/rechecks/round-N.md`, for N from 1 to 4.
   - "integrate-2" to "integrate-5" mark a problem that the coordinator found while it built v2.
5. Paths are relative to `docs/architecture/image-acquisition-planning/`, except `path:line` citations of project code, which are relative to the worktree root. Line numbers in the Claude and Codex sections are at checkpoint `6a6dfb2`, unless an entry names another checkpoint.
6. Where one finding appears in both reviews, this file keeps one issue and lists both sources.

## Neutrality check

The coordinator runs on Claude. In round 5, the only input is a Claude fix that a Codex recheck accepts. An accept of a Claude fix is the case where a Claude coordinator could pass a defect with no check. So the coordinator checked the fix against the section text and the project code, and it did not rely on the recheck alone.

Check of the i15 fix:

1. `start` now reads the init result and the lifecycle value in one locked section, at the end of the step 3 wait (`claude/sections/control-plane.md:219`, `:221`).
2. The table "`start` after the init result" has six rows, one for each init result and each value `kStarting`, `kStopping`, and `kStopped`. The row "Succeeded, `kStopped`" returns `kFeedClosed` (`claude/sections/control-plane.md:225-232`). This is expected change 1.
3. The transition table allows no other value at step 5. Only `start` leaves `kStarting` for `kRunning`, a `shutdown()` or a failed `init` gives `kStopping`, and only the join owner gives `kStopped` (`claude/sections/control-plane.md:193-200`, `:236`). No transition goes back.
4. In `kStopped`, the stop wait returns with no block, because the thread object is gone and the predicate is already true (`claude/sections/control-plane.md:211`). So the new row cannot hang.
5. The worker completes each queued request with `kFeedClosed` before it exits (`claude/sections/control-plane.md:284`). So the `start` result matches the result of each queued caller.
6. `Controller.ShutdownJoinedBeforeStartReads` holds `start` in the hook with no lock, lets thread B join and set `kStopped`, and checks `start_returned` false before it opens the gate (`claude/sections/testing.md:321-342`). This forces the order of the round 4 finding. It does not depend on the scheduler. This is expected change 2.
7. Implementation step 5 exit check 1.4 and the coverage row for ic2 and ic4 name the test (`claude/sections/implementation-sequence.md:158`, `claude/sections/testing.md:483`). This is expected change 3.
8. The hook header is under `src/acquisition_support/`. The package installs only `include/` (`src/venimapping_camera/CMakeLists.txt:58-63`). So the seam does not reach an installed consumer.

The coordinator found no new defect in the fix. The fix adds a test seam that no reviewer asked for. It is one private `std::function` member with one friend class, so it changes no public behavior. The coordinator records it as register text in i36 and opens no issue on it.

The data-plane, error-vocabulary, and bring-up sections did not change in round 5. No finding was softened or dropped. Codex owns no open finding.

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
| i15 | r-codex-6, recheck-codex-r1, recheck-codex-r2, recheck-codex-r3 | claude | control-plane, testing, implementation-sequence | Major | Closed | Round 1: opened. Rounds 2 to 4: fixed, Codex recheck reopened. Round 5: fixed with the `start` table and the start test hook, Codex recheck accepted. |
| i16 | r-codex-7 | claude | control-plane, testing | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i17 | r-codex-8, recheck-codex-r1 | claude | control-plane, testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with the pending-epoch rule, Codex recheck accepted. |
| i18 | r-codex-9, recheck-codex-r1 | claude | control-plane, error-vocabulary, testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with one confirmation stop, Codex recheck accepted. |
| i19 | r-codex-10, N6, recheck-codex-r1, recheck-codex-r2 | claude | bring-up, testing, implementation-sequence | Major | Closed | Round 1: opened. Rounds 2 and 3: fixed, Codex recheck reopened. Round 4: fixed with the init wait, Codex recheck accepted. |
| i20 | r-codex-11 | claude | testing, implementation-sequence | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i21 | r-codex-12, recheck-codex-r1 | claude | testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with one source-time interval, Codex recheck accepted. |
| i22 | r-codex-13, recheck-codex-r1 | claude | testing | Major | Closed | Round 1: opened. Round 2: reopened. Round 3: fixed with take hooks, Codex recheck accepted. |
| i23 | r-codex-14 | claude | error-vocabulary | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i24 | r-codex-15 | claude | implementation-sequence | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i25 | r-codex-16, N7, recheck-codex-r1, recheck-codex-r2 | claude | bring-up | Minor | Closed | Round 1: opened. Rounds 2 and 3: fixed, Codex recheck reopened on the load check. Round 4: fixed with the i19 init wait, Codex recheck accepted. |
| i26 | r-codex-17, r-claude mismatch 6, recheck-codex-r1 | claude | control-plane, testing | Blocking | Closed | Round 1: opened. Round 2: reopened on double release. Round 3: fixed with the `released` flag, Codex recheck accepted. |
| i27 | N4 | claude | control-plane, error-vocabulary, testing | Minor | Closed | Round 1: opened. Round 2: adopted, Codex recheck accepted. |
| i28 | N3, r-claude mismatch 10, r-codex mismatch 5 | coordinator | register ic5 | Minor | Closed | Round 1: closed. |
| i29 | N8 | coordinator | register ic4 | Minor | Closed | Round 1: closed. |
| i30 | Verdicts, register d20 | Logan | data-plane, bring-up, testing | Major | For Logan | Round 1: verdicts disagree, question L1. Rounds 2 to 5: no change. |
| i31 | integrate-2 | claude | implementation-sequence, testing | Minor | Closed | Round 2: opened by the coordinator. Round 3: fixed, Codex recheck accepted. |
| i32 | recheck-claude-r1 register list | coordinator | register ic1, ic2, ic3, ic7, ic8, d24 | Minor | Closed | Round 2: opened and closed. v2 §4.4 records the text. |
| i33 | fix-claude-r1 register list | coordinator | register d18, d22, d26, ic3, ic4, ic5 | Minor | Closed | Round 2: opened and closed for the accepted fixes. Round 3: i34 adopts two of the three waiting items. Round 4: i35 adopts the third. |
| i34 | fix-claude-r2 register list | coordinator | register d19, d26, ic2, ic3, ic4, ic5 | Minor | Closed | Round 3: opened and closed for the accepted fixes. Round 4: i35 replaces the two waiting items. |
| i35 | fix-claude-r3 register list | coordinator | register ic4, ic5, ic6 | Minor | Closed | Round 4: opened and closed for items 1, 2, and 4. Round 5: i36 item 1 replaces the waiting item 3. |
| i36 | fix-claude-r4 register list | coordinator | register ic4, ic5, ic7 | Minor | Closed | Round 5: opened and closed. v2 §4.4 records both items. |

Counts after round 5: 0 Open, 35 Closed, 1 For Logan. This round closed 2 issues: i15 and the new register issue i36.

No issue is Open, so this round adds no task. The prose pass starts next.

## Issues on the data-plane section (owner codex)

All nine issues are Closed. Each fix is in `codex/sections/data-plane.md` at checkpoint `5bb39db`. `recheck-claude-r1` accepted each one. The section did not change in rounds 3 to 5.

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
- Resolution: Closed in round 2. The fallback calls `close_admission()` and runs the full start sequence. Each `open_admission` passes the bit depth (`claude/sections/control-plane.md`, "Silence, outage, and reconnect"). `ReconnectNoRestart` asserts the order and epoch 3 (`claude/sections/testing.md`, controller tables).

### i11. `TriggerSelector` write during a stream conflicts with d18 item 7

- Round 1 finding: The reconnect readback writes the selector while the driver can stream.
- Resolution: Closed in round 2. The section adopts the amended d18 item 7 and cites c2 (`claude/sections/control-plane.md`, "Configuration order and readback"). i33 records the register text.

### i12. d24 promises the first push, but the capacity-1 queue keeps the newest

- Resolution: Closed in round 1. The d24 decision reads: "The answer is a frame that the fan-out pushed to the get image subscription after it opened, with `receive_seq` greater than `frames_received` at the request." The Codex dissent for a one-shot latch is in v2 section 14.

### i13. Requests during recovery states take the normal start path

- Round 1 finding: New requests could start a stream in `kOutage` and write before a confirmed stop.
- Resolution: Closed in round 2. The table "Stream states and new requests" gives one rule per state. Corrective writes need a confirmed stop (`claude/sections/control-plane.md`, "Stream states and new requests" and "Configuration order and readback").

### i14. Get image cancellation is checked only after a pending call

- Round 1 finding: The worker checked abandonment only after a pending gateway call.
- Round 2 recheck finding: No check ran between the calls of one readback. The take loop could return a frame queued after the deadline. No rule closed admission after an expiry between `open_admission` and `stream_start`.
- Round 3 fix (`fix-claude-r2`): A check point before each gateway call, under the outcome mutex. `close_admission()` after an expiry before `stream_start`. The take loop checks the deadline before each `take` and after each frame (`claude/sections/control-plane.md:157-170`, and "Get image").
- Resolution: Closed in round 3. `recheck-codex-r2` accepts each item. The fix adopts the acceptance check that the round 2 recheck asked for, so the disagreement on item 2 is settled and needs no dispute.

### i15. No completion rule for queued requests at init failure or shutdown

- Location: `claude/sections/control-plane.md:178-288`. `claude/sections/testing.md:128-133`, `:273-344`. `claude/sections/implementation-sequence.md:131-158`.
- Round 1 finding: Queued requests had no result at init failure or shutdown, and a worker call to `shutdown` would join its own thread.
- Round 2 recheck finding: Shutdown before `start` had no path. No rule decided which thread joins when `start` and `shutdown` overlap.
- Round 3 fix (`fix-claude-r2`): A lifecycle value under one mutex. Shutdown in `kCreated` completes the queue on the calling thread. A join rule: only the thread that moves the thread object out joins. `recheck-codex-r2` accepts the shutdown before `start`.
- Round 3 recheck finding: `start` set `kStopped` while another thread still joined. After a `shutdown()` from `WorkerInit`, `start` could own the join and set no `kStopped`.
- Round 4 fix (`fix-claude-r3`): A transition table. Only the join owner leaves `kStopping`, after its join returns. A shared stop wait for `start` and `shutdown()`. The worker never joins and never waits. New tests `InitFailureWithShutdown` and `ShutdownFromInitWithWaiter`. `recheck-codex-r3` accepts the join owner rule and the worker rule.
- Round 4 recheck finding: After a successful `init`, `start` had return rules only for `kStarting` and `kStopping`. A concurrent `shutdown()` could join the worker and set `kStopped` first. No test forced this order.
- Round 5 fix (`fix-claude-r4`): `start` reads the init result and the lifecycle value in one locked section and acts by the table "`start` after the init result". The row "Succeeded, `kStopped`" returns `kFeedClosed`. A private start test hook, `detail::ControllerTestAccess::set_before_init_wait`, holds `start` with no lock. New test `ShutdownJoinedBeforeStartReads` in step 5 and in the coverage table (`claude/sections/control-plane.md:215-280`, `claude/sections/testing.md:321-342`, `:483`, `claude/sections/implementation-sequence.md:158`).
- Resolution: Closed in round 5. `recheck-codex-r4` accepts each expected change. The coordinator check is in "Neutrality check". i36 records the register text.

### i16. Bit depth comes from the first readback, and feature calls omit the module

- Resolution: Closed in round 2. The final readback decides the format check and the bit depth. Each feature call passes `FeatureModule::kRemoteDevice` (`claude/sections/control-plane.md`, "Start sequence" and "Configuration order and readback").

### i17. A failed start leaves admission open, and the no-user stop has no failure path

- Round 1 finding: A failed start left admission open, and the no-user stop had no failure path.
- Round 2 recheck finding: The section promised that an open feed never gets a frame from a failed epoch. Admission opens before `stream_start`, so the promise was false.
- Round 3 fix (`fix-claude-r2`): "Frames from an epoch whose start is pending" defines what a feed and a get image can see. New test `ConsumerDuringFailingStart`.
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

### i18. -15 can reach a caller, and a poll error can clear a live wedge

- Round 1 finding: The first error and the reconciliation result were mixed, and a poll error could clear a live wedge.
- Round 2 recheck finding: The confirmation stop was in the general failure recovery, which gave a different state from the wedge rule for the same failure.
- Round 3 fix (`fix-claude-r2`): One confirmation stop for each change signal, outside the failure recovery. Any failure keeps `kWedged`. Tests `WedgePollErrorKeepsWedge` and `WedgeConfirmMinus3`.
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

### i19. The bring-up checks do not prove that the installed values applied

- Round 1 finding: The topic check and the settings check could pass when the file did not apply.
- Round 2 recheck finding: Part A had no readback before the reopen. The log check matched only at the start of a line, so it could not fail.
- Round 3 recheck finding: Part A ran `grep` on `driver_b.log` right after the launch. The driver tries the load before it logs `Initialization done!`, so the `grep` could miss a later failed-load line.
- Round 4 fix (`fix-claude-r3`): "The init line" states the order of the load and the init line. The init wait runs `timeout 60` on a `grep -qF "Initialization done!"` loop. A status other than 0 fails the check. Part A runs it after each launch, before each `grep` or CLI step (`claude/sections/bring-up.md:102-121`, `:203-226`). Implementation steps 1, 8, and 9 and tier 4 check 2 use the same wait.
- Resolution: Closed in round 4. `recheck-codex-r3` accepts it. The coordinator confirmed the one place that logs the init line (`driver:vimbax_camera/src/vimbax_camera_node.cpp:134`).

### i20. Step 9 leaves the driver on device stamps before the wedge check

- Resolution: Closed in round 2. Tier 4 check 4 relaunches with host stamps and reads `use_ros_time`. The wedge check restores `Mono8` with the CLI and keeps one controller across the restart (`claude/sections/implementation-sequence.md`, step 9).

### i21. The outside-reader check uses a `ros2 topic hz` option that does not exist

- Round 1 finding: `ros2 topic hz` has no QoS option, and the stamp run had no rule to tell a reader gap from a driver gap.
- Round 2 recheck finding: Driver gap lines counted only after the start reply, but stamps started at the first frame. One log line could match more than one gap.
- Round 3 fix (`fix-claude-r2`): One source-time interval for each rate. Each line belongs to at most one pair. Ambiguous items make the result inconclusive.
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it. Gap fact 4 keeps the clock agreement as a working assumption with an inconclusive outcome.

### i22. Tests lack synchronization points and observation hooks

- Round 1 finding: Several tests had no hold point, no address check, a fake stamp equal to the boundary, and an undefined match timer.
- Round 2 recheck finding: `InFlightFrameSkipped` could pass with the `receive_seq <= R` skip removed, because N+1 could evict N first.
- Round 3 fix (`fix-claude-r2`): Take hooks on each fake subscription. The test waits for a second `take` and checks `taken_seqs(1) == {N}` before it injects N+1.
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

### i23. Error vocabulary rows are narrower than the behavior

- Resolution: Closed in round 2. A "Deadline stages" table, a corrective write rule, and the `transport_lost` row as the RMW `message_lost` total (`claude/sections/error-vocabulary.md:99-115`, `:134-152`). Round 3 adds the rows for i14.

### i24. The acquisition target is not installed or exported

- Resolution: Closed in round 2. Step 5 installs and exports `venimapping_camera_acquisition` and links an installed consumer. "CMake layout" gives the join rule for steps 4 and 5 (`claude/sections/implementation-sequence.md:29-40`, step 5).

### i25. The settings file scope is not stated

- Round 1 finding: The file scope and the limit of the readback were not stated.
- Round 2 fix: The section states `VmbFeaturePersistNoLUT`, the three module flags, 10 load iterations, and the readback limit. Codex accepts these parts.
- Round 3 recheck finding: The remaining load check used the part A log check, which could read the log before the driver tried the load (i19).
- Round 4 fix (`fix-claude-r3`): The scope text reads the failed-load line after the init wait (`claude/sections/bring-up.md:121`).
- Resolution: Closed in round 4. `recheck-codex-r3` accepts it.

### i26. `Feed` and the worker share a subscription that ic2 gives to `Feed` alone

- Round 1 finding: The section shared the subscription between the worker and `Feed`.
- Round 2 recheck finding: An explicit close and the destructor posted two releases. A move assignment into a live `Feed` replaced its subscription with no close.
- Round 3 fix (`fix-claude-r2`): A `released` flag under the link mutex, a lease set keyed by link, and a move assignment that closes the destination first (`claude/sections/control-plane.md`, "Subscription ownership"). Tests `FeedCloseThenDestroy` and `FeedMoveAssignIntoLive`.
- Resolution: Closed in round 3. `recheck-codex-r2` accepts it.

### i27. `feed_open` has no caller deadline

- Resolution: Closed in round 2. `FeedOptions::deadline`, default 5000 ms, uses the same request state as `get_image` (`claude/sections/control-plane.md`, "Public interface" and "Requests and deadlines"). The i14 check points apply to both calls.

### i31. Step 5 exit check needs the step 6 `get_image`

- Source: integrate-2.
- Round 2 finding: Four step 5 tests called `get_image`, which step 6 adds.
- Round 3 fix (`fix-claude-r2`): A step column in the controller test tables. The four tests use `feed_open` only. `ShutdownWakesGetImage` moves to step 6.
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
- Waiting items: d19 item 5 and ic2 `Feed` with `LeaseLink` are adopted through i34. ic6 item 3 is adopted through i35, in its round 3 form.

### i34. Register text for the accepted Claude round 2 fixes

- Source: `claude/fixes/round-2.md`, section "Register text that these fixes need", items 1 to 10.
- Resolution: Closed in round 3 for items 1 to 7 and for the accepted parts of items 8 and 9. v2 section 4.4 records the text.
- Waiting items: the ic4 join rule and the `kStopped` transition (item 8), and ic6 item 3 (item 10). `fix-claude-r3` replaces both with its own register items, so i35 handles them.

### i35. Register text for the accepted Claude round 3 fixes

- Source: `claude/fixes/round-3.md`, section "Register text that these fixes need", items 1 to 4.
- Resolution: Closed in round 4 for items 1, 2, and 4. v2 section 4.4 records the text.
- Waiting item 3: "A `start` that fails in `init`, or that sees shutdown during `init`, returns only after the worker has exited." In round 5, i36 item 1 replaces it with the form that adds the `kStopped` rule. No item of i35 waits now.

### i36. Register text for the accepted Claude round 4 fix

- Source: `claude/fixes/round-4.md`, section "Register text that this fix needs", items 1 and 2.
- Resolution: Closed in round 5. v2 section 4.4, "Contract amendments from round 5", records both items:
  1. ic4 and ic5: "A `start` that fails in `init`, or that sees a shutdown before it handles the init result, returns only after the worker has exited. After a successful `init`, `start` returns `kFeedClosed` if the lifecycle value is `kStopping` or `kStopped`, and success only if it is still `kStarting`." (i15)
  2. ic7: "The controller has one test seam, `detail::ControllerTestAccess`, in a private header. It sets a hook that `start` runs with no lock held, before it waits for the init result. The hook is empty in production." (i15)
- Limit: the coordinator did not rewrite `register.md` in this round. The file is still at the `register-final` text. v2 section 4.4 is the record of each amendment from i12 and i28 to i36.

## Issues for Logan

### i30. The d20 dispute verdicts disagree

- Source: `claude/disputes/d20-verdict.md`, `codex/disputes/d20-verdict.md`, register d20.
- Finding: The Claude verdict keeps `use_ros_time: false` and fills `host_stamp_ns` from the DDS source timestamp, with an optional device stamp. The Codex verdict sets `use_ros_time: true` and fills one `host_stamp_ns` from the header.
- Status: For Logan, question L1. The sections use the Codex verdict as a working assumption. The cost to reverse is low (register d20). Rounds 2 to 5 changed nothing.

## Notes for the prose pass

These notes change no substance, so they are not issues.

1. The data-plane section cites `claude/sections/testing.md:149-154` for the `rtt` mode (`codex/sections/data-plane.md:166`). The Claude fixes moved that text. The `rtt` row is now in the tier 3 table of `claude/sections/testing.md`, "Tier 3: driver and camera".
2. `register.md` holds the `register-final` text. v2 section 4.4 lists the amendments of rounds 1 to 5. A reader of the register alone does not see them.

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

## Tasks emitted in round 4

| Task | Template | Tool | Issues | Sections | Depends on |
|---|---|---|---|---|---|
| `fix-claude-r4` | fix | claude | i15 | control-plane, testing, implementation-sequence | none |
| `recheck-codex-r4` | recheck | codex | i15 | the same | `fix-claude-r4` |
| `integrate-5` | integrate | claude | all | | the two tasks above. It blocks `prose`. |

## Tasks emitted in round 5

None. No issue is Open, so this round writes no emit file, and the prose pass starts next.

1. No fix and no recheck task, because no issue is Open.
2. No dispute task. Each fix and recheck pair ended in an accept. i30 stays with Logan, and a dispute already ran on d20.
3. No `integrate-6` task, because this round adds no other task.

## Camera requests

No draft, review, fix, or recheck task wrote a camera request. The files in `claude/camera-requests/` and `codex/camera-requests/` come from the trace and positions tasks, and c1 to c3 answered them. This round accepts no camera check. i15 is a rule inside the controller, and a fake-based test checks it, so a camera check cannot change it.
