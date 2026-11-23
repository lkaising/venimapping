# Round 3 fixes to the Claude sections

Round 3. Checkpoint `ff1b533`. Claude answers the issues i15, i19, and i25 in task `fix-claude-r3`.

Planning paths are relative to `docs/architecture/image-acquisition-planning/`. Line numbers in `claude/sections/` and `claude/source-tree.md` are in the new files of this task. Other line numbers are at the checkpoint. Project code citations are `path:line` from the worktree root. `driver:` is from the driver root. `ros:` is from the ROS source root.

## Summary

| Id | Result | Sections changed |
|---|---|---|
| i15 | Fixed | control-plane, testing, implementation-sequence, source tree |
| i19 | Fixed | bring-up, testing, implementation-sequence, source tree |
| i25 | Fixed | bring-up |

Result: 3 Fixed, 0 Rejected. Each finding is correct on the evidence. The error-vocabulary section does not change, because no return value changes.

## i15. Fixed

Only the join owner sets `kStopped`, and each other thread that needs the worker to exit waits for that transition.

What changed:

1. New table "Lifecycle transitions" (`claude/sections/control-plane.md:183-192`). It lists each allowed transition and the thread that makes it. The only way out of `kStopping` is the join owner after its join returns (`:192`).
2. New "Join rules" 1 to 6 (`claude/sections/control-plane.md:194-201`). Rule 3: after its join returns, the join owner sets `kStopped` and notifies all waiters. Rule 4: a thread that did not get the thread object waits for `kStopped` with a predicate. Rule 5: so `kStopped` means that the worker has exited, or that no worker was made.
3. Rule 2: the worker never becomes the join owner. A thread compares its id with the recorded worker id. The id stays recorded after another thread moves the object out, so a `shutdown()` inside `WorkerInit` never waits for itself.
4. New "stop wait", the one step that `start` and `shutdown()` share: take the object and join, or wait for `kStopped` (`claude/sections/control-plane.md:203`).
5. `start` step 4 replaces the old step 3. After an init failure, `start` sets `kStopping` and runs the stop wait. It no longer sets `kStopped` itself (`claude/sections/control-plane.md:212`). This closes recheck item 1.
6. `start` step 6 replaces the old step 5. After a successful init with `kStopping`, `start` runs the stop wait, so the join owner sets `kStopped` (`claude/sections/control-plane.md:214`). This closes recheck item 2.
7. `shutdown()` step 1 on the worker now sets `kStopping` with the flag. Step 4 in `kStopping` runs the stop wait instead of a plain wait. The object can still be in the controller after a `shutdown()` from `WorkerInit` (`claude/sections/control-plane.md:218`, `:221`).
8. "The two overlap cases that the rules close" walks through both recheck cases (`claude/sections/control-plane.md:224-227`).
9. The stop request is a flag in the request queue, set under the queue mutex. The worker waits with a predicate that includes it, so the request after `init` is not lost (`claude/sections/control-plane.md:205`).
10. Two smaller additions. The `start` comment in the header sketch states that a failed or shut-down start returns only after the worker exits (`claude/sections/control-plane.md:94`). Shutdown rule 3 states the working assumption that `WorkerInit` returns in bounded time (`:241`).
11. New test helper `WorkerExitMark`. It is a `thread_local` guard that sets a flag at worker thread exit, after a delay. It needs no hook in the controller (`claude/sections/testing.md:113-127`). The fake gateway log adds each entry when the call starts (`claude/sections/testing.md:110`).
12. New test `Controller.InitFailureWithShutdown` for expected change 3. B owns the join before `init` fails. `start` and a later `shutdown()` on C must each return with `exited` true (`claude/sections/testing.md:275`, `:285-298`).
13. New test `Controller.ShutdownFromInitWithWaiter` for expected change 4. `WorkerInit` calls `shutdown()` and succeeds. A second `shutdown()` on B must return within 1000 ms, with `exited` true. Both join orders must pass (`claude/sections/testing.md:276`, `:300-311`).
14. `Controller.StartShutdownOverlap` now checks `exited` at each return. Its repeat count drops from 100 to 20, so the three repeated tests fit in about 7 s. That keeps the step 7 limit of 30 s for the suite (`claude/sections/testing.md:274`, `:313`).
15. Implementation step 5 lists the two new tests and the new lifecycle parts (`claude/sections/implementation-sequence.md:135`, `:155`). The source tree describes the join owner, the stop request, and `WorkerExitMark`.

Evidence:

1. `[F]` The checkpoint `start` step 3 set `kStopped` after the join rule, also when another thread held the object (`claude/sections/control-plane.md:182`, `:188`, at the checkpoint). The checkpoint `shutdown()` step 3 let a call that did not get the object wait for `kStopped`. Step 4 let a call in `kStopping` wait for it too (`:196-197`). So a waiter could return while the worker still ran.
2. `[F]` The checkpoint `shutdown()` on the worker only set the flag (`claude/sections/control-plane.md:194`, at the checkpoint). The checkpoint `start` step 5 joined but set no `kStopped` (`:190`). A waiter in `shutdown()` step 3 had no transition to wake it.
3. `[F]` In the new rules, exactly one transition leaves `kStopping`, and only the join owner makes it, after `join()` returns (`claude/sections/control-plane.md:192`, `:198`). `join()` returns only after the worker thread completes. So no call that waits for `kStopped` returns before the worker exits.
4. `[F]` Three paths enter `kStopping` with a worker: `start` step 4, and `shutdown()` steps 1 and 3. A stop wait follows each one. After `start` step 4, `start` runs it. After `shutdown()` step 3, the same caller runs it. After `shutdown()` step 1 on the worker, `start` step 4 or 6 runs it. So one thread always takes the object, and `kStopped` always comes.
5. `[F]` C++ destroys `thread_local` objects at thread exit. The completion of the thread synchronizes with the return of `join()` (C++17 [basic.start.term], [thread.thread.member]). So `WorkerExitMark` sets `exited` before any join of the worker returns. With the checkpoint rule, `start` returned in recheck case 1 before the mark delay ended, and the test reads `exited` as false.

## i19. Fixed

Each log check now waits for `Initialization done!` in that log, with a 60 s limit. A missing line at the limit fails the check.

What changed:

1. New list "The init line" with six items (`claude/sections/bring-up.md:102-109`). It states where the driver tries the load, where it logs `Initialization done!`, and why the two lines keep their order.
2. New "init wait" command with its rules (`claude/sections/bring-up.md:111-119`). `timeout 60` runs a `grep -qF "Initialization done!"` loop on one log. A status other than 0 fails the check. The 60 s limit is a working assumption.
3. Part A now has 16 steps (`claude/sections/bring-up.md:203-220`). Steps 2, 7, and 14 run the init wait after each launch. Step 3 is the control `grep`, after the step 2 wait. Step 15 is the final `grep` on `driver_a.log` and `driver_b.log`, after the step 14 wait.
4. Part A note 2 states why the waits come before each `grep` (`claude/sections/bring-up.md:225`). Part B note 4 states that part B runs on the step 13 driver, after its init wait (`:248`).
5. Implementation step 1 exit check 3 now names steps 1 to 16. It requires status 0 from each init wait before the `grep` or CLI step that follows it. The final `grep` runs after the init wait on `driver_b.log` (`claude/sections/implementation-sequence.md:64`, `:73`). Step 8 exit check 1 names the init waits (`:197`).
6. Tier 4 check 2, the settings load check, runs the init wait before its `grep` (`claude/sections/testing.md:395`, `:411`). Implementation step 9 states the same (`claude/sections/implementation-sequence.md:209`). That check also had the timing gap, so the fix covers it.

Evidence:

1. `[F]` The node constructor runs `initialize_camera` at `driver:vimbax_camera/src/vimbax_camera_node.cpp:97`. That function reads `settings_file`, tries the load, and logs a failed load before it returns (`:390-400`).
2. `[F]` The node logs `Initialization done!` through `RCLCPP_INFO` at `driver:vimbax_camera/src/vimbax_camera_node.cpp:134`. That line comes after each init step at `:85-131`. A search of the driver source finds that text only at `:134`.
3. `[F]` rcutils sends each severity to one stream, stderr unless `RCUTILS_LOGGING_USE_STDOUT` is 1 (`ros:ros2/rcutils/src/logging.c:659-674`). So the failed-load line leaves the driver before the init line, on the same stream.
4. `[A]` `launch` and `tee` keep the line order of one stream. Part A steps 1 to 4 test this. The control launch log must hold the failed-load line when it holds the init line.
5. `[F]` If the camera does not open, the driver logs a fatal line and calls `rclcpp::shutdown()` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:375-382`). The init line then never appears, and the init wait fails the check. A missing camera cannot pass the check.
6. `[F]` The driver also runs `initialize_camera(true)` on a reconnect (`driver:vimbax_camera/src/vimbax_camera_node.cpp:561-566`). Part A makes no cable change, so the one load attempt of each launch comes before its init line.

## i25. Fixed

The settings file scope text now uses the init wait. The load check that i25 depends on is the i19 part A check, so the i19 fix applies to it.

What changed:

1. The paragraph after the init wait states that the rig check reads the failed-load line after the init wait. It therefore sees the load result of each launch (`claude/sections/bring-up.md:121`).
2. The scope items and the readback limit from round 2 stay the same (`claude/sections/bring-up.md:86-93`). `recheck-codex-r2` accepted them.

Evidence: the i19 evidence. `[F]` The driver uses `VmbFeaturePersistNoLUT`, the three module flags, and 10 load iterations for the same load (`driver:vimbax_camera/src/vimbax_camera.cpp:1358-1367`). That load runs inside `initialize_camera`, before the init line.

## Register text that these fixes need

These amendments make the register match the fixed sections. `integrate-4` owns them. They replace the waiting i34 items 8 and 10.

1. ic4 stop order step 1, join rule: "One thread moves the worker `std::thread` object out under the lifecycle mutex and joins. After its join returns, that thread alone sets `kStopped` and notifies all waiters. Each other `start` or `shutdown()` that needs the worker to exit waits for `kStopped`. The worker never joins and never waits." (i15)
2. ic4 stop order step 1, worker thread: "`shutdown()` on the worker sets the shutdown flag and `kStopping`, posts the stop request, and returns." (i15)
3. ic4 or ic5: "A `start` that fails in `init`, or that sees shutdown during `init`, returns only after the worker has exited." (i15)
4. ic6 item 3: the bring-up rig check adds the part A control launch, the readback before the reopen, and the `grep -F` match anywhere in the line. Before each log check, it adds the init wait for `Initialization done!` with a 60 s limit, and a missing line fails the check. (i19, i25)
