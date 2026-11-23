## Data-plane source tree

Use the existing `venimapping_camera` package (`d1`, `ic0`, `ic8`). [F] Its build installs headers from `include/` and exports targets through `export_${PROJECT_NAME}`. (`src/venimapping_camera/CMakeLists.txt:58-75`)

| File | Proposed change |
|---|---|
| `src/venimapping_camera/include/venimapping_camera/image_frame.hpp` | Add `ImageFrameFields`, `ImageFrame::create`, and read-only accessors. Declare `FrameFanout` as a friend and add the private `stage` factory. |
| `src/venimapping_camera/include/venimapping_camera/frame_source.hpp` | Add the ROS-free source and subscription ports, queue options, epoch result, and stats types. Include both callback duration fields in `FrameSourceStats`. |
| `src/venimapping_camera/src/image_frame.cpp` | Validate layout and allocate the shared frame block. Retain the type-erased pixel owner in the block. |
| `src/venimapping_camera/src/frame_support/frame_fanout.hpp` | Declare `FrameFanoutClock` and `FrameFanout` in `venimapping::camera::frame_support`. Declare the shared state and queue block used by concrete subscriptions. |
| `src/venimapping_camera/src/frame_support/frame_fanout.cpp` | Add the bounded queues, pull and close operations, admission checks, and counters. Allocate queue storage and list nodes before locking. Release frame holders and detached list nodes after unlocking. |
| `src/venimapping_camera/include/venimapping_camera/vimbax_frame_source.hpp` | Add the pinned VimbaX adapter and its factory for a caller-owned node. |
| `src/venimapping_camera/src/vimbax_frame_source.cpp` | Hold the production clock and `FrameFanout` by value in the adapter's private implementation block. Reject an empty namespace before subscribing. Translate images and report publisher matches and RMW loss events. |
| `src/venimapping_camera/CMakeLists.txt` | Build, install, and export `venimapping_camera_frame_api` over `venimapping_camera_gateway_api`. Add, install, and export `venimapping_camera_vimbax_frame_source` in the adapter step with `rclcpp` and `sensor_msgs`. |
| `src/venimapping_camera/package.xml` | Add the `sensor_msgs` dependency in the adapter step. |

The frame API target compiles `src/image_frame.cpp` and `src/frame_support/frame_fanout.cpp` without ROS headers or libraries. The adapter target links the frame API and keeps the ROS subscription private. Add `find_package(sensor_msgs REQUIRED)` in the adapter step. Export the dependency in that step. Keep `src/frame_support/` private. The package test targets can include that directory (`ic7`, `ic8`).

Both sources hold `FrameFanout` by value. The clock must outlive it. The adapter constructs its clock before its `FrameFanout`. `FakeFrameSource` borrows its test clock. Concrete subscriptions retain their queue block and shared state, so their methods work after `FrameFanout` closes the queues and goes away (`ic2`, `ic7`).
