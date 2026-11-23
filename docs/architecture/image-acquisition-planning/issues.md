# Issues for the image acquisition design

Round 2. Checkpoint `ecba565`. The coordinator wrote this file in task `integrate-2`. Round 1 wrote the first version at checkpoint `8d2c760`.

## How to read this file

1. Each issue has an id, `i1` to `i33`. An id is never reused.
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
   - `fix-codex-r1` is `codex/fixes/round-1.md`. `fix-claude-r1` is `claude/fixes/round-1.md`.
   - `recheck-claude-r1` is `claude/rechecks/round-1.md`. `recheck-codex-r1` is `codex/rechecks/round-1.md`.
   - "integrate-2" marks a problem that the coordinator found while it built v2.
5. Paths are relative to `docs/architecture/image-acquisition-planning/`, except `path:line` citations of project code, which are relative to the worktree root. Line numbers in the Claude and Codex sections are at checkpoint `ecba565`.
6. Where one finding appears in both reviews, this file keeps one issue and lists both sources.

## Neutrality check

The coordinator runs on Claude. In round 2, the Codex recheck reopened 9 of the 17 Claude fixes. The Claude recheck accepted all 9 Codex fixes. This imbalance needs a check in both directions.

Check of the Codex reopens. The coordinator read each reopened passage in the Claude sections and each cited code line. Each reopen holds:

1. i14. The check points in `claude/sections/control-plane.md:146-149` surround whole readbacks. The 8 calls of one readback (`:279-286`) have no check between them.
2. i15. `shutdown()` "sets the shutdown flag, wakes the worker, and joins it" (`claude/sections/control-plane.md:171`). Before `start`, no worker exists, but requests can wait in the queue (`:159`).
3. i17. The section promises that "a feed that stays open never gets a frame from a failed epoch" (`claude/sections/control-plane.md:265`). Admission opens before `stream_start` (`:259-260`), and `take` returns a queued frame at once (`codex/sections/data-plane.md:100`).
4. i18. Failure recovery item 1 lists "the confirmation stop in `kWedged`" (`claude/sections/control-plane.md:369`). Items 2 to 5 then send a -3 to the outage rules and run a reconciliation stop. The wedge rule keeps `kWedged` after a failed confirmation stop (`:388`).
5. i19 and i25. The driver logs the failed load through `RCLCPP_ERROR` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:395-398`). The default console format is `"[{severity}] [{time}] [{name}]: {message}"` (`ros:ros2/rcutils/src/logging.c:89`). No console line starts with `Loading settings from file`, so the part A check cannot fail.
6. i21. The gap rules count driver gap lines only between the start reply and the stop request (`claude/sections/testing.md:253`). The probe records stamps from the first frame, about 79 ms before the reply (c1 §3.5).
7. i22. `InFlightFrameSkipped` injects N+1 right after it releases N (`claude/sections/testing.md:158`). The get image queue has capacity 1, so N+1 can evict N before the caller pulls.
8. i26. `Feed::close()` posts the lease release (`claude/sections/control-plane.md:198`). The destructor runs `close()` again (`:199`). No rule makes the release happen once. Rule 4 (`:201`) covers a move, but not a move assignment into a live `Feed`.

Check of the Claude accepts. The coordinator reread the fixed data-plane section for i1, i3, i5, and i7, which carry the most risk:

1. i1. One `fetch_add(1) + 1` on one atomic (`codex/sections/data-plane.md:124`, `:132`).
2. i3. Subscriptions hold shared pointers to the queue block and the shared state. Neither block refers to the source or the clock (`codex/sections/data-plane.md:102-106`).
3. i5. Storage and list nodes are allocated before the lock. Four holders defer the last release of each evicted or cleared frame (`codex/sections/data-plane.md:104`, `:108`). The suffix argument in `claude/rechecks/round-1.md` holds for any number of subscriptions with capacity at most 4.
4. i7. The private `stage` factory and the `friend` declaration are named (`codex/sections/data-plane.md:30`).

The coordinator found no defect in the data-plane section. The two notes in the Claude recheck, the abstract clock class and the register text, are contract text. i32 records them.

The coordinator found one new issue, i31, on a Claude section. It is a step order conflict that neither recheck covers. No finding was softened or dropped.

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
| i14 | r-codex-5, recheck-codex-r1 | claude | control-plane, error-vocabulary, testing | Major | Open | Round 1: opened. Round 2: fixed, Codex recheck reopened. Coordinator confirmed. |
| i15 | r-codex-6, recheck-codex-r1 | claude | control-plane, testing | Major | Open | Round 1: opened. Round 2: fixed, Codex recheck reopened. Coordinator confirmed. |
| i16 | r-codex-7 | claude | control-plane, testing | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i17 | r-codex-8, recheck-codex-r1 | claude | control-plane, testing | Major | Open | Round 1: opened. Round 2: fixed, Codex recheck reopened. Coordinator confirmed. |
| i18 | r-codex-9, recheck-codex-r1 | claude | control-plane, error-vocabulary, testing | Major | Open | Round 1: opened. Round 2: fixed, Codex recheck reopened. Coordinator confirmed. |
| i19 | r-codex-10, N6, recheck-codex-r1 | claude | bring-up, implementation-sequence | Major | Open | Round 1: opened. Round 2: fixed, Codex recheck reopened. Coordinator confirmed the log format. |
| i20 | r-codex-11 | claude | testing, implementation-sequence | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i21 | r-codex-12, recheck-codex-r1 | claude | testing | Major | Open | Round 1: opened. Round 2: fixed, Codex recheck reopened. Coordinator confirmed. |
| i22 | r-codex-13, recheck-codex-r1 | claude | testing | Major | Open | Round 1: opened. Round 2: fixed, Codex recheck reopened. Coordinator confirmed. |
| i23 | r-codex-14 | claude | error-vocabulary | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i24 | r-codex-15 | claude | implementation-sequence | Major | Closed | Round 1: opened. Round 2: fixed, Codex recheck accepted. |
| i25 | r-codex-16, N7, recheck-codex-r1 | claude | bring-up | Minor | Open | Round 1: opened. Round 2: fixed, Codex recheck reopened on the i19 log check. |
| i26 | r-codex-17, r-claude mismatch 6, recheck-codex-r1 | claude | control-plane, testing | Blocking | Open | Round 1: opened. Round 2: ownership fixed, Codex recheck reopened on double release. |
| i27 | N4 | claude | control-plane, error-vocabulary, testing | Minor | Closed | Round 1: opened. Round 2: adopted, Codex recheck accepted. |
| i28 | N3, r-claude mismatch 10, r-codex mismatch 5 | coordinator | register ic5 | Minor | Closed | Round 1: closed. |
| i29 | N8 | coordinator | register ic4 | Minor | Closed | Round 1: closed. |
| i30 | Verdicts, register d20 | Logan | data-plane, bring-up, testing | Major | For Logan | Round 1: verdicts disagree, question L1. Round 2: no change. |
| i31 | integrate-2 | claude | implementation-sequence, testing | Minor | Open | Round 2: opened by the coordinator. |
| i32 | recheck-claude-r1 register list | coordinator | register ic1, ic2, ic3, ic7, ic8, d24 | Minor | Closed | Round 2: opened and closed. v2 §4.4 records the text. |
| i33 | fix-claude-r1 register list | coordinator | register d18, d22, d26, ic3, ic4, ic5 | Minor | Closed | Round 2: opened and closed for the accepted fixes. Three items wait. |

Counts after round 2: 10 Open, 22 Closed, 1 For Logan. This round closed 19 issues: 17 round 1 issues and the two new register issues i32 and i33.

Open issues by severity: one Blocking (i26), seven Major (i14, i15, i17, i18, i19, i21, i22), and two Minor (i25, i31). All open issues are on the Claude sections.

## Issues on the data-plane section (owner codex)

All nine issues are Closed. Each fix is in `codex/sections/data-plane.md` at checkpoint `ecba565`. `recheck-claude-r1` accepted each one.

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
- Resolution: Closed in round 2. The fallback calls `close_admission()` and runs the full start sequence. Each `open_admission` passes the bit depth (`claude/sections/control-plane.md:417-419`). `ReconnectNoRestart` asserts the order and epoch 3 (`claude/sections/testing.md:187`).

### i11. `TriggerSelector` write during a stream conflicts with d18 item 7

- Round 1 finding: The reconnect readback writes the selector while the driver can stream.
- Resolution: Closed in round 2. The section adopts the amended d18 item 7 and cites c2 (`claude/sections/control-plane.md:292-298`). The Codex recheck accepts the amendment. i33 records the register text.

### i12. d24 promises the first push, but the capacity-1 queue keeps the newest

- Resolution: Closed in round 1. The d24 decision reads: "The answer is a frame that the fan-out pushed to the get image subscription after it opened, with `receive_seq` greater than `frames_received` at the request." The Codex dissent for a one-shot latch is in v2 section 14.

### i13. Requests during recovery states take the normal start path

- Round 1 finding: New requests could start a stream in `kOutage` and write before a confirmed stop.
- Resolution: Closed in round 2. The table "Stream states and new requests" gives one rule per state. Corrective writes need a confirmed stop (`claude/sections/control-plane.md:207-226`, `:250-254`).

### i14. Get image cancellation is checked only after a pending call

- Location: `claude/sections/control-plane.md:144-151`, `:324-332`. `claude/sections/error-vocabulary.md:101-109`. `claude/sections/testing.md:159-162`.
- Round 1 finding: The worker checked abandonment only after a pending gateway call.
- Round 2 fix: One absolute deadline and one shared outcome. The worker checks before each readback, before the writes, before each match poll, before `open_admission`, and before `stream_start`.
- Round 2 recheck finding, confirmed by the coordinator:
  1. One readback is 8 gateway calls (`claude/sections/control-plane.md:279-286`), and the write list is up to 8 more. No check runs between the calls of one list. After expiry, each remaining call still runs to its own gateway timeout.
  2. Caller step 5 calls `take(deadline - now)` in a loop (`claude/sections/control-plane.md:328`). A timeout of 0 or less acts as `try_take` (`codex/sections/data-plane.md:100`). The loop can therefore return a frame that was queued after the deadline. The section keeps this on purpose (`claude/sections/control-plane.md:332`).
  3. If the deadline passes after `open_admission` and before `stream_start`, the section does not say what closes that admission.
- Expected change: Check the deadline and the outcome before each gateway call that advances the request. State what closes admission after an expiry between `open_admission` and `stream_start`. For item 2, enforce the absolute deadline when the caller accepts a frame, or keep the rule and show that it meets d26 item 4. Add tests for expiry during a readback and for a fresh frame queued after expiry.
- Disagreement note: item 2 is a disagreement between the fix and the recheck. If `fix-claude-r2` and `recheck-codex-r2` do not settle it, `integrate-3` opens a dispute on i14.

### i15. No completion rule for queued requests at init failure or shutdown

- Location: `claude/sections/control-plane.md:155-183`. `claude/sections/testing.md:197-201`.
- Round 1 finding: Queued requests had no result at init failure or shutdown, and a worker call to `shutdown` would join its own thread.
- Round 2 fix: A lifecycle table, a worker-run shutdown, a destructor rule, and four tests.
- Round 2 recheck finding, confirmed by the coordinator:
  1. Requests can queue before `start` (`claude/sections/control-plane.md:159`). Shutdown gives all queue completion to the worker (`:171-177`). Before `start`, no worker exists, so a queued caller waits until its deadline instead of getting `kFeedClosed`.
  2. The section gives no rule for a `start` and a `shutdown` that overlap. Both can try to join the worker.
- Expected change: Give shutdown before `start` a path that closes the queue and completes each waiting request with `kFeedClosed`, with no gateway call. Make one owner of the worker join when `start` and `shutdown` overlap. Test shutdown with a queued request and no worker.

### i16. Bit depth comes from the first readback, and feature calls omit the module

- Resolution: Closed in round 2. The final readback decides the format check and the bit depth. Each feature call passes `FeatureModule::kRemoteDevice` (`claude/sections/control-plane.md:248-259`, `:275-286`). `FormatCorrectionBits` checks 8 bits on the first frame (`claude/sections/testing.md:144`).

### i17. A failed start leaves admission open, and the no-user stop has no failure path

- Location: `claude/sections/control-plane.md:259-265`. `claude/sections/testing.md:170`.
- Round 1 finding: A failed start left admission open, and the no-user stop had no failure path.
- Round 2 fix: Start step 9 calls `close_admission()` at once. Each failed start or stop goes through d19, also the no-user stop.
- Round 2 recheck finding, confirmed by the coordinator: The section states that "a feed that stays open never gets a frame from a failed epoch" (`claude/sections/control-plane.md:265`). Admission opens in step 7, before `stream_start` (`:259-260`). The first frame arrives about 79 ms before the start reply (c1 §3.5). `take` returns a queued frame at once (`codex/sections/data-plane.md:100`). A consumer that waits in `take` can therefore get a frame from the failed epoch before step 9 clears the queue.
- Expected change: Define what a retained feed can see from an epoch whose start is still pending, and correct the promise. Test an active consumer during a failing recovery start.

### i18. -15 can reach a caller, and a poll error can clear a live wedge

- Location: `claude/sections/control-plane.md:365-391`. `claude/sections/testing.md:175-176`.
- Round 1 finding: The first error and the reconciliation result were mixed, and a poll error could clear a live wedge.
- Round 2 fix: Two status fields. A change signal and then a successful confirmation stop clear `kWedged`.
- Round 2 recheck finding, confirmed by the coordinator: Failure recovery item 1 includes "the confirmation stop in `kWedged`" (`claude/sections/control-plane.md:369`). Under that rule, a -3 goes to the outage rules (item 2), and another failure gets one more reconciliation stop (item 3). The wedge rule says that a failed confirmation stop keeps `kWedged` and waits for the next change signal (`:388`). The two rules give different states for the same failure.
- Expected change: Make the confirmation one stop per change signal, outside the general failure recovery. Keep `kWedged` after any failed confirmation. Assert the stop count in `WedgePollErrorKeepsWedge`.

### i19. The bring-up checks do not prove that the installed values applied

- Location: `claude/sections/bring-up.md:92`, `:170-179`. `claude/sections/implementation-sequence.md:63`.
- Round 1 finding: The topic check and the settings check could pass when the file did not apply.
- Round 2 fix: Part A makes a controlled reopen from known different values. Part B reads `settings_file`, the plugin filter, and the publisher count, and bounds the first-frame wait.
- Round 2 recheck finding, confirmed by the coordinator:
  1. Part A writes `ExposureTime` 10000.0 and `AcquisitionFrameRate` 20.0 and restarts the driver with no readback (`claude/sections/bring-up.md:172-176`). A write that did not apply makes part B pass for the wrong reason.
  2. Both exit checks fail only on a console line that starts with `Loading settings from file` (`claude/sections/bring-up.md:177`, `claude/sections/implementation-sequence.md:63`). The driver logs that text as the message of `RCLCPP_ERROR` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:395-398`). The default console line starts with `[{severity}] [{time}] [{name}]: ` (`ros:ros2/rcutils/src/logging.c:89`). The check therefore cannot fail.
- Expected change: Read back both part A values before the driver stops. In both checks, match the failed-load message anywhere in the console line.

### i20. Step 9 leaves the driver on device stamps before the wedge check

- Resolution: Closed in round 2. Tier 4 check 4 relaunches with host stamps and reads `use_ros_time`. The wedge check restores `Mono8` with the CLI and keeps one controller across the restart (`claude/sections/testing.md:271-312`, `claude/sections/implementation-sequence.md:200-205`).

### i21. The outside-reader check uses a `ros2 topic hz` option that does not exist

- Location: `claude/sections/testing.md:243-265`.
- Round 1 finding: `ros2 topic hz` has no QoS option, and the stamp run had no rule to tell a reader gap from a driver gap.
- Round 2 fix: A RELIABLE `ros2 topic echo` reader, a match wait in the `stamps` mode, and gap rules.
- Round 2 recheck finding, confirmed by the coordinator: A driver gap counts only between the start reply and the stop request (`claude/sections/testing.md:253`). The probe records stamps from the first frame (`:247`), which arrives about 79 ms before the reply (c1 §3.5). A driver gap in that interval becomes an unmatched device gap, and rule 4 calls it a reader gap. The rules also let one log line match more than one device gap.
- Expected change: For each rate, use one source-time interval for the stamp pairs and for the driver log lines. Match each line at most once. Mark an ambiguous match inconclusive.

### i22. Tests lack synchronization points and observation hooks

- Location: `claude/sections/testing.md:158`.
- Round 1 finding: Several tests had no hold point, no address check, a fake stamp equal to the boundary, and an undefined match timer.
- Round 2 fix: `TestClock` with a hold, a 1 ms advance in `inject`, an intra-process address check, and named timer endpoints. Codex accepts these parts.
- Round 2 recheck finding, confirmed by the coordinator: `InFlightFrameSkipped` releases the hold on frame N and then injects N+1 (`claude/sections/testing.md:158`). The get image queue has capacity 1 and drops the oldest (`codex/sections/data-plane.md:98`). N+1 can evict N before the caller pulls. The test then passes even with the `receive_seq <= R` skip removed.
- Expected change: Add a test hook that shows when the caller has taken and skipped N. Wait for it, with a time limit, before the test injects N+1.

### i23. Error vocabulary rows are narrower than the behavior

- Resolution: Closed in round 2. A "Deadline stages" table, a corrective write rule, and the `transport_lost` row as the RMW `message_lost` total (`claude/sections/error-vocabulary.md:97-111`, `:129-146`). The deadline check points still depend on i14.

### i24. The acquisition target is not installed or exported

- Resolution: Closed in round 2. Step 5 installs and exports `venimapping_camera_acquisition` and links an installed consumer. "CMake layout" gives the join rule for steps 4 and 5 (`claude/sections/implementation-sequence.md:28-39`, `:140-153`).

### i25. The settings file scope is not stated

- Location: `claude/sections/bring-up.md:88-94`.
- Round 1 finding: The file scope and the limit of the readback were not stated.
- Round 2 fix: The section states `VmbFeaturePersistNoLUT`, the three module flags, 10 load iterations, and the readback limit. Codex accepts these parts.
- Round 2 recheck finding, confirmed by the coordinator: The remaining part, "use the driver load result in the rig check", depends on the part A log check, which cannot fail (i19 item 2).
- Expected change: Apply the i19 log check fix here.

### i26. `Feed` and the worker share a subscription that ic2 gives to `Feed` alone

- Location: `claude/sections/control-plane.md:66-79`, `:185-205`. `claude/sections/testing.md:202-203`.
- Round 1 finding: The section shared the subscription between the worker and `Feed`.
- Round 2 fix: `Feed` owns the subscription alone. A shared `LeaseLink` gives the worker a close path. Codex accepts this model.
- Round 2 recheck finding, confirmed by the coordinator:
  1. `Feed::close()` posts the lease release (`claude/sections/control-plane.md:198`). The destructor runs `close()` again (`:199`). No rule makes the release happen once. An explicit close and then destruction post two releases for one lease. The second release can drop the count of a different live lease and stop its stream.
  2. Rule 4 covers a move (`:201`). A move assignment into a live `Feed` (`:69`) replaces its subscription with no close and no release. Its old link keeps a pointer to a destroyed subscription, and its lease is never released.
- Expected change: Use the link lock so that each lease releases once. Close the destination `Feed` before a move assignment replaces its subscription. Test an explicit close followed by destruction. Test a move assignment into a live `Feed`.

### i27. `feed_open` has no caller deadline

- Resolution: Closed in round 2. `FeedOptions::deadline`, default 5000 ms, uses the same request state as `get_image` (`claude/sections/control-plane.md:45-48`, `:128-153`). The i14 check points apply to both calls.

### i31. Step 5 exit check needs the step 6 `get_image`

- Source: integrate-2.
- Location: `claude/sections/implementation-sequence.md:142`, `:148`. `claude/sections/testing.md:197-201`.
- Finding: In step 5, the header has no `get_image` and no `GetImageOptions` (`claude/sections/implementation-sequence.md:142`). The step 5 exit check lists `QueuedBeforeStart`, `InitFailure`, `Shutdown`, and `DestroyWithPendingRequest` (`:148`). Each of these tests calls `get_image` (`claude/sections/testing.md:197`, `:198`, `:200`, `:201`). Step 5 cannot pass its own exit check, which breaks the rule that each step builds alone and passes its own check (`claude/sections/implementation-sequence.md:3`).
- Expected change: Move the four cases to the step 6 exit check, or write their step 5 form with `feed_open` only.

## Register amendments closed by the coordinator

### i12, i28, i29

Closed in round 1. See the round 1 text in v2 section 4.4.

### i32. Register text for the accepted data-plane fixes

- Source: `claude/rechecks/round-1.md`, section "Register text that the fixes need", items 1 to 10.
- Resolution: Closed. The coordinator adopts each item. v2 section 4.4 records the amended contract text:
  1. ic1 item 4: immutable after `create` or after `FrameFanout` publishes it (i7).
  2. ic1 sketch: `encoding()` and `tf_frame()` return `const std::string&`. Other accessors return the field type (i6).
  3. ic2 `FrameSourceStats`: add `callback_ns_max` and `callback_ns_total` (i2).
  4. ic3 item 3.1: `receive_seq = frames_received.fetch_add(1) + 1` (i1).
  5. ic3 item 3.2: a second `steady_now()` read after the deferred releases (i2).
  6. ic3 item 3.3: the private `stage` factory replaces `ImageFrame::create` (i7).
  7. ic2 `VimbaXFrameSource` item 1: an empty namespace returns `kSourceCreateFailed` (i8).
  8. ic7 item 2: `FrameFanoutClock` is an abstract class with virtual `realtime_ns() const` and `steady_now() const`. The clock outlives `FrameFanout` (i9). The `const` form follows `TestClock` in `claude/sections/testing.md:44-49`. The data-plane section is silent on it, so no conflict exists.
  9. ic8 guarantee 10: the interval runs from the first `steady_now()` read to the read after the deferred releases (i2).
  10. d24 decision: the i12 text.
- Limit: the coordinator could not rewrite `register.md` in this round. v2 section 4.4 is the record until the next register write.

### i33. Register text for the accepted Claude fixes

- Source: `claude/fixes/round-1.md`, section "Register text that these fixes need", items 1 to 10.
- Resolution: Closed for the items whose issues are Closed or whose text the recheck accepted:
  1. d18 item 7: the i11 text (item 1).
  2. d22 item 7: the fallback calls `close_admission` and runs the start sequence (item 3, i10).
  3. d22 item 5: the stop before the writes is part of the start sequence and gives a confirmed stop (item 4, i13).
  4. d26: `FeedOptions::deadline`, default 5000 ms, with the same mechanism (item 5, i27). The queue wait part waits for i14.
  5. ic3 item 4.3: `close_admission` after a failed `stream_start` (item 7). The Codex recheck accepts this part of i17.
  6. ic4 stop order step 1: the worker makes each gateway call of the shutdown (item 8). The Codex recheck accepts this part of i15.
  7. ic5: `kDeadlinePassed` adds `feed_open`. `kFeedClosed` adds the init failure and requests queued at shutdown. `kInvalidArgument` adds a second `start` call. Item 2 adds the corrective write rule (item 9, i23).
- Items that wait for an open issue: d19 item 5 (item 2, i18), ic2 `Feed` and `LeaseLink` (item 6, i26), and ic6 item 3 (item 10, i19). `integrate-3` adopts them after the fixes.

## Issues for Logan

### i30. The d20 dispute verdicts disagree

- Source: `claude/disputes/d20-verdict.md`, `codex/disputes/d20-verdict.md`, register d20.
- Finding: The Claude verdict keeps `use_ros_time: false` and fills `host_stamp_ns` from the DDS source timestamp, with an optional device stamp. The Codex verdict sets `use_ros_time: true` and fills one `host_stamp_ns` from the header.
- Status: For Logan, question L1. The sections use the Codex verdict as a working assumption. The cost to reverse is low (register d20). Round 2 changed nothing.

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

1. Codex owns no open issue, so this round emits no Codex fix and no Claude recheck.
2. No dispute task. i14 item 2 is the only disagreement that remains after a fix and a recheck. Its effect is bounded by one wake-up of the caller thread, so one more fix round comes first. `integrate-3` opens a dispute if round 2 does not settle it.
3. i30 stays with Logan. A dispute already ran on d20.

## Camera requests

No draft, review, fix, or recheck task wrote a camera request. The files in `claude/camera-requests/` and `codex/camera-requests/` come from the trace and positions tasks, and c1 to c3 answered them. This round accepts no camera check.
