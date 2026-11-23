# Round 4 fixes to the Claude sections

Round 4. Checkpoint `5851f35`. Claude answers the issue i15 in task `fix-claude-r4`.

Planning paths are relative to `docs/architecture/image-acquisition-planning/`. Line numbers in `claude/sections/` and `claude/source-tree.md` are in the new files of this task. Other line numbers are at the checkpoint. Project code citations are `path:line` from the worktree root.

## Summary

| Id | Result | Sections changed |
|---|---|---|
| i15 | Fixed | control-plane, testing, implementation-sequence, source tree |

Result: 1 Fixed, 0 Rejected. The finding is correct on the evidence. The error-vocabulary section does not change, because `kFeedClosed` is already the `start` result after a shutdown. The bring-up section does not change.

## i15. Fixed

After a successful `init`, `start` now returns `kFeedClosed` if it reads `kStopped`. One table gives the `start` action and result for each init result and each lifecycle value that `start` can read. A new test forces the order in which the join owner sets `kStopped` before `start` reads the init result.

### Check of the finding

1. `[F]` At the checkpoint, `start` steps 5 and 6 cover a successful `init` only with `kStarting` or `kStopping` (`claude/sections/control-plane.md:213-214`, at the checkpoint). No step covers `kStopped`.
2. `[F]` At the checkpoint, a `shutdown()` in `kStarting` sets `kStopping`, moves the thread object out, and joins (`claude/sections/control-plane.md:220`, at the checkpoint). The join owner sets `kStopped` after its join returns (`:192`, `:198`). It needs nothing from `start`.
3. `[F]` At the checkpoint, `start` step 2 waits for the init result, and the worker notifies after it records it (`claude/sections/control-plane.md:210`, at the checkpoint). The worker then sees the stop request at the top of its first loop and exits (`:205`, `:214`). Nothing makes `start` get the lifecycle mutex before B sets `kStopped`. So `start` can read "succeeded" and `kStopped`.
4. `[F]` At the checkpoint, `ShutdownFromInitWithWaiter` starts B only after `stream_stop` begins, and it states that A usually wakes first (`claude/sections/testing.md:300-311`, at the checkpoint). No test forces the order of item 3.

The finding is therefore correct. In "What changed", items 1 to 3 make expected change 1. Items 7, 10, and 11 make expected change 2. Items 12 and 15 make expected change 3.

### What changed

Control-plane section:

1. `start` step 5 now reads the init result and the lifecycle value in the locked section that ends the step 3 wait. It then acts by the new table "`start` after the init result" (`claude/sections/control-plane.md:221`, `:223-232`). The old steps 4 to 6 are now rows of that table.
2. The table row "Succeeded, `kStopped`" runs the stop wait and returns `kFeedClosed` (`claude/sections/control-plane.md:232`). This is expected change 1. The row "Failed, `kStopped`" makes the old init failure path explicit, with no change of behavior (`:229`).
3. "Rules for the table" (`claude/sections/control-plane.md:234-241`). Rule 1 proves from the transition table that `start` can read only `kStarting`, `kStopping`, or `kStopped` in step 5. Rule 2 adds a debug assertion for that set. Rule 4 states why a successful `init` gives `kFeedClosed` and not success after a shutdown. Rule 5 states that in `kStopped` the worker has exited and has completed each queued request. Rule 6 states that each result other than success comes after `kStopped`.
4. The stop wait now states that in `kStopped` it returns with no block, because the object is gone and the predicate is already true (`claude/sections/control-plane.md:211`).
5. `start` step 1 now ends with an unlock, and step 3 locks again and waits with a predicate on the recorded init result (`claude/sections/control-plane.md:217-219`). The predicate means that a result recorded before the wait is not lost. The behavior does not change, because the checkpoint step 2 wait also left the mutex free for the worker.
6. Overlap case 3 walks through the i15 order (`claude/sections/control-plane.md:251`, `:255`).
7. New step 2 runs the start test hook (`claude/sections/control-plane.md:218`). New subsection "Start test hook" (`claude/sections/control-plane.md:257-280`). `detail::ControllerTestAccess::set_before_init_wait` sets one private `std::function<void()>`. The hook is empty in production. It runs with no controller lock held, so a blocked hook blocks only `start`.
8. The header sketch forward-declares `detail::ControllerTestAccess` and names it as a friend (`claude/sections/control-plane.md:29-32`, `:110-111`). Interface note 8 states that it is the only test seam in the controller (`:124`).
9. The `start` comment in the header sketch states that a `shutdown()` during `init` gives `kFeedClosed` also if `init` succeeded (`claude/sections/control-plane.md:97`).

Testing section:

10. New text on the start test hook, after `WorkerExitMark` (`claude/sections/testing.md:128-133`). The test files table names the private header (`:34`).
11. New test `Controller.ShutdownJoinedBeforeStartReads`, step 5 (`claude/sections/testing.md:284`, `:321-342`). This is expected change 2. The hook holds A at `start` step 2. B calls `shutdown()` in `kStarting`, becomes the join owner, and returns with `exited` true while A is still held. The test then opens the gate. `start` must return `kFeedClosed` within 100 ms. "Why the order is exact" gives the four reasons that the order is forced, not left to the scheduler (`:335-340`).
12. The coverage table row for ic2 and ic4 names the new test (`claude/sections/testing.md:483`). This is expected change 3, coverage part.
13. The `ShutdownFromInitWithWaiter` note now states that it leaves the order to the scheduler, and names the new test that forces the other order (`claude/sections/testing.md:319`).
14. The timing assumption now covers four repeated lifecycle tests, about 8 s in total (`claude/sections/testing.md:344`). The step 7 limit of 30 s for the suite does not change.

Implementation-sequence section:

15. Step 5 exit check 1.4 names `ShutdownJoinedBeforeStartReads` (`claude/sections/implementation-sequence.md:158`). This is expected change 3, step part.
16. Step 5 files add `src/acquisition_support/controller_test_access.hpp`, the friend in the header, the `start` table, and the start test hook (`claude/sections/implementation-sequence.md:134-137`). A new paragraph states that the test target adds `src/` to its private include path, and that the installed package does not carry the header (`:150`).

Source tree:

17. New row for `src/acquisition_support/controller_test_access.hpp`. The rows for the header, `src/acquisition_controller.cpp`, the controller test, and `CMakeLists.txt` name the seam, the `start` table, and the include path (`claude/source-tree.md:15-18`, `:32`, `:36`).

### Evidence

1. `[F]` In the new rules, `start` reads the lifecycle value once, in step 5. The transition table allows only these moves after step 1: `kStarting` to `kRunning` by `start`, `kStarting` to `kStopping` by `shutdown()`, and `kStopping` to `kStopped` by the join owner (`claude/sections/control-plane.md:193-200`). `start` makes no move before step 5. So the value is `kStarting`, `kStopping`, or `kStopped`, and the table has a row for each with each init result (`:227-232`).
2. `[F]` Join rule 5 states that `kStopped` means that the worker has exited, or that no worker was made (`claude/sections/control-plane.md:208`). `start` step 1 made a worker. So in the "Succeeded, `kStopped`" row the worker has exited, and `start` has nothing to join.
3. `[F]` The worker shutdown steps complete each queued request with `kFeedClosed` before the worker exits (`claude/sections/control-plane.md:284`, step 1). So `kFeedClosed` from `start` matches what each queued caller gets.
4. `[F]` The C++ thread constructor synchronizes with the start of the new thread (C++17 [thread.thread.constr]). The test sets the hook before it makes thread A, so A reads the set value with no lock.
5. `[F]` In the new test, B returns from `shutdown()` only after its join returns and it sets `kStopped` (join rule 3). `WorkerExitMark` sets `exited` before any join of the worker returns (`claude/sections/testing.md:124`). The worker records the init result before it reaches its first loop. So when B returns with `exited` true, the init result is success and the value is `kStopped`. A is still in the hook, so A has not read either value. This is the exact order that the finding names.
6. `[F]` With the checkpoint rules, no step gives a result for that order. The new test requires `kFeedClosed` within 100 ms after the gate opens. Success fails the check, and no return fails it at the limit.
7. `[F]` The package installs only the headers under `include/` (`src/venimapping_camera/CMakeLists.txt:58-63`). The new seam header is under `src/acquisition_support/`, so a consumer outside the package cannot include it.

### Why a hook and not a timing test

1. `start` wakes when the worker records the init result. The worker then needs about 20 ms or more to run its shutdown steps and exit. A test with no hook can only make the i15 order likely, for example with a long `stream_stop` delay and a busy start thread. It cannot make the order certain.
2. The hook gives one point with no lock held, before the step 3 lock. The test holds `start` there and lets B finish. The result is the same on each run.
3. The hook adds one check of an empty `std::function` to `start` in production. It adds no lock and no thread.

## Register text that this fix needs

This amendment makes the register match the fixed sections. `integrate-5` owns it. It replaces the waiting i35 item 3.

1. ic4 or ic5: "A `start` that fails in `init`, or that sees a shutdown before it handles the init result, returns only after the worker has exited. After a successful `init`, `start` returns `kFeedClosed` if the lifecycle value is `kStopping` or `kStopped`, and success only if it is still `kStarting`." (i15)
2. ic7: "The controller has one test seam, `detail::ControllerTestAccess`, in a private header. It sets a hook that `start` runs with no lock held, before it waits for the init result. The hook is empty in production." (i15)
