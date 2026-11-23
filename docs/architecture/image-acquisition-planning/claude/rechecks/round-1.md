# Recheck of the round 1 data-plane fixes

Round 1. Checkpoint `5bb39db`. Claude rechecks the Codex fixes for i1 to i9 in task `recheck-claude-r1`.

Inputs:

1. The issues in `docs/architecture/image-acquisition-planning/issues.md:72-133`.
2. The Codex response in `docs/architecture/image-acquisition-planning/codex/fixes/round-1.md`.
3. The fixed section `docs/architecture/image-acquisition-planning/codex/sections/data-plane.md`.
4. The fixed source tree `docs/architecture/image-acquisition-planning/codex/source-tree.md`.

The recheck also reads the register contracts ic1 to ic8 and the Claude testing and control-plane sections. These show whether a fix breaks a consumer of the data plane. Each citation is `path:line` from the worktree root.

## Summary

| Id | Verdict | Reason |
|---|---|---|
| i1 | Accept | One `fetch_add(1) + 1` on a zero-initialized atomic. `stats()` loads the same atomic. |
| i2 | Accept | `callback_ns_max` and `callback_ns_total` are in `FrameSourceStats`. Two named `steady_now()` reads bound the interval. |
| i3 | Accept | Subscriptions share their queue block and the lock state. `close()` after source destruction uses only these blocks. |
| i4 | Accept | The section states the queue link as the push cutoff and `receive_seq <= R` as the freshness cutoff. |
| i5 | Accept | Storage and list nodes are allocated before the lock. Four holders defer each last frame release until after the unlock. |
| i6 | Accept | `encoding()` and `tf_frame()` return `const std::string&`. Scalars return by value. |
| i7 | Accept | `FrameFanout` is a friend, the private `stage` factory gives the mutable block, and the section states "immutable after `FrameFanout` publishes it". |
| i8 | Accept | An empty `camera_namespace` returns `kSourceCreateFailed` before the ROS subscription. |
| i9 | Accept | `FrameFanoutClock`, its two reads, the `FrameFanout` method set, and the clock lifetime rule are named. |

Result: 9 Accept, 0 Reopen. The fixes add no new defect in the data plane. The section "Register text that the fixes need" lists contract text that `integrate-2` must change to match the fixed section. These changes are not reasons to reopen.

## i1. Accept

Fact. Step 1 sets `receive_seq = frames_received.fetch_add(1) + 1` on a zero-initialized `std::atomic<std::uint64_t>` (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:124`). The first value is 1. `stats().frames_received` loads the same atomic and gives the last sequence assigned (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:132`).

Checks:

1. The increment and the assignment are now one atomic operation. A concurrent `stats()` read is an atomic load, so the data race in the finding is gone.
2. After the increment, `receive_seq` equals the counter value. The control-plane rule `R = stats().frames_received` and "skip `receive_seq <= R`" therefore compares like values (`docs/architecture/image-acquisition-planning/claude/sections/control-plane.md:194-209`).
3. Each discard also takes a number (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:132`). This matches `Fanout.SequenceFromOne` and `Adapter.SequenceAcrossDiscards` (`docs/architecture/image-acquisition-planning/claude/sections/testing.md:82`, `:140`).
4. The atomic total order also makes the cutoff sound. A frame with `receive_seq > R` did its `fetch_add` after the worker loaded `R`, so the frame arrived after the request.

## i2. Accept

Fact. `FrameSourceStats` now has `callback_ns_max` and `callback_ns_total` (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:68-69`). Step 2 reads `steady_now()` as the start. Step 7 reads `steady_now()` again after the deferred releases (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:125`, `:130`). The total uses an atomic add. The maximum uses a compare-and-exchange loop. The source tree carries the two fields (`docs/architecture/image-acquisition-planning/codex/source-tree.md:8`).

Checks:

1. The expected change asked for a duration field and the clock reads that bound it. The section gives both.
2. The interval starts after the sequence assignment and excludes adapter conversion and ROS deserialization (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:132`). This is not a defect for d5. The `rtt` probe mode measures the gateway round-trip directly, and d5 decides on that value (`docs/architecture/image-acquisition-planning/claude/sections/testing.md:154`). The adapter conversion builds two short strings and parses one stamp, so the missing part is small.
3. A discard goes directly to step 7 (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:122`). So every message is timed, and `callback_ns_total / frames_received` gives a mean. With one executor thread, at most one callback is in flight when `stats()` reads the two values.
4. The `feed` and `load` modes can now record the callback time from `stats()` (`docs/architecture/image-acquisition-planning/claude/sections/testing.md:152-153`).

## i3. Accept

Fact. The adapter and `FakeFrameSource` each hold `FrameFanout` by value (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:102`, `docs/architecture/image-acquisition-planning/codex/source-tree.md:19`). `FrameFanout` holds a shared state with the fan-out lock and the list of open queues. Each concrete subscription holds a shared pointer to its queue block and another to the shared state. Neither block refers to the source or the clock (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:102`). At source teardown, `FrameFanout` closes and unlinks each queue under the lock. A later `close()` sees the closed flag and returns (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:106`).

Checks:

1. After source destruction, `close()`, `take`, and `stats()` touch only the queue block and the shared state. The subscription keeps both alive. No freed memory is used.
2. A `take` that waits at teardown waits on the queue block condition variable with the shared-state lock. Both stay alive, so the wake and the `kFeedClosed` result are safe. This meets ic2 rules 3 and 7 (`docs/architecture/image-acquisition-planning/register.md:707`, `:711`).
3. The source tree now states how each source holds `FrameFanout`. `FakeFrameSource` uses the same class, so the fake copies the model with no extra rule.
4. `Fanout.SourceGone` and `Controller.FeedOutlivesController` can pass under AddressSanitizer with this model (`docs/architecture/image-acquisition-planning/claude/sections/testing.md:93`, `:128`).

The port still returns `std::unique_ptr<FrameSubscription>` (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:89-90`). This keeps ic2 `Feed` item 1 valid. The control-plane text that the worker and `Feed` share the subscription stays in conflict with ic2 (`docs/architecture/image-acquisition-planning/claude/sections/control-plane.md:303`). That conflict is i26, owned by Claude. The i3 model makes either i26 option safe, because `close()` is safe from any thread and after source destruction.

## i4. Accept

Fact. The section states that `subscribe` and a push both take the fan-out lock, so only pushes after the queue link reach the new queue. It states that a callback can take its sequence before `subscribe` and push after the link, with a sequence at or below `frames_received` at that time (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:134`). It states that the worker reads `R` before `subscribe`, skips each frame with `receive_seq <= R`, and that capacity 1 can evict an earlier qualifying frame (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:136`).

Checks:

1. The text has all three parts of the expected change: the earlier sequence can arrive, the queue link decides the pushes, and the control plane skips `receive_seq <= R`.
2. The qualifying frame matches the i12 text: a push after the queue link and `receive_seq > R` (`docs/architecture/image-acquisition-planning/issues.md:156`).
3. The section names a test seam for the in-flight case: a pause in the first `steady_now()` read. That read comes after step 1 and before the lock (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:124-128`). `Controller.InFlightFrameSkipped` can use it (`docs/architecture/image-acquisition-planning/claude/sections/testing.md:112`). The i22 barrier request is met on the data-plane side.

## i5. Accept

Fact. `subscribe` creates the subscription, queue storage, and list node before the lock and splices the node under the lock (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:104`). `close` unlinks its node under the lock, and the node is destroyed after the unlock. Four local holders keep one reference to each distinct evicted or cleared frame until after the unlock (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:108`). A pull moves its frame out under the lock and builds any error text after the unlock.

Checks:

1. The suffix argument holds. Each push reaches every open queue, a new queue starts empty, a pull or an eviction removes the oldest entry, and `close_admission` empties all queues. So each queue holds a contiguous run that ends at the newest push. The union of all queues is the longest run, at most 4 frames with capacity at most 4 (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:98`).
2. A push evicts only frames from that union, so four holders cover a push. `close_admission`, `close`, and source teardown remove at most that union, so four holders cover them also.
3. Each holder keeps one reference, so a duplicate reference that leaves a queue only decrements the count. No 1,337,472-byte payload is freed under the lock.
4. A ring with fixed storage and a splice into a preallocated node do not allocate under the lock. The staged frame block is allocated in step 3, before the lock (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:126`). A discarded staged block is released in step 7, after the lock.
5. The source tree assigns the deferred releases to `frame_fanout.cpp` (`docs/architecture/image-acquisition-planning/codex/source-tree.md:11`).

This meets ic8 guarantee 3 (`docs/architecture/image-acquisition-planning/register.md:864`).

## i6. Accept

Fact. Scalar accessors return by value. `encoding()` and `tf_frame()` return `const std::string&` into the shared frame block (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:13`). The section tells the caller to keep a frame copy alive while it uses a string reference or the pixel span (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:32`).

The field table still gives `std::string` in the type column (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:19`, `:21`). The column gives the stored field type, and line 13 gives the accessor type. This is wording only.

## i7. Accept

Fact. `ImageFrame` declares `frame_support::FrameFanout` as a friend. The private `stage` factory validates and allocates a mutable block before the lock. Under the lock, only `FrameFanout` sets `stream_epoch` and `significant_bits` on the unpublished block. It then moves the sole staging handle into an `ImageFrame` with a const block. The section states "The frame is immutable after `FrameFanout` publishes it" (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:30`). The source tree adds the friend and `stage` to `image_frame.hpp` (`docs/architecture/image-acquisition-planning/codex/source-tree.md:7`).

Checks:

1. The seam is named, and only one class can use it.
2. The conversion from the mutable handle to the const block moves a shared pointer, so it does not allocate under the lock.
3. No other thread can see the block before the publish, so the late writes do not race an accessor.

## i8. Accept

Fact. An empty `camera_namespace` returns `kSourceCreateFailed` before the ROS subscription. A nonempty value loses its trailing slashes and gets `/image_raw` (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:150`). The gateway rejects an empty value at `src/venimapping_camera/src/vimbax_camera_gateway.cpp:21-25` and strips trailing slashes at `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:41-45`. The source tree repeats the rule (`docs/architecture/image-acquisition-planning/codex/source-tree.md:13`).

A namespace of only `"/"` becomes an empty string after the strip and gives `/image_raw`. The gateway has the same result for its services, because it checks emptiness before the strip. The two layers stay consistent, and the finding asked only for the empty case. This is not a reason to reopen.

## i9. Accept

Fact. The private header `src/frame_support/frame_fanout.hpp` declares `FrameFanoutClock` and `FrameFanout` in `venimapping::camera::frame_support`. The clock gives `realtime_ns()` as `std::int64_t` and `steady_now()` as a `std::chrono::steady_clock::time_point`. `FrameFanout` takes a `FrameFanoutClock&`, and the clock must outlive it (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:118`). The method set is `subscribe`, `open_admission`, `close_admission`, `stats`, `set_transport_lost`, and `on_message` (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:120-122`). Each source implements `matched_publishers()`. The adapter builds its clock before its `FrameFanout` (`docs/architecture/image-acquisition-planning/codex/source-tree.md:19`).

Checks:

1. `FakeFrameSource(FrameFanoutClock& clock)` and its forwarding list in the testing draft match these names (`docs/architecture/image-acquisition-planning/claude/sections/testing.md:42-51`).
2. Member order in the adapter destroys `FrameFanout` before the clock, so the lifetime rule holds in production.

The section does not say that `FrameFanoutClock` is an abstract class with virtual reads. The adapter owns a "production clock" and the fake borrows a "test clock", so a polymorphic interface is the only reading that works. The register note below asks `integrate-2` to state it.

## Register text that the fixes need

These amendments make the register match the accepted fixes. They do not change any fix. `integrate-2` owns them.

1. ic1 item 4 (`docs/architecture/image-acquisition-planning/register.md:646`): change "immutable after `create`" to "immutable after `create` or after `FrameFanout` publishes it" (i7).
2. ic1 sketch comment (`docs/architecture/image-acquisition-planning/register.md:638`): `encoding()` and `tf_frame()` return `const std::string&`. Other accessors return the field type (i6).
3. ic2 `FrameSourceStats` (`docs/architecture/image-acquisition-planning/register.md:679-689`): add `callback_ns_max` and `callback_ns_total` (i2).
4. ic3 item 3.1 (`docs/architecture/image-acquisition-planning/register.md:750`): state `receive_seq = frames_received.fetch_add(1) + 1` (i1).
5. ic3 item 3.2 (`docs/architecture/image-acquisition-planning/register.md:751`): add the second `steady_now()` read after the deferred releases (i2).
6. ic3 item 3.3 (`docs/architecture/image-acquisition-planning/register.md:752`): replace `ImageFrame::create` with the private `stage` factory (i7).
7. ic2 `VimbaXFrameSource` item 1 (`docs/architecture/image-acquisition-planning/register.md:732`): add the empty-namespace rejection (i8).
8. ic7 item 2 (`docs/architecture/image-acquisition-planning/register.md:834`): name `FrameFanoutClock` as an abstract class with virtual `realtime_ns()` and `steady_now()`, and state the lifetime rule (i9).
9. ic8 guarantee 10 (`docs/architecture/image-acquisition-planning/register.md:871`): state that the measured interval runs from the first `steady_now()` read to the read after the deferred releases (i2).
10. d24 decision text (`docs/architecture/image-acquisition-planning/register.md:515`) still has the round 0 wording. i12 closed it with new text (`docs/architecture/image-acquisition-planning/issues.md:156`). The section text from i4 depends on that new text.

## Effect on the Claude fixes

1. i26. The data plane keeps `std::unique_ptr<FrameSubscription>` and makes `close()` safe from any thread and after source destruction. `fix-claude-r1` must remove the shared ownership claim at `docs/architecture/image-acquisition-planning/claude/sections/control-plane.md:303` or propose the ic2 change.
2. i22. The barrier for `Controller.InFlightFrameSkipped` can sit in the first `steady_now()` call of the injected `FrameFanoutClock`. The fake stamp default and the match timer endpoints stay with `fix-claude-r1`.
3. i22. A test clock that blocks in `steady_now()` makes the measured callback duration include the block. Tests that check `callback_ns_max` must not use the barrier.
