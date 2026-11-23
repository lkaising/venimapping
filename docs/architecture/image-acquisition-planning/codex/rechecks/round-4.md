# Recheck of the round 4 fixes

Checkpoint `ae32c74539972292267642e0b8151ea0156519c5`. Planning citations are relative to `docs/architecture/image-acquisition-planning/`.

## i15. Accept

[F] The issue requires a return rule for successful `init` in `kStopped`, a test that forces that order, and two entries for the test. (`issues.md:173-177`, `claude/fixes/round-4.md:15-17`)

[F] `start` reads the init result and lifecycle value under the lifecycle mutex. The table covers both init results in all three reachable lifecycle values. After successful `init` in `kStopped`, the stop wait returns at once and `start` returns `kFeedClosed`. Only the join owner can move `kStopping` to `kStopped`, after the worker exits and the join returns. The worker completes queued requests with `kFeedClosed` before it exits. (`claude/sections/control-plane.md:195-211`, `:219-241`, `:282-288`)

[F] `Controller.ShutdownJoinedBeforeStartReads` holds thread A in the start test hook with no controller lock held. Thread B calls `shutdown()` in `kStarting`, joins the worker, and sets `kStopped`. The worker records a successful init result before it exits. The test opens the gate only after B returns, then checks that A returns `kFeedClosed` within 100 ms. (`claude/sections/control-plane.md:245-259`, `claude/sections/testing.md:321-342`)

[F] Step 5 names `ShutdownJoinedBeforeStartReads` in exit check 1.4. The coverage table lists it for ic2 and ic4. (`claude/sections/implementation-sequence.md:152-158`, `claude/sections/testing.md:483`)
