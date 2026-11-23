# Recheck of the round 1 fixes

Checkpoint `e58d00a8f7fc3cf753f0746635958e09839003fd`. Planning citations are relative to `docs/architecture/image-acquisition-planning/`. The `driver:` and `ros:` prefixes identify the local source roots.

## i10. Accept

[F] The matching-profile branch waits for a publisher match and passes the verified bit depth to `open_admission`. The fallback closes admission and runs the full start sequence. That sequence reads back the profile, checks the format, waits for a match, and opens a new epoch before `stream_start`. (`claude/sections/control-plane.md:246-261`, `:412-421`)

[F] `ReconnectNoRestart` checks the call order and epoch 3. `ReconnectNewEpoch` checks `open_admission(8)` on the driver restart path. (`claude/sections/testing.md:185-187`)

## i11. Accept

[F] The driver can restart the stream after a reopen. The camera accepted `TriggerSelector` writes during acquisition, and repeated selector changes left the `FrameStart` mode unchanged. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:556-568`, `:579-593`, `claude/camera/c2.md:128-130`, `:187`)

[F] The fix permits the selector write before `TriggerMode` readback and keeps admission closed until the profile matches. Corrective writes still require a confirmed stop. Adopt the proposed d18 item 7 amendment. (`claude/sections/control-plane.md:292-306`, `:415-418`, `claude/fixes/round-1.md:45-57`)

## i13. Accept

[F] In `kOutage`, `kConnectionUnknown`, and `kStalled`, new requests attach without a gateway call. The start sequence requires a confirmed stop before corrective writes. `RequestDuringOutage` checks deadline and recovery outcomes with a feed already open. (`claude/sections/control-plane.md:207-226`, `:250-254`, `claude/sections/testing.md:184-189`)

## i14. Reopen

[F] The fix adds a shared outcome and one deadline. The named checks surround whole readbacks and the corrective write list. A pending call can finish after expiry, then the next call in the list can still run. (`claude/sections/control-plane.md:128-151`, `:275-286`, `:300-316`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:79-94`)

[F] The caller passes `deadline - now` to `take` and accepts any fresh frame it returns. A nonpositive timeout still takes a queued frame, so the caller can return a frame that arrived after expiry. (`claude/sections/control-plane.md:324-332`, `codex/sections/data-plane.md:98-100`, `register.md:543-547`)

Check the deadline and outcome before each gateway call that advances the request. Check the deadline under the outcome lock before delivery. If expiry prevents `stream_start` after admission opens, close that admission. Enforce the absolute deadline at frame acceptance. Add tests for expiry during readback and a fresh frame queued after expiry. (`claude/sections/control-plane.md:144-151`, `:259-261`, `claude/sections/testing.md:159-163`)

## i15. Reopen

[F] Requests can queue before `start`, but `shutdown` gives all queue completion to the worker. Before `start`, no worker exists to wake those callers with `kFeedClosed`. The tests cover a successful late `start` and destruction after the worker enters `stream_start`. (`claude/sections/control-plane.md:85-95`, `:155-183`, `claude/sections/testing.md:197-201`)

Give shutdown before `start` a path that closes the request queue and completes pending callers without a gateway call. Test shutdown with a queued request and no worker. Serialize ownership of the worker join when `start` and shutdown overlap. (`claude/sections/control-plane.md:108`, `:165-177`)

## i16. Accept

[F] The start sequence takes the gate check and bit depth from the final `PixelFormat`. Each feature getter and setter supplies `FeatureModule::kRemoteDevice`, as the gateway signatures require. The Mono12-to-Mono8 test checks 8 significant bits on the first frame. (`claude/sections/control-plane.md:246-261`, `:275-286`, `:300-306`, `src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:59-110`, `claude/sections/testing.md:140-144`)

## i17. Reopen

[F] A failed start now closes admission before reconciliation. The no-user stop also enters recovery on failure. `StartFailClearsQueue` checks that failure clears a frame that the feed has yet to take. (`claude/sections/control-plane.md:259-261`, `:367-373`, `:430-435`, `claude/sections/testing.md:169-174`)

[F] The section promises that a retained feed never gets a frame from a failed epoch. The queue opens before `stream_start`, and `take` returns a queued frame at once. A consumer can therefore take a frame before the start reports failure. Clearing the queue cannot recover that frame. (`claude/sections/control-plane.md:259-265`, `codex/sections/data-plane.md:98-100`, `claude/camera/c1.md:149-161`)

Define when a retained feed can take frames from an epoch with a pending start. Test an active consumer during a failing recovery start.

## i18. Reopen

[F] The fix separates the original error and the reconciliation result. It uses a successful stop as evidence to clear `kWedged` and tests a poll timeout followed by `true`. (`claude/sections/control-plane.md:365-391`, `claude/sections/error-vocabulary.md:119-126`, `claude/sections/testing.md:171-176`)

[F] The wedge rule keeps `kWedged` after a failed confirmation stop. The general failure rule also covers that stop and orders another stop on -15, or outage handling on -3. These paths conflict. The `connected` service only reports camera object presence. (`claude/sections/control-plane.md:369-373`, `:384-391`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1520-1527`)

Make confirmation a single stop attempt per change signal. Keep `kWedged` after any failed confirmation and assert the stop count in the poll timeout test.

## i19. Reopen

[F] The rig check reads the installed XML path and live plugin filter. It requires one raw publisher, checks the plugin topic prefix, and bounds the first frame wait. (`claude/sections/bring-up.md:181-195`)

[F] Part A writes two different values and restarts the driver without reading either value back before the restart. Both exit checks look for a console line that starts with `Loading settings from file`. The driver puts that text in the log message, and ROS prefixes the console line. (`claude/sections/bring-up.md:170-179`, `claude/sections/implementation-sequence.md:59-69`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:390-399`, `ros:ros2/rcutils/src/logging.c:87-89`)

Read back the two different values before stopping the driver. In both checks, match the failed-load message within the console line. This catches a load error even if part B finds matching profile values.

## i20. Accept

[F] Step 9 restores host stamps and verifies `use_ros_time` before the wedge check. The check reads back `Mono8` while the driver remains wedged. It keeps one controller alive across the driver restart. If the write cannot restore `Mono8`, the scripted tests cover recovery. (`claude/sections/implementation-sequence.md:196-210`, `claude/sections/testing.md:275-277`, `:290-306`)

## i21. Reopen

[F] Jazzy `ros2 topic echo` supports the explicit RELIABLE QoS in the replacement command. The stamp reader waits for a match, and the load result is inconclusive when no driver gap occurs. (`ros:ros2/ros2cli/ros2topic/ros2topic/verb/echo.py:55-76`, `:111-127`, `claude/sections/testing.md:243-265`, `:279-286`)

[F] The probe records every received stamp, but it counts driver gap lines only after the start reply. Mono8 frames arrived about 79 ms before that reply. An early driver gap can therefore look like a reader gap. (`claude/sections/testing.md:245-256`, `claude/camera/c1.md:149-161`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1603`)

For each rate, use one source-time interval for both frames of each stamp pair and the driver logs. Match each line at most once. Mark ambiguous matches inconclusive.

## i22. Reopen

[F] The clock hold sits between sequence assignment and the fan-out lock. The fake advances realtime for default stamps. The adapter test compares addresses over intra-process delivery, and the probe names both timing endpoints. (`claude/sections/testing.md:41-62`, `:64-83`, `:218-222`, `:238-241`, `codex/sections/data-plane.md:124-130`)

[F] `InFlightFrameSkipped` injects N+1 after releasing N. Its stats show that N reached the queue. On a capacity-1 queue, N+1 can evict N before the caller takes it. The test can then pass with the freshness check removed. (`claude/sections/testing.md:158`, `claude/sections/control-plane.md:334-346`, `codex/sections/data-plane.md:98-100`)

Use a test-only hook on the fake subscription to observe the second `take`. Wait for that call, with a time limit, before injecting N+1.

## i23. Accept

[F] The deadline table names queue, gateway, match, start, and frame waits. Corrective write results come from the second readback. The loss row counts RMW `message_lost` events and explains that Cyclone DDS history overwrite can leave the counter unchanged. The deadline execution rule still needs the i14 fix. (`claude/sections/error-vocabulary.md:97-111`, `:129-146`, `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`)

## i24. Accept

[F] Step 5 installs `venimapping_camera_acquisition` into the package export set. A separate consumer finds the installed package and calls `AcquisitionController::create`, so it must link the library. The CMake rules give steps 4 and 5 separate blocks and specify the rebase order. (`claude/sections/implementation-sequence.md:28-39`, `:129-153`, `src/venimapping_camera/CMakeLists.txt:62-75`)

## i25. Reopen

[F] The scope and readback limits are explicit. The driver selects `VmbFeaturePersistNoLUT` for the remote device, local device, and stream modules. Readback checks the seven listed values and the selector write. (`claude/sections/bring-up.md:83-94`, `driver:vimbax_camera/src/vimbax_camera.cpp:1358-1367`)

[F] The remaining requirement uses the load result in the rig check. The check can miss a failed load when the seven values already match because it checks the start of a prefixed line. Apply the i19 log check fix here. (`claude/sections/bring-up.md:92-94`, `:172-188`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:390-399`, `ros:ros2/rcutils/src/logging.c:87-89`)

## i26. Reopen

[F] `Feed` owns the only subscription handle. Shutdown locks the shared `LeaseLink` before it uses the borrowed pointer. The data-plane close remains safe after source destruction. (`claude/sections/control-plane.md:185-205`, `codex/sections/data-plane.md:102-106`)

[F] `Feed::close` posts a release after clearing the pointer, and the destructor calls `close` again. An explicit close followed by destruction can post two releases for one lease. Move assignment also needs to close the destination's old lease before replacing its subscription. Otherwise its old link can retain a dangling pointer. (`claude/sections/control-plane.md:66-78`, `:196-205`)

Use the link lock to make release occur once per lease. Apply that close path before move assignment replaces an owned subscription. Test explicit close followed by destruction. Test move assignment into a live `Feed`.

## i27. Accept

[F] `FeedOptions::deadline` uses the shared request mechanism and defaults to 5000 ms. The error table covers `feed_open`, and `FeedOpenDeadline` checks caller expiry and later lease cleanup. Apply the i14 request checks to both entry points. (`claude/sections/control-plane.md:45-48`, `:128-153`, `claude/sections/error-vocabulary.md:79-81`, `claude/sections/testing.md:162`)

[A] The cold path takes less than 500 ms at a few milliseconds per gateway call. The 5000 ms default leaves room for that path. (`claude/sections/control-plane.md:153`)
