# Round 1 data-plane fixes

## i1. Fixed

Assign `receive_seq` with `frames_received.fetch_add(1) + 1` on the zero-initialized source counter. The first sequence is 1. Source stats load the same atomic counter.

[F] The worker uses `frames_received` for the freshness cutoff. The sequence test expects 1 for the first message and checks that discards also take a number. (`docs/architecture/image-acquisition-planning/claude/sections/control-plane.md:194-209`, `docs/architecture/image-acquisition-planning/claude/sections/testing.md:82`, `docs/architecture/image-acquisition-planning/register.md:749-750,865-866`)

## i2. Fixed

Add `callback_ns_max` and `callback_ns_total` to `FrameSourceStats`. Time each `on_message` path with steady-clock reads after sequence assignment and after deferred release. This measures fan-out work and lock wait. Adapter conversion and ROS deserialization precede the first read.

[F] The feed and load probe modes record callback duration, but the draft stats have no timing field. The gateway round-trip test uses its own measurements for d5. (`docs/architecture/image-acquisition-planning/codex/sections/data-plane.md:56-66`, `docs/architecture/image-acquisition-planning/claude/sections/testing.md:149-154`, `docs/architecture/image-acquisition-planning/register.md:840,869-871`)

## i3. Fixed

Give each source a `FrameFanout` by value. Each concrete subscription shares its queue block and the state that holds the fan-out lock. `FrameFanout` closes and unlinks queues at teardown. A surviving subscription keeps its queue block and lock, so a later `close()` is safe.

[F] ic2 permits the subscription to outlive its source. The tests cover a pull after source destruction and a feed after controller destruction. (`docs/architecture/image-acquisition-planning/register.md:703-711`, `docs/architecture/image-acquisition-planning/claude/sections/testing.md:93,128`)

The port still returns `std::unique_ptr<FrameSubscription>`. For i26, the worker needs a way to close live feed subscriptions during controller shutdown. Source teardown covers a later lifetime boundary.

## i4. Fixed

Order queue registration and frame pushes under the same lock. For get image, use the worker's pre-subscribe value `R = stats().frames_received`. Skip every frame with `receive_seq <= R`. This includes a frame whose callback took a sequence before the cutoff and pushed it after the queue linked. Capacity 1 can evict an earlier qualifying frame.

[F] i12 requires both the push after queue registration and the sequence cutoff. The c1 check saw the first Mono8 frame 78.6 ms before the driver logged a successful start. (`docs/architecture/image-acquisition-planning/issues.md:152-156`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:149-161`)

## i5. Fixed

Allocate the list node and ring storage before taking the lock. Splice the list node on subscribe. Detach nodes on close and destroy them after unlocking. Hold one reference to each distinct evicted or cleared frame until after unlocking. Four local holders cover the last four pushes, since each open queue is a suffix of those pushes.

[F] ic8 bars heap allocation under the fan-out lock, and the c1 Mono8 payload is 1,337,472 bytes. The draft clears queue entries even when they hold the last frame reference. (`docs/architecture/image-acquisition-planning/register.md:860-866`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:100-109`, `docs/architecture/image-acquisition-planning/claude/review-of-codex.md:34`)

## i6. Fixed

Return `const std::string&` from `encoding()` and `tf_frame()`. Scalar accessors return by value. A frame copy keeps the returned strings alive.

[F] The register gave the strings by value with `noexcept`. v1 returned both string fields by const reference, which avoids copying them in the accessors. (`docs/architecture/image-acquisition-planning/register.md:615-639`, `docs/architecture/image-acquisition-design-v1.md:686-697`)

## i7. Fixed

Give `FrameFanout` friend access to the private `ImageFrame::stage` factory. Validate and allocate before locking. Under the lock, set the epoch and bit depth on the unpublished block. Publish it through a const shared block. The public factory still returns an immutable frame.

[F] ic1 made the public factory result immutable. ic3 sets the epoch fields under the lock, where ic8 forbids allocation. The ic1 text for fan-out frames now needs the rule that the frame is immutable after `FrameFanout` publishes it. (`docs/architecture/image-acquisition-planning/register.md:643-647,749-755,864`)

## i8. Fixed

Return `kSourceCreateFailed` for an empty `camera_namespace` before creating the ROS subscription. Apply the existing trailing-slash rule to nonempty input.

[F] The gateway rejects empty input before constructing service clients. Its name helper removes trailing slashes and appends the service leaf. (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:16-25`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:36-46`)

## i9. Fixed

Name `FrameFanoutClock`, its two readings, and the `FrameFanout` method set in the section. The clock outlives the fan-out. The adapter owns the production clock, and `FakeFrameSource` borrows the test clock. The adapter and fake supply their own publisher counts.

[F] ic7 gives the clock return types and message entry point. The testing draft takes a `FrameFanoutClock&` and forwards to the private fan-out. (`docs/architecture/image-acquisition-planning/register.md:831-839`, `docs/architecture/image-acquisition-planning/claude/sections/testing.md:39-51`, `docs/architecture/image-acquisition-planning/claude/draft-notes.md:84`)
