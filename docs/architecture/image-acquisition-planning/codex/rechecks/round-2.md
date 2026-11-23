# Recheck of the round 2 fixes

Checkpoint `e30bd14d6cb7607ef10fc974b8015e79257e3dd8`. Planning citations are relative to `docs/architecture/image-acquisition-planning/`. The `driver:` and `ros:` prefixes identify the local source roots.

## i14. Accept

[F] The worker checks the outcome and deadline before each readback call, corrective write, and stream call that advances the request. It checks again under the outcome mutex at delivery. If the request expires after admission opens and before `stream_start`, the worker closes admission and releases the lease. An in-flight gateway call keeps its own timeout. (`claude/sections/control-plane.md:142-165`, `:284-297`, `:328-344`, `:364-371`, `src/venimapping_camera/src/vimbax_camera_gateway.cpp:187-201`)

[F] The caller checks the clock before `take` and after it returns a frame. The late-frame test makes `take` return a fresh frame after expiry and requires `kDeadlinePassed`. Two other tests cover expiry in a readback and between admission and start. The acceptance rule meets d26 item 4. (`claude/sections/control-plane.md:386-399`, `claude/sections/error-vocabulary.md:99-114`, `claude/sections/testing.md:172-174`, `:197-208`, `register.md:543-547`)

## i15. Reopen

[F] Shutdown before `start` completes queued requests with `kFeedClosed` on the calling thread. The test checks that both callers wake and that the gateway log stays empty. (`claude/sections/control-plane.md:173-180`, `:192-198`, `claude/sections/testing.md:258`)

[F] One thread takes the join handle. On init failure, `start` still sets `kStopped` even if a concurrent `shutdown` took the handle. Another `shutdown` can then return before the worker exits. If `WorkerInit` calls `shutdown` and succeeds, `start` can own the join. That path skips the transition to `kStopped`, so a concurrent `shutdown` can wait indefinitely. (`claude/sections/control-plane.md:96-98`, `:182-206`)

1. After the join, make its owner set `kStopped` and notify all waiters.
2. If another thread owns the join, wait for that transition.
3. Test failed init during concurrent shutdown.
4. Test successful init that calls `shutdown` on the worker, with another shutdown waiting. (`claude/sections/testing.md:256-259`)

## i17. Accept

[F] A retained feed can take frames while a start waits for its result. A failed start closes admission and clears queued frames. The request that caused the start receives its `Feed` only after success. On the rig, the first Mono8 frame arrived about 79 ms before the start reply. (`claude/sections/control-plane.md:295-322`, `codex/sections/data-plane.md:100`, `:116`, `claude/camera/c1.md:149-161`)

[F] The failing-start test waits for the consumer to enter its second `take` before the scripted start fails. It checks the consumed frame's epoch and bit depth, the closed admission, and delivery in a later epoch. The no-user stop test checks recovery after a failed stop. (`claude/sections/testing.md:218-234`)

## i18. Accept

[F] A change signal triggers one confirmation stop outside general recovery. Any failure keeps `kWedged` and updates `last_reconciliation`. The `connected` service checks only for a camera object. The tests check one stop after a poll timeout and continued wedge state after a confirmation returns -3. (`claude/sections/control-plane.md:433-457`, `claude/sections/error-vocabulary.md:129-132`, `claude/sections/testing.md:221-223`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1520-1527`)

## i19. Reopen

[F] Part A reads back both changed values before the reopen. The fixed-string search finds the failed-load message after the ROS and launch prefixes. The missing-file launch checks that the search can find that message. (`claude/sections/bring-up.md:95-100`, `:184-198`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:390-399`, `ros:ros2/rcutils/src/logging.c:88-89`, `ros:ros2/launch/launch/launch/actions/execute_local.py:90-91`)

[F] Part A searches `driver_b.log` right after launch. The driver attempts the load during camera initialization. If the search runs first, it can miss a later failure. Part B can still pass if the seven values match, and step 1 repeats the same log check. (`claude/sections/bring-up.md:102`, `:196-198`, `:208-216`, `claude/sections/implementation-sequence.md:60-70`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:93-105`, `:390-399`)

[F] The driver emits `Initialization done!` after the load attempt. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:97-134`, `:390-399`)

1. Before checking each launch log, wait for `Initialization done!` in that log with a time limit.
2. If the marker does not appear by the limit, fail the check.

## i21. Accept

[F] Each rate uses one source-time interval for both stamp pairs and driver gap lines. The rules flag shared endpoints, multiple lines in a pair, size mismatches, and lines outside the interval as ambiguous. An ambiguous run is inconclusive. (`claude/sections/testing.md:306-337`, `claude/sections/implementation-sequence.md:208-215`)

[F] The driver logs a gap before it publishes the next frame. On Linux with Cyclone DDS, `rmw_publish` stamps that write with `CLOCK_REALTIME`, and the reader exposes the stamp as `source_timestamp`. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1603`, `:1631`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:1965-1969`, `:3280`, `ros:eclipse-cyclonedds/cyclonedds/src/ddsrt/src/time/posix/time.c:21-26`)

[A] Host time advances throughout each run. Pair matching depends on that order. [F] The outside reader's `ros2 topic echo` command supports explicit reliability and depth. (`claude/sections/testing.md:353-358`, `ros:ros2/ros2cli/ros2topic/ros2topic/verb/echo.py:55-76`, `:111-127`)

## i22. Accept

[F] The test waits up to 1000 ms for the second `take` and checks that the first returned N. It then injects N+1. The capacity-1 queue cannot evict N with N+1 before the first `take`. If the caller returns N, it never enters the second `take`, and the test fails. (`claude/sections/testing.md:94-99`, `:184-195`, `codex/sections/data-plane.md:98-100`)

## i25. Reopen

[F] The section states the persistence scope and the readback limit. The driver uses `VmbFeaturePersistNoLUT` for the remote device, local device, and stream modules, with 10 load iterations. The remaining load check can still miss an error if it reads the log too early. Apply the i19 wait to the settings file check. (`claude/sections/bring-up.md:84-104`, `:184-198`, `driver:vimbax_camera/src/vimbax_camera.cpp:1358-1367`)

## i26. Accept

[F] `Feed` owns the subscription. The link mutex guards `released` and the borrowed pointer. The first close clears the pointer and posts the named release. The worker removes only that link. Move assignment closes the destination before it destroys the old subscription. The tests exercise move assignment into a live `Feed` and explicit close followed by destruction while a get image lease remains active. (`claude/sections/control-plane.md:213-241`, `claude/sections/testing.md:263-266`)

## i31. Accept

[F] `QueuedBeforeStart`, `InitFailure`, `Shutdown`, and `DestroyWithPendingRequest` now use `feed_open` in step 5. The step 6 exit check includes `ShutdownWakesGetImage`. Step 6 adds `get_image` before that test runs. (`claude/sections/testing.md:251-262`, `claude/sections/implementation-sequence.md:143-153`, `:160-171`)
