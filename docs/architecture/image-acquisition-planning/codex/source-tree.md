## Data-plane source tree

Use the existing `venimapping_camera` package (`d1`, `ic0`, `ic8`). [F] Its build installs headers from `include/` and exports targets through `export_${PROJECT_NAME}`. (`src/venimapping_camera/CMakeLists.txt:58-75`)

| File | Proposed change |
|---|---|
| `src/venimapping_camera/include/venimapping_camera/image_frame.hpp` | Add `ImageFrameFields`, the checked `ImageFrame` factory, and read-only accessors for shared frame storage. |
| `src/venimapping_camera/include/venimapping_camera/frame_source.hpp` | Add the ROS-free source and subscription ports, queue options, epoch result, and stats types. |
| `src/venimapping_camera/src/image_frame.cpp` | Add layout validation and the shared frame block that retains the type-erased pixel owner. |
| `src/venimapping_camera/src/frame_support/frame_fanout.hpp` | Declare the private fan-out, injectable clocks, and message entry point used by the adapter and testing fake. |
| `src/venimapping_camera/src/frame_support/frame_fanout.cpp` | Add the bounded queues, pull and close operations, admission checks, and source and subscription counters. |
| `src/venimapping_camera/include/venimapping_camera/vimbax_frame_source.hpp` | Add the pinned VimbaX adapter type and its caller-owned node factory. |
| `src/venimapping_camera/src/vimbax_frame_source.cpp` | Subscribe to `image_raw`, translate each message, and report publisher matches and RMW loss events. |
| `src/venimapping_camera/CMakeLists.txt` | Build and export `venimapping_camera_frame_api` over `venimapping_camera_gateway_api`, then add `venimapping_camera_vimbax_frame_source` with `rclcpp` and `sensor_msgs`. |
| `src/venimapping_camera/package.xml` | Add the `sensor_msgs` dependency in the adapter step. |

The frame API target compiles `src/image_frame.cpp` and `src/frame_support/frame_fanout.cpp` without ROS headers or libraries. The adapter target links the frame API and keeps the ROS subscription private. Add `find_package(sensor_msgs REQUIRED)` and export the dependency in the adapter step. Keep `src/frame_support/` private. The test targets may include that directory in the package build (`ic7`, `ic8`).
