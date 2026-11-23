# Recheck of the round 3 fixes

Checkpoint `939dbb7c84d7dba75ecc1630560b7e352e66cedf`. Planning citations are relative to `docs/architecture/image-acquisition-planning/`. The `driver:` and `ros:` prefixes identify the local source roots.

## i15. Reopen

[F] Only the join owner can move the lifecycle from `kStopping` to `kStopped`, after `join()` returns. Other threads in the stop wait use a predicate for `kStopped`. The worker posts the stop request and returns from `shutdown()` without joining or waiting. (`claude/sections/control-plane.md:183-205`, `:216-222`)

[F] After a successful init, `start()` has return rules for `kStarting` and `kStopping`. A concurrent `shutdown()` can join the worker and set `kStopped` before `start()` reacquires the lifecycle mutex. The original `start()` then has no return rule for this state. (`claude/sections/control-plane.md:194-203`, `:207-222`)

[F] Step 5 includes both new overlap tests. `ShutdownFromInitWithWaiter` starts the second shutdown after `stream_stop` begins. Its steps leave `start()` free to process the init result before the join ends. (`claude/sections/testing.md:274-276`, `:285-311`, `claude/sections/implementation-sequence.md:149-157`)

1. If init succeeded and the original `start()` sees `kStopped`, return `kFeedClosed`.
2. Test the successful init with the join owner publishing `kStopped` before `start()` handles the result.

## i19. Accept

[F] The driver attempts the settings load and logs any failure before it emits `Initialization done!`. Both messages use the same console stream. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:97-134`, `:390-400`, `ros:ros2/rcutils/src/logging.c:659-674`)

[A] The console capture keeps the line order. The missing-file control launch checks that the failed-load line is present after the init wait. (`claude/sections/bring-up.md:104-109`, `:197-209`)

[F] Part A waits on each launch log and fails if the marker does not appear within 60 s. It reads back both changed values before reopening. Step 1 uses the same wait before its log checks. The tier 4 settings load check also waits before it searches the log. (`claude/sections/bring-up.md:111-119`, `:203-226`, `claude/sections/implementation-sequence.md:60-73`, `:195-209`, `claude/sections/testing.md:388-395`)

## i25. Accept

[F] The driver uses `VmbFeaturePersistNoLUT` for the remote device, local device, and stream modules, with 10 load iterations. The controller readback covers seven profile values and the selector write. The settings file check uses the part A log wait before the failure search. That wait covers the load attempt even when the camera already holds the expected values. (`driver:vimbax_camera/src/vimbax_camera.cpp:1358-1367`, `claude/sections/bring-up.md:84-93`, `:104-123`, `:203-220`)
