# Image acquisition design positions

## Structure

### D1. Package layout

- Position. Keep the ports, controller, and adapter in `venimapping_camera`. Build the ROS-free acquisition code and the rclcpp frame adapter as separate targets.
- Evidence. [F] The package already separates its C++23 gateway API from the VimbaX gateway library. Its install rule exports public headers. (`src/venimapping_camera/CMakeLists.txt:22-48`, `src/venimapping_camera/CMakeLists.txt:58-75`)
- Rejected options. A separate ROS-free package adds a package boundary where the existing target boundary suffices. A separate acquisition package adds a dependency on the gateway package for the same camera.
- What would change my mind. [Q] Will a non-ROS build need to install the ports and controller without a ROS underlay?
- Cost to reverse. Medium. Moving packages changes CMake exports, manifests, and downstream dependencies.

### D2. Port shape

- Position. Keep v1's separate ROS-free `FrameSource` port. The controller composes it with `CameraGateway` and owns stream policy.
- Evidence. [F] The gateway already has blocking stream controls and a bound worker contract. The driver publishes pixels on a separate topic. (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:24-44`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-49`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:350-364`)
- Rejected options. Frame methods on `CameraGateway` mix blocking controls and concurrent frame delivery in one contract. Direct topic access gives each C++ consumer responsibility for ROS and frame admission.
- What would change my mind. [Q] Will all consumers be ROS nodes that need only the driver topic and no project acquisition policy?
- Cost to reverse. Medium. A port change moves the controller's frame dependency and changes its fakes and callers.

### D3. Frame type and metadata

- Position. Use a ROS-free `ImageFrame` with width, height, `step`, encoding, `is_bigendian`, driver host stamp, `frame_id`, receive sequence, stream epoch, and immutable data. Keep the steady receipt time inside `FrameSource`.
- Evidence. [F] The driver supplies layout and byte order, then applies the transform. With D20, the wire stamp marks driver processing, and `frame_id` names a coordinate frame. (`driver:vimbax_camera/src/vimbax_camera.cpp:1712-1715`, `driver:vimbax_camera/src/vimbax_camera.cpp:1745-1757`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1605-1618`)
- Rejected options. Exposing the ROS message makes the controller and consumers depend on ROS. The device stamp is unavailable with D20. A public receipt stamp adds a second host event without a consumer requirement. Defer source bit depth and `CameraInfo` under R3 and R11.
- What would change my mind. [Q] Does the first consumer need calibrated intrinsics or a time tied to the exposure event?
- Cost to reverse. Medium. Adding metadata changes frame construction and consumer contracts.

### D4. Memory model

- Position. Keep v1's type-erased shared owner of the received image and return a const byte span. Each retained `ImageFrame` keeps that payload alive after close.
- Evidence. [F] Jazzy rclcpp takes a shared message on its ordinary executor path. CycloneDDS restricts loans to fixed types, and `Image` has unbounded fields. (`ros:ros2/rclcpp/rclcpp/src/rclcpp/executor.cpp:554-606`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:2949-2984`, `ros:ros2/common_interfaces/sensor_msgs/msg/Image.msg:21-26`)
- Rejected options. A project-owned buffer adds one full payload copy per frame. A preallocated pool still copies each payload and needs rules for exhaustion when consumers retain frames.
- What would change my mind. [Q] Does the deployed adapter receive loans that it must return promptly, or must the project cap storage even when callers retain frames?
- Cost to reverse. Low. Replace the owner and span in the adapter while preserving the frame interface.

### D5. Thread and executor model

- Position. Use one application-owned node and one `SingleThreadedExecutor` thread for frame callbacks and gateway replies, as in v1. Keep blocking controller calls on the gateway worker.
- Evidence. [F] The probe already spins a separate executor. The gateway contract makes the worker independent of that executor. (`src/venimapping_camera/src/camera_gateway_probe.cpp:1011-1037`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-64`)
- Rejected options. A separate callback group on a multithreaded executor adds concurrent scheduling before reply delay has been measured. A separate image node and executor also adds node and thread lifetime management.
- What would change my mind. [Q] At the agreed rate, do image callbacks or deserialization cause a gateway reply to miss its deadline on the shared executor?
- Cost to reverse. Medium. A split changes executor setup, callback group membership, and shutdown tests.

### D6. Error vocabulary

- Position. Add contractual acquisition codes for feed closed, request busy, deadline passed, invalid configuration, and stream recovery required. Preserve gateway and driver errors, and use an empty result for an ordinary feed pull timeout.
- Evidence. [F] `Error` currently defines driver and gateway domains. The adapter preserves the driver's code and text, while gateway diagnostic numbers are for logs and tests. (`src/venimapping_camera/include/venimapping_camera/types/error.hpp:17-38`, `src/venimapping_camera/src/vimbax_camera_gateway.cpp:213-229`, `src/venimapping_camera/src/gateway_support/gateway_errors.hpp:15-22`)
- Rejected options. v1's private gateway diagnostics leave callers without a stable distinction between a closed feed and a failed get image request. Driver-only codes cannot describe a local close or deadline.
- What would change my mind. [Q] Will callers handle these local outcomes through distinct result variants with the same information?
- Cost to reverse. Medium. A type change alters result handling, recovery tests, and any callers that branch on acquisition codes.

## Data plane

### D7. Consumer API

- Position. Keep v1's pull API with `take(timeout)` and `try_take()` on a single-consumer feed. An idempotent close wakes a blocked pull, and the image callback never runs consumer code.
- Evidence. [F] The gateway blocks on a separate reply path. The camera delivered one Mono8 frame every 13 to 16 ms in the c1 sample. (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-47`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:111-119`)
- Rejected options. A project-thread callback needs a dispatch queue and rules for slow callbacks. An executor callback can delay gateway replies. A topic-only contract transfers timeout and close policy to consumers.
- What would change my mind. [Q] Does the first consumer require push delivery with a specified dispatch thread and a measured benefit over pull?
- Cost to reverse. Medium. Add a dispatch loop and specify callback cancellation, backlog, and shutdown behavior.

### D8. Transport mechanism

- Position. Keep v1's plain rclcpp subscription to `<camera_namespace>/image_raw`. Use the same namespace input as the gateway.
- Evidence. [F] The launch takes a camera namespace, and the driver advertises the raw topic. The driver opens the camera with exclusive access. (`src/venimapping_bringup/launch/camera.launch.py:19-41`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:350-364`, `driver:vimbax_camera/src/vimbax_camera.cpp:164-185`)
- Rejected options. An `image_transport` subscriber adds plugin selection without a compressed transport requirement. A VmbC adapter requires taking camera ownership from the driver and replacing its acquisition path.
- What would change my mind. [Q] Does a remote consumer need a tested compressed transport, or does profiling identify DDS as the cause of a missed local budget?
- Cost to reverse. High for VmbC. The project would take over SDK capture, control, reconnect, and bring-up.

### D9. Subscriber QoS and history depth

- Position. Request BEST_EFFORT, KEEP_LAST depth 1, and VOLATILE. Keep these settings in the VimbaX adapter.
- Evidence. [F] The driver offers RELIABLE, KEEP_LAST 10, and VOLATILE. A BEST_EFFORT reader matches that offer. CycloneDDS can overwrite unread reader history without a loss event. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:350-357`, `ros:ros2/rmw/rmw/include/rmw/qos_profiles.h:51-62`, `ros:ros2/rmw_dds_common/rmw_dds_common/src/qos.cpp:114-124`, `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`)
- Rejected options. v1's small RELIABLE history still permits silent history eviction. Depth 2 or 3 can retain older unread frames. A public QoS setting adds a caller choice before a second reader policy has a use.
- What would change my mind. [Q] Does a same-host load test show that depth 2 or RELIABLE meets the agreed frame delivery target with acceptable age and driver gap counts?
- Cost to reverse. Low. Change the adapter's reader settings and rerun the load test.

### D10. Queue bound, overflow, and driver buffers

- Position. Give `FrameSource` one pending feed slot and one separate slot for the first frame of a pending get image request. Replace the oldest pending feed frame at capacity, count the eviction, and keep driver `buffer_count` at 7.
- Evidence. [F] At full size, c1 measured 1,337,472 bytes per Mono8 frame and 2,674,944 bytes per Mono12 frame. The driver defaults to seven buffers. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:100-109`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:286-290`)
- Evidence. [F] At those sizes, two pending slots can pin 2,674,944 or 5,349,888 payload bytes. Seven driver buffers account for 9,362,304 or 18,724,608 payload bytes. Callback and consumer references, driver alignment storage, and DDS history are separate. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:100-109`, `driver:vimbax_camera/src/vimbax_camera.cpp:1695-1712`)
- Rejected options. A depth of 2 to 4 or v1's caller-set depth adds storage and backlog. Dropping the newest favors stale frames. A different driver buffer count needs evidence of driver buffer pressure.
- What would change my mind. [Q] Does a loaded probe show that depth 2 meets a required loss target within the age budget, or that seven SDK buffers cause gaps?
- Cost to reverse. Low. Change the feed bound or launch-time driver count and repeat the retention and load tests.

### D11. Frame identity and sequence scope

- Position. Assign a receive sequence at each image callback and keep it increasing across starts for the lifetime of the shared subscription. The controller opens a new stream epoch at each logical start or observed outage recovery.
- Evidence. [F] The SDK frame ID feeds only the driver gap log. `Image` has no sequence field, and CycloneDDS leaves both RMW sequence fields unsupported. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1605`, `ros:ros2/common_interfaces/sensor_msgs/msg/Image.msg:4-26`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3274-3285`)
- Rejected options. v1's receive sequence alone hides stream boundaries. A device stamp lacks a verified epoch and identity contract. An SDK frame ID requires a driver or transport change.
- What would change my mind. [Q] Must a consumer identify a sensor frame across independent readers or detect every physical reconnect?
- Cost to reverse. Medium. A stronger identity needs driver metadata, an adapter update, and new reset semantics.

### D12. Loss reporting

- Position. Count callbacks, feed slot evictions, and frames discarded for invalid layout or an inactive epoch. Expose the RMW-reported loss count when supported, plus the time since the last valid frame.
- Evidence. [F] The driver logs incomplete receives, SDK frame ID gaps, and requeue errors. CycloneDDS maps `message_lost` to its DDS sample-lost event, and KEEP_LAST overwrites raise no event. (`driver:vimbax_camera/src/vimbax_camera.cpp:1724-1742`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1595-1638`, `ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3943-3955`, `ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`)
- Reporting rule. Document visibility gaps for driver losses, unreported DDS losses, and reader history overwrites. Report counters over the subscription lifetime and count feed evictions only while a feed has its slot.
- Rejected options. A patched frame ID counter needs a different wire contract. Stall time measures duration and cannot give a frame count. A single total or an unspecified coverage claim obscures where losses can occur.
- What would change my mind. [Q] Does Logan require a count of every missing sensor frame for recording or measurement acceptance?
- Cost to reverse. High for complete loss counts. Add source-side identity and account for resets and gaps at each transport boundary.

### D13. Several consumers

- Position. Allow one open feed and one pending get image request per camera. Fan out one shared immutable frame from the same subscription to both slots when both qualify.
- Evidence. [F] CycloneDDS takes each `Image` through the ordinary receive path. The source exposes no camera sequence for correlating independent readers. (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:2949-2984`, `ros:ros2/common_interfaces/sensor_msgs/msg/Image.msg:4-26`)
- Rejected options. Several feeds with one reader add per-consumer queues and memory policy beyond R1. Several readers also add separate deserialization, history, and receipt order.
- What would change my mind. [Q] Do two in-process consumers need independent feeds at the same time?
- Cost to reverse. Medium. Extend the shared reader to one slot per feed and define a bound across those slots.

### D14. Pixel interpretation

- Position. Keep v1's pass-through of pixels and wire encoding, with Mono8 as the first profile. Document that the driver's Mono12 path emits `mono16` with significant bits in the upper 12 bits.
- Evidence. [F] Mono8 and Mono12 are the two offered formats that pass the gate. The driver shifts Mono12 samples left four bits. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:84-98`, `driver:vimbax_camera/src/vimbax_camera.cpp:1621-1651`, `driver:vimbax_camera/src/vimbax_camera.cpp:1781-1806`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:189-191`)
- Rejected options. Source bit depth would require trusted profile metadata because the wire encoding alone cannot identify Mono12. Shifting back requires a pixel pass and breaks the wire representation.
- What would change my mind. [Q] Does the first consumer need more than eight bits, and does it require original sample values or explicit source bit depth?
- Cost to reverse. Medium. Add verified per-epoch format metadata or a conversion in the consumer and update fixtures.

### D15. Calibration pairing

- Position. Leave `CameraInfo` out of the first frame contract, as in v1. If pairing becomes necessary, treat zero `K[0]` as unavailable calibration.
- Evidence. [F] The driver copies the image header to `CameraInfo` and uses blank calibration on a size mismatch. The c1 driver found no calibration file. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1620-1631`, `ros:ros2/common_interfaces/sensor_msgs/msg/CameraInfo.msg:20-23`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:159-163`)
- Rejected options. Pairing now adds a second reader and a wait policy before R11 requires it. Loading a separate project calibration duplicates the driver's calibration source and risks using a different ROI.
- What would change my mind. [Q] Does the first mapping or measurement consumer need intrinsics for its active ROI and binning?
- Cost to reverse. Medium. Add a bounded join by shared header, a validity check, and calibration for the selected profile.

## Stream control and configuration

### D16. Stream ownership

- Position. Give the acquisition controller exclusive ownership of project stream calls and camera configuration. Count an open feed and a pending get image request as separate users.
- Evidence. [F] Bring-up sets `autostream: 0`. The driver serializes stream calls and can independently request a start after reconnect. (`src/venimapping_bringup/config/camera.yaml:9-12`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:579-618`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1538-1593`)
- Rejected options. A feed that owns its own stop can interrupt a pending get image request. Operator or bring-up control leaves an idle get image request with no owner to start the stream. Autostream can restart on a subscriber count increase.
- What would change my mind. [Q] Must an operator or another process retain authority to start, stop, or change this same camera during project acquisition?
- Cost to reverse. High. Shared authority requires a control protocol that covers stream users and feature writes across clients.

### D17. Feed start, readiness, and close

- Position. Let the frame port arm delivery and report a compatible raw publisher match. Let the controller start the stream if idle and return the feed after a successful start reply.
- Evidence. [F] The publisher uses VOLATILE durability. In c1, the matched reader received the first frame about 79 ms before the Mono8 driver's start log. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:350-357`, `ros:ros2/rmw/rmw/include/rmw/qos_profiles.h:51-62`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:145-163`)
- Delivery rule. A frame may fill the slot while the start reply is pending. Feed close clears its slot and wakes its consumer. The controller queues stop on the gateway worker when the last user releases the stream.
- Rejected options. Arming alone leaves callers responsible for stream control. Subscription creation alone leaves a discovery race. First frame readiness adds a frame wait to open. Always stopping can interrupt get image. Never stopping leaves the camera running with zero users.
- What would change my mind. [Q] Must feed open prove pixel delivery before returning, or must a recorder keep streaming after all project users close?
- Cost to reverse. Medium. Change the controller's open or close transition and update readiness and ownership tests.

### D18. Configuration ownership and order

- Position. Put one verified free-run profile in bring-up's `settings_file` for open and reopen. Before a project start, read back its shape, `PixelFormat`, trigger state, and effective rate.
- Evidence. [F] The driver tries to load the file before it finishes camera initialization. It logs a load failure and continues. The graph thread can then request a reconnect start. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:366-400`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:556-593`)
- Evidence. [F] In c1, `PixelFormat`, `Width`, and the selected `TriggerMode` became read only during acquisition. `ExposureTime` stayed writable. The rate was read only with rate enable false. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:165-185`)
- Profile rule. Use full-sensor Mono8 and free run with `FrameStart` off. Qualify a 30 Hz profile by setting `AcquisitionFrameRateEnable` before `AcquisitionFrameRate` while stopped, then measuring delivery. If qualification fails, keep the measured free-run setting for the probe. Require readback after loading the installed profile. Keep all profile changes outside an active stream in the first phase.
- Rejected options. A power-on `UserSet` puts configuration under a camera-local state that bring-up cannot review. Service writes alone can lose the race with an automatic restart. Live rate or exposure control adds a configuration path before a consumer needs it.
- What would change my mind. [Q] Does a stopped-state test show that the saved profile fails to restore a required setting on reopen?
- Cost to reverse. Medium. Move the affected settings to controller writes and add a verified stop before applying them on reopen.

### D19. Start and stop failure recovery

- Position. Check `PixelFormat` against the intersection of the selected profile and the driver gate before every controller start. If a stream failure leaves a wedge, close frame admission and request a supervised driver restart.
- Evidence. [F] Early errors can leave `kStarting` or `kStopping`. Later stream calls return -15 in either state. The streaming predicate includes `kStarting` and excludes `kStopping`. (`driver:vimbax_camera/src/vimbax_camera.cpp:416-519`, `driver:vimbax_camera/src/vimbax_camera.cpp:527-585`, `driver:vimbax_camera/src/vimbax_camera.cpp:1508-1513`)
- Evidence. [F] c1 found that only Mono8 and Mono12 pass on this camera. The gateway contract warns that a timeout can leave an operation applied. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:84-98`, `src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-52`)
- Recovery rule. After a failed or uncertain operation, preserve its error and use at most one bounded reconciliation stop if the camera is reachable. If the stop returns -15 or stopped state remains unconfirmed, require driver restart. Revalidate the profile and wait for a matched reader before resuming.
- Rejected options. Format checks alone cannot prevent capture or stop failures. Testing -15 with `status.streaming` true misses `kStopping`. Patching before the failure paths have tests risks incomplete cleanup. An operator message alone leaves active users without a recovery path.
- What would change my mind. [Q] Does a fault-injection test show that a fork fix reliably unwinds buffers, the frame worker, and both transitional states?
- Cost to reverse. Medium. Replace the process restart path with tested in-driver cleanup and adjust recovery tests.

### D20. Timestamp source

- Position. Keep v1's `use_ros_time: true` in `camera.yaml` and set `use_sim_time: false` on both nodes. Treat the image stamp as driver processing time and use steady time for local deadlines.
- Evidence. [F] The driver samples `node->now()` after the transform and before publish. With camera stamps in c1, the offset to host receipt changed by about 10.4 ms between the observed formats. (`driver:vimbax_camera/src/vimbax_camera.cpp:1745-1757`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1605-1633`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:123-143`)
- Rejected options. Keeping device time and adding host receipt time leaves driver topics on a different clock and adds executor delay to the project stamp. Offset mapping needs a new estimate after a clock reset or a profile change. Publishing both stamps needs a driver change.
- What would change my mind. [Q] Must the first consumer align exposure with pose or another sensor within a specified error bound?
- Cost to reverse. Medium. Change bring-up time settings and frame metadata, then qualify the new time basis and update epoch admission.

### D21. Driver changes

- Position. Use the pinned driver fork without a first-phase patch, as in v1. Keep autostream off, validate starts, set buffer count only at launch, and supervise driver recovery.
- Evidence. [F] The project README pins the fork tag. The driver dereferences `camera_` in the buffer parameter callback and uses nested shared locking on service start and stop. (`README.md:13-15`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:307-321`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1544-1565`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1587-1591`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1653-1655`)
- Rejected options. Launch policy avoids the autostream guard and the live buffer count hazard. No first-phase consumer needs SDK frame identity or a second wire stamp. A wedge or lock patch needs regression coverage first. VmbC replacement expands camera ownership and maintenance.
- What would change my mind. [Q] Does an unplug or fault test reproduce a driver hang or recovery failure that process supervision cannot correct within the agreed outage budget?
- Cost to reverse. Medium for a targeted patch. Revise the pinned fork and test the affected recovery path against the same camera.

### D22. Disconnect, silence, and outage

- Position. At `max(250 ms, five profile frame periods)` without a valid frame, report a stall and ask the gateway worker to check `connected`. Keep the feed open and admit frames from the driver's reconnect restart after verifying the profile.
- Evidence. [F] `connected` reports whether the driver holds a camera object. The graph thread attempts a reconnect restart and clears the flag without checking the start result. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:545-568`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:579-593`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1520-1527`)
- Recovery rule. Suspend delivery and clear pending frames once the stall starts. Report disconnected if `connected` is false. Poll at 250 ms while a stream user remains. Label service failure as connection unknown. If connected, read back the profile and open a new epoch before admitting frames. Admit only frames stamped after the new epoch boundary. On a detected host clock step, clear pending frames and re-arm the boundary. If no valid frame arrives in another silence interval, attempt one guarded start. If that fails, use D19.
- Recovery with zero users. If a reconnect can still restart the driver, keep delivery closed and reconcile to stopped on reconnect. If a later frame reveals a restart, request stop on the worker.
- Rejected options. A fixed timeout alone can flag a slow profile as stalled. A period multiple alone gives little startup margin at high rates. A stop and restart on every reconnect adds interruption. Closing the feed requires a new caller session after a cable outage.
- What would change my mind. [Q] Must the system mark reconnects shorter than the silence threshold, or does a cable test show that the driver cannot restore this profile reliably?
- Cost to reverse. Medium. Add a driver connection event or change the controller's recovery sequence and epoch tests.

## Get image

### D23. Frame source for get image

- Position. Sample the active free-run stream when a feed is open. If idle, start free run for one eligible frame and stop after the last user releases the stream.
- Evidence. [F] In c1 the first Mono8 frame reached a matched reader 29.7 ms after the buffer alignment log. Start and stop each use a command poll with a 100 ms sleep. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:145-162`, `driver:vimbax_camera/src/vimbax_camera.cpp:503-510`, `driver:vimbax_camera/src/vimbax_camera.cpp:527-535`, `driver:vimbax_camera/src/vimbax_camera.cpp:674-688`)
- Rejected options. Sampling only fails while idle. Starting and stopping on every call interrupts an open feed. Software triggering requires exclusive trigger setup. v1's per-call strategy adds that path before R6 requires exposure freshness.
- What would change my mind. [Q] Does Logan require exposure after the request, or does get image run often enough for cold starts to miss its latency target?
- Cost to reverse. Medium. Add a trigger strategy or a stream hold policy and qualify it on hardware.

### D24. Freshness rule

- Position. Return the first valid frame admitted by the image callback after the request arms its slot. Order admission and arming under the same lock and measure the deadline with a steady clock.
- Evidence. [F] The driver can queue and transform a frame before publication. Its host stamp in D20 precedes ROS delivery. (`driver:vimbax_camera/src/vimbax_camera.cpp:458-482`, `driver:vimbax_camera/src/vimbax_camera.cpp:1745-1757`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1605-1633`)
- Admission rule. The slot takes one frame from an eligible epoch and keeps it until the pending request takes it or ends. A frame admitted after arming can contain an earlier exposure.
- Rejected options. A host stamp after the request enforces a different event and depends on clock behavior. Exposure after the request needs controlled triggering or a verified map to camera time.
- What would change my mind. [Q] Must the answer prove that the driver published after the request, or that exposure started after it?
- Cost to reverse. Medium. Change the admission predicate and qualify its time basis or add trigger association.

### D25. Idle behavior and subscription lifetime

- Position. Keep one raw subscription for the controller lifetime, including idle. Arm the get image slot before a cold start and stop the stream when the last user releases it.
- Evidence. [F] With `autostream: 0`, a new reader does not start the driver. The c1 first frame preceded the start reply. (`src/venimapping_bringup/config/camera.yaml:9-12`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:588-618`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:145-163`)
- Idle rule. The idle subscription holds no admitted frame. A cold call waits for a compatible match before start. At an epoch start, a driver host stamp floor excludes late callbacks from the old stream.
- Rejected options. A temporary reader adds discovery and teardown to each cold call. A persistent stream spends camera and DDS bandwidth with zero active users. Failing while idle would remove cold get image.
- What would change my mind. [Q] Does a host test show that per-call matching stays inside the cold deadline under load, or that an idle reader conflicts with a deployment requirement?
- Cost to reverse. Low. Move reader creation and destruction into the controller's cold path and retain the match check.

### D26. Deadline and timeout result

- Position. Use one absolute steady deadline from request entry through any matching, readback, start, frame wait, and required stop. Return a deadline error for get image and an empty result for an ordinary feed pull timeout.
- Evidence. [F] The gateway currently sets one timeout per call. A local timeout removes the pending request, and the driver can still apply the operation. Start and stop have the command poll floor. (`src/venimapping_camera/include/venimapping_camera/vimbax_camera_gateway.hpp:45-61`, `src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:79-94`, `driver:vimbax_camera/src/vimbax_camera.cpp:503-510`, `driver:vimbax_camera/src/vimbax_camera.cpp:527-535`, `driver:vimbax_camera/src/vimbax_camera.cpp:674-688`)
- Budget rule. [A] Cap a cold request at 2 s and reserve its last 250 ms for stop. Cap a warm request at two profile frame periods. Honor a shorter caller deadline. If a cold deadline cannot fit the stop reserve, return a deadline error before starting. Add deadline-aware gateway calls for this path. Return the request result by its deadline even when the worker must finish reconciliation later. If stop fails, preserve its error or record it alongside an earlier request error. Block new starts until the worker confirms stopped state or D19 recovers it.
- Rejected options. Independent step budgets can exceed the caller's total wait. An empty get image result hides whether the promised capture completed. A successful frame return before a required stop hides an uncertain stream state.
- What would change my mind. [Q] Do loaded cold runs show that the 250 ms stop reserve is too small, or can callers accept a longer total deadline?
- Cost to reverse. Low for time values. Update the stop reserve and caller limits using measured service and frame latencies.

### D27. Trigger association and restore

- Position. Defer software triggering in the first phase. If exposure freshness becomes a requirement, use a matched, quiet, exclusive stream and take the first frame after command dispatch for one outstanding command.
- Evidence. [F] c2 saw seven commands yield one frame each and two successful replies yield none. It observed selector-dependent writes go to a different selector after `status`. (`docs/architecture/image-acquisition-planning/claude/camera/c2.md:98-130`)
- Evidence. [F] The command reply carries no frame identity. The command poll can leave the reply pending while frames arrive. (`driver:vimbax_camera_msgs/srv/FeatureCommandRun.srv:1-4`, `driver:vimbax_camera/src/vimbax_camera.cpp:458-482`, `driver:vimbax_camera/src/vimbax_camera.cpp:674-688`)
- If trigger support lands, use this order.

  1. Block `status` and other selector clients until restore completes.
  2. While stopped, save the selector and each available selector's mode and source.
  3. Set up `FrameStart`, `TriggerMode=On`, and `TriggerSource=Software`.
  4. Before each selector-dependent operation, select its target again.
  5. After the reader matches, start the stream.
  6. After a quiet interval, arm the slot at command dispatch.
  7. Send one `TriggerSoftware` command.
  8. If the reply is uncertain or no frame arrives, end the request without retrying the command.
  9. On every exit, stop the stream before restoring modes and sources.
  10. If stop fails, use D19 before restoring the trigger state.
  11. Verify restored values under their selectors.
  12. Restore the original selector last.

- Rejected options. Taking the first frame after the reply can miss the commanded frame. Device stamps lack a verified exposure event and host map. A quiet interval alone provides no command identifier. A successful reply alone does not establish that a frame arrived.
- What would change my mind. [Q] Does Logan require exposure after the request and allow exclusive camera use during a trigger capture?
- Cost to reverse. High. Add a trigger state machine, uncertain-command recovery, and hardware tests for association and restore.

### D28. Get image during an open feed

- Position. Share the feed stream and satisfy get image through its independent slot. Leave the pending feed frame available to its consumer.
- Evidence. [F] The driver publishes one raw image stream, and the gateway exposes start and stop for that stream. c1 found that `TriggerMode` was locked during acquisition. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:350-364`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1538-1574`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:165-179`)
- Rejected options. Pausing the feed violates R8 and adds stop and start delays. Returning an error wastes a running stream. Draining the feed queue as in v1 steals frames from its consumer.
- What would change my mind. [Q] Must get image use a different camera profile or trigger mode, and may it interrupt the feed?
- Cost to reverse. High. A separate capture mode adds feed interruption, profile restore, and epoch rules.

### D29. Get image caller interface

- Position. Keep a C++ `get_image` call on the controller in the first phase, as in v1. Return `Expected<ImageFrame>` to the local caller.
- Evidence. [F] The project launch starts the driver, and the camera package builds a gateway library and temporary probe. The driver service definitions expose controls and no image response. (`src/venimapping_bringup/launch/camera.launch.py:35-41`, `src/venimapping_camera/CMakeLists.txt:22-56`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:660-1579`)
- Rejected options. Adding a ROS service now requires a large reply and a service callback scheduling contract before R1 needs them. A ROS-only service also couples the local caller to serialization and discovery.
- What would change my mind. [Q] Does a named process need to request a single frame and receive it through a ROS API?
- Cost to reverse. Medium. Add a thin service adapter with reply size, deadline, and worker scheduling tests.

## Working assumptions

### Requirements

| ID | Acceptance and reason |
|---|---|
| R1 | [A] Accept one local C++ consumer for the first phase. A named second consumer can change D1, D2, D7, D13, or D29. |
| R2 | [A] Accept full sensor and no binning for the first profile. Read dimensions and stride per frame so a different ROI changes payload estimates and profile checks. [F] c1 measured 1296 × 1032 at both formats. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:100-109`) |
| R3 | [A] Accept Mono8. Enable Mono12 if the first consumer needs its extra bits. D14 defines how the consumer sees the shifted samples. [F] Both formats pass the gate on this camera. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:84-98`) |
| R4 | [A] Accept 30 Hz as a target, conditional on qualification. Size the load test for the measured setting until rate control passes. [F] The observed Mono8 free run was 69.721 Hz. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:111-119`) |
| R5 | [A] Accept a count bound on pending payloads. D10 also counts the get image slot. Consumer retention can exceed those two slots. [F] c1 gives byte sizes for both formats. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:100-109`) |
| R6 | [A] Accept receipt after arming. The shared stream then serves both operations. D23, D24, and D27 change if Logan needs exposure after the request. |
| R7 | [A] Accept 2 s cold and two profile frame periods warm as initial deadlines. Treat them as wait limits and verify the success rate under load. D25 and D26 use these limits. |
| R8 | [A] Accept less than one get image request per second and overlap with an open feed. Keep the feed running and allow one outstanding request. A higher rate can change idle policy or request limits. |
| R9 | [A] Accept a feed that favors new frames and reports observed drops. D9, D10, and D12 follow this policy. A lossless requirement would change reader and camera ownership decisions. |
| R10 | [A] Accept a shared live host clock and no hardware synchronization. D20 uses driver processing time. Exposure alignment requires a new time contract. |
| R11 | [A] Accept frames without intrinsics in the first phase. A consumer that requires calibration changes D3 and D15. |
| R12 | [A] Accept one host and CycloneDDS. Confirm the RMW selection at launch. [F] The environment script preserves an existing RMW choice. (`scripts/env.sh:127-134`) |
| R13 | [A] Accept the pinned fork without patches in the first phase. Keep restart recovery and measure it before deciding on a fix. D11, D12, D19, and D21 depend on this. |
| R14 | [A] Accept a feed that stays open across observed outages. A short reconnect may leave no observed boundary. Reliable identification of every physical reconnect changes D11 and D22. |
| R15 | [A] Accept one writer and stream owner. Extend the future trigger exclusion through command dispatch and restore. [F] c2 observed `status` move the selector during setup. (`docs/architecture/image-acquisition-planning/claude/camera/c2.md:122-130`) |
| R16 | [A] Accept reapplying the profile on every reopen. Leave actual feature persistence open and verify the profile before admitting frames. [F] The driver attempts to load the settings file on camera initialization. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:366-400`) |

### Technical assumptions

| ID | Acceptance and reason |
|---|---|
| T1 | Accept as confirmed. [F] Mono8 and Mono12 are the two offered formats in the driver gate. D14 and D19 use that intersection. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:84-98`, `driver:vimbax_camera/src/vimbax_camera.cpp:1621-1651`) |
| T2 | Replace symbolic sizes for the tested profile. [F] c1 measured 1,337,472 bytes at Mono8 and 2,674,944 bytes at Mono12. D10 budgets by measured payload. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:100-109`) |
| T3 | Accept 30 Hz or more for the measured conditions. [F] c1 delivered 69.721 Hz at Mono8 and 45.124 Hz at Mono12. The results do not establish a configured 30 Hz cap. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:111-119`) |
| T4 | Accept the clock mismatch. [F] c1 found no `DeviceTimestampFrequency` and observed different device and host origins. [Q] The device epoch and exposure event remain unknown. D20 uses the driver host stamp. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:123-143`) |
| T5 | Reject the greater-than-100 ms first-frame assumption. [F] c1 measured 29.7 ms for Mono8 and 43.1 ms for Mono12 from the driver buffer log to the first receipt. The start log came later. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:145-162`) |
| T6 | Replace general uncertainty with the c2 result. [F] The features exist. Seven commands gave one frame each, and two gave none despite successful replies. [Q] One-command association under exclusive selector control still needs qualification if D27 lands. (`docs/architecture/image-acquisition-planning/claude/camera/c2.md:88-130`) |
| T7 | Accept the measured lock on `PixelFormat` and `Width`, and accept live `ExposureTime` access. [F] The tested `TriggerMode` was read only during acquisition. [Q] Live rate access with rate enable true remains open. D18 avoids live writes. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:165-179`) |
| T8 | Replace unknown with the measured result. [F] Rate enable exists, was false, and was writable in both states. [Q] A stopped-state check must establish whether enabling it permits and delivers the 30 Hz setting. (`docs/architecture/image-acquisition-planning/claude/camera/c1.md:165-185`) |
| T9 | [A] Accept slow-reader blocking as a risk for D9 and D10. [F] The driver requeues after publish. [Q] The timing and gap count under reader load remain unmeasured. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1631-1638`, `docs/architecture/image-acquisition-planning/claude/camera/c1.md:206-215`) |
| T10 | [A] Reject raw-only installation as a design dependency. [Q] The installed plugins are unknown. D8 selects the raw topic regardless. [F] Plugin availability and the enable filter control the extra transports. (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:112-155`) |
| T11 | [A] Treat socket tuning as unverified. Record host limits before the D9 load test. [F] The local CycloneDDS guidance gives 8,388,608 bytes for receive limits. (`ros:ros2/rmw_cyclonedds/README.md:27-32`) |
| T12 | [A] Reject tens of milliseconds as a deadline bound. D17 and D25 wait on the match within the caller budget. [Q] Measure matching under host load with the selected QoS. |

### Other assumptions in the reconciled facts

- [A] Accept the risk from the buffer-count null dereference. D10 and D21 keep that setting at launch. [F] The parameter callback dereferences `camera_`, and disconnect resets it. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:307-321`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:545-555`)
- [A] Accept the nested shared lock as a recovery risk. [Q] Unplug testing must establish whether start or stop hangs on this deployment. D21 keeps a targeted fix conditional on that result. [F] The service handlers and stream functions both acquire `camera_mutex_`. (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1544-1565`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1587-1591`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:1653-1655`)
- [A] Retire the trigger feature availability assumption for c2. [F] c2 found `FrameStart`, `Software`, and `TriggerSoftware`. A different camera still needs feature discovery. (`docs/architecture/image-acquisition-planning/claude/camera/c2.md:90-96`)
- Accept the resolutions of X8 and X9. [F] The reader history overwrite path raises no sample-lost event. ROS launch applies both remaps. (`ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`, `ros:ros2/launch_ros/launch_ros/launch_ros/actions/node.py:492-494`, `ros:ros2/rcl/rcl/src/rcl/node.c:204-229`)
