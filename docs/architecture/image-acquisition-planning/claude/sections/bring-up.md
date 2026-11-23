## Bring-up

`venimapping_bringup` starts the driver with values that the acquisition code depends on. This section lists the parameter, launch, file, and namespace changes, and the checks that prove them (ic6, d8, d10, d15, d18, d20).

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption. `[Q]` is an open question. `ros:path:line` is from the ROS source root. `vimbax:path:line` is from `/opt/vimbax`.

### What exists today

1. `[F]` `camera.launch.py` starts `vimbax_camera/vimbax_camera_node` with the node name `vimbax_camera`. The namespace comes from the launch argument `camera_namespace`, default `/vimbax_camera`. Parameters come from the launch argument `params_file` (`src/venimapping_bringup/launch/camera.launch.py:19-41`).
2. `[F]` `camera.yaml` sets only `camera_id: "0GPF3"` and `autostream: 0` under the key `/**/vimbax_camera` (`src/venimapping_bringup/config/camera.yaml:9-12`).
3. `[F]` The package installs `config/` and `launch/` and has no tests (`src/venimapping_bringup/CMakeLists.txt:14`).
4. `[F]` All other driver parameters keep their defaults: `buffer_count` 7, `use_ros_time` false, `settings_file` and `camera_info_url` empty (`driver:vimbax_camera/src/vimbax_camera_node.cpp:276-305`, `:415-418`).
5. `[F]` `settings_file` and `camera_info_url` are read-only parameters. `use_ros_time` and `buffer_count` can change at run time (`driver:vimbax_camera/src/vimbax_camera_node.cpp:282-305`, `:415-418`).
6. `[F]` The launch `Node` sets no `output` argument (`src/venimapping_bringup/launch/camera.launch.py:35-41`). The default `output` is `log`, which also sends the process stderr to the screen (`ros:ros2/launch/launch/launch/actions/execute_process.py:217-219`).

### Driver parameters

New `camera.yaml`:

```yaml
/**/vimbax_camera:
  ros__parameters:
    camera_id: "0GPF3"
    autostream: 0
    buffer_count: 7
    use_ros_time: true
    use_sim_time: false
    image_raw:
      enable_pub_plugins: ["image_transport/raw"]
```

| Key | Value | Reason | Register |
|---|---|---|---|
| `autostream` | `0`, no change | `[F]` With 0, only a `stream_start` call and the reconnect restart start the stream (facts 1.4.12). The controller owns the stream. | d16 |
| `buffer_count` | `7`, now written | `[F]` About 3100 Mono8 frames and 630 Mono12 frames streamed at 7 with no "frames missing" log (c1 §3.7 item 2). `[A]` A run-time change during a disconnect crashes the driver (facts 1.10.2), so only this file sets it. | d10, d21 |
| `use_ros_time` | `true` | `[F]` The driver then sets `header.stamp = node_->now()` after the transform and before publish (`driver:vimbax_camera/src/vimbax_camera_node.cpp:1608-1609`). `ImageFrame::host_stamp_ns` comes from that stamp. | d20 working assumption |
| `use_sim_time` | `false` | `[F]` With sim time off, the ROS clock reads `CLOCK_REALTIME` (`ros:ros2/rcl/rcl/src/rcl/time.c:62-72`). | d20 |
| `image_raw.enable_pub_plugins` | `["image_transport/raw"]` | `[F]` `image_transport` advertises one subtopic per installed plugin unless this list limits it (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:114-153`). The filter makes the topic set the same on each host. | d8 |
| `camera_info_url` | not set | `[F]` No calibration exists for this camera (c1 §3.5 item 5). Phase 1 has no `CameraInfo`. | d15 |
| `settings_file` | set by the launch file | See "Camera settings file". | d18 |

1. `[F]` The parameter name for the plugin filter is the topic name relative to the node namespace, with `/` changed to `.`, plus `.enable_pub_plugins` (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:114-128`). For `image_raw`, it is `image_raw.enable_pub_plugins`.
2. `[F]` `image_transport` declares that parameter on the driver node, with all installed plugins as the default (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:127-128`). A wrong key in `camera.yaml` therefore leaves the default, and a read of the live parameter shows it.
3. `[F]` The driver reads `use_ros_time` on each frame, so a change during a stream changes the time basis between two frames (facts 1.6.4). No project code changes it while acquisition runs (d20 decided item 2).
4. `[F]` `camera_info` still publishes, because the driver uses a `CameraPublisher` (facts 1.3.1). It carries only width and height (facts 1.8.2). The filter does not affect it.

### Launch file

`camera.launch.py` gets two launch arguments. Both pass to the driver after `params_file`, so they win over the file.

```python
DeclareLaunchArgument(
    "use_ros_time",
    default_value="true",
    description="Host header stamps. Only the device stamp probe sets false.",
),
DeclareLaunchArgument(
    "settings_file",
    default_value=PathJoinSubstitution(
        [FindPackageShare("venimapping_bringup"), "config", "camera_settings.xml"]
    ),
    description="Camera feature file that the driver loads on each open.",
),
Node(
    package="vimbax_camera",
    executable="vimbax_camera_node",
    namespace=LaunchConfiguration("camera_namespace"),
    name="vimbax_camera",
    parameters=[
        LaunchConfiguration("params_file"),
        {
            "use_ros_time": LaunchConfiguration("use_ros_time"),
            "settings_file": LaunchConfiguration("settings_file"),
        },
    ],
),
```

1. `[F]` `launch_ros` reads a substituted parameter value as YAML, so `"true"` becomes a boolean (`ros:ros2/launch_ros/launch_ros/launch_ros/utilities/evaluate_parameters.py:71-79`).
2. `[A]` A later entry in `parameters` overrides an earlier one for the same name. The rig check reads both values back, so a wrong order fails the check.
3. `settings_file` must be an absolute installed path. A YAML file cannot use `FindPackageShare`, so the launch file sets it (d18 item 1).
4. The `use_ros_time` argument exists only for the device stamp probe run (d20 item 6). That run uses `use_ros_time:=false` and never uses the controller.

### Camera settings file

New file `config/camera_settings.xml`. The driver loads it on each open and reopen (d18 item 1).

1. `[F]` The driver loads `settings_file` inside `initialize_camera`. On a reconnect, it sets the restart flag only after that function returns (`driver:vimbax_camera/src/vimbax_camera_node.cpp:390-400`, `:561-566`). The file is therefore the only way to apply the profile before the driver restarts the stream.
2. `[F]` The driver saves and loads with one fixed setting: persistence type `VmbFeaturePersistNoLUT`, module flags `RemoteDevice | LocalDevice | Streams`, and 10 load iterations (`driver:vimbax_camera/src/vimbax_camera.cpp:1358-1367`).
3. `[F]` `VmbFeaturePersistNoLUT` means all features except look-up tables (`vimbax:api/include/VmbC/VmbCTypeDefinitions.h:473-475`). The SDK repeats the load up to the iteration count, because one write can change a feature that it set before (`vimbax:doc/VimbaX_Documentation/cAPIManual.html:1470-1479`).
4. Scope: the file can hold features of the camera, the local device module, and the stream module. It holds no system or interface feature. `[A]` The SDK saves each feature of those modules that it can read. The module flags alone do not prove that each feature is in the file. Review the saved file to see its content.
5. `[F]` The save service accepts only a `.xml` name (`driver:vimbax_camera/src/vimbax_camera.cpp:1335-1337`).
6. `[F]` A missing file returns -3, and the driver only logs a failed load. The driver continues (`driver:vimbax_camera/src/vimbax_camera.cpp:1312-1314`, `driver:vimbax_camera/src/vimbax_camera_node.cpp:394-399`).

The failed-load line:

1. `[F]` The driver logs the message `Loading settings from file <path> failed with error <code> (<text>)` through `RCLCPP_ERROR` (`driver:vimbax_camera/src/vimbax_camera_node.cpp:395-398`). It is the only driver log text that contains `Loading settings from file`, and the driver logs it only on a failed load.
2. `[F]` The default console format is `[{severity}] [{time}] [{name}]: {message}` (`ros:ros2/rcutils/src/logging.c:88-89`). Console output goes to stderr by default (`ros:ros2/rcutils/src/logging.c:659-670`).
3. `[F]` `launch` puts `[<process name>] ` before each line of process output (`ros:ros2/launch/launch/launch/actions/execute_local.py:91`).
4. So the message is in the middle of the console line, after two prefixes. Each check in this document matches the text anywhere in the line, with `grep -F 'Loading settings from file'`.

The controller readback is a check of the seven listed profile values and the selector write only (d18 item 3). It does not check any other feature in the file. It also cannot see a failed load when the camera already holds the listed values. The rig check below uses the failed-load line and a controlled reopen to see the load result.

`[A]` A change to a feature outside the profile enters through the file with no readback (N7). Review the file diff in each change to `camera_settings.xml`.

Make the file on the rig. Do these steps with the stream stopped and the driver started without `settings_file`:

1. Write `PixelFormat` `Mono8`, `Width` 1296, and `Height` 1032.
2. Write `TriggerSelector` `FrameStart`, then write `TriggerMode` `Off`.
3. Write `AcquisitionFrameRateEnable` `true`.
4. Write `AcquisitionFrameRate` 30.0.
5. Write `ExposureTime` 4999.455.
6. Do not call the `status` service between steps 2 and 6. It moves `TriggerSelector` (facts 1.5.7).
7. Call `settings/save` with an absolute `.xml` path.
8. Copy the file to `src/venimapping_bringup/config/camera_settings.xml`.
9. Run the bring-up checks in this section.

`[F]` c3 wrote steps 3 and 4 on this camera while stopped. The read back was 30.000001907348633 Hz, and the stream gave 30.010 Hz (c3 §3 items 2 to 4).

`[A]` The file holds values for this one camera, `0GPF3`. A new camera needs a new file.

### Acquisition profile file

New file `config/acquisition_profile.yaml`. It holds the values that the controller expects (d18 item 2). The composition root reads it as ROS parameters and fills `AcquisitionProfile`. The controller stays ROS-free.

```yaml
/**:
  ros__parameters:
    use_sim_time: false
    profile:
      pixel_format: "Mono8"
      width: 1296
      height: 1032
      trigger_mode: "Off"
      acquisition_frame_rate_enable: true
      acquisition_frame_rate: 30.0
      exposure_time: 4999.455
      allowed_formats: ["Mono8"]
```

1. The file goes only to the application node through `--params-file`. The key `/**` therefore reaches no other node.
2. `use_sim_time: false` on the application node keeps its clock on `CLOCK_REALTIME` (d20 decided item 1).
3. `[A]` P2: the settings file and this file describe the same values. The rig check proves it.
4. In phase 1, the application node is the feed probe, `camera_feed_probe`. It declares `camera_namespace` with the default `/vimbax_camera`, as `camera_gateway_probe` does (`src/venimapping_camera/src/camera_gateway_probe.cpp:136`).

### Namespace

1. The launch argument `camera_namespace` stays the only source of the driver namespace.
2. The application node passes one `camera_namespace` string to `VimbaXCameraGateway::create` and to `VimbaXFrameSource::create` (ic6).
3. `[F]` Both adapters remove trailing slashes and append the leaf (`src/venimapping_camera/src/gateway_support/vimbax_service_calls.hpp:36-46`). The same string therefore gives `/vimbax_camera/image_raw` and `/vimbax_camera/stream_start`.
4. If the launch argument changes, the application node needs the same value. A wrong value gives a gateway error from the readback, or `kSubscriptionNotMatched`.

### Package changes

| File | Change |
|---|---|
| `config/camera.yaml` | New keys in "Driver parameters" |
| `config/camera_settings.xml` | New. The phase 1 camera profile |
| `config/acquisition_profile.yaml` | New. The expected values for readback |
| `launch/camera.launch.py` | Two launch arguments and the parameter override |
| `CMakeLists.txt` | An `if(BUILD_TESTING)` block with `ament_add_pytest_test` for `test/test_camera_config.py` |
| `package.xml` | `test_depend` on `ament_cmake_pytest` and `python3-yaml` |
| `test/test_camera_config.py` | New. The configuration test without a camera |

The `install(DIRECTORY config launch ...)` line already installs the new files (`src/venimapping_bringup/CMakeLists.txt:14`).

### Checks

Configuration test without a camera, `test/test_camera_config.py`:

1. Load `config/camera.yaml`. Check each value in "Driver parameters".
2. Load `config/acquisition_profile.yaml`. Check that each `allowed_formats` entry is `Mono8` or `Mono12`.
3. Call `generate_launch_description()`. Check that the arguments `use_ros_time` and `settings_file` exist with their defaults.
4. Old behavior: `camera.yaml` has no `use_ros_time` key and the launch file has no `settings_file` argument, so the test fails. New behavior: it passes.

The rig check has two parts. The operator does part A, and `camera_feed_probe` with `mode:=bringup` does part B (ic6 item 3, d18 item 8, d20 items 7 and 8). Part A makes a controlled reopen from known different values, so a pass proves that the installed file applied.

Each launch in part A writes the console output to a file. The step 11 launch is an example:

```sh
ros2 launch venimapping_bringup camera.launch.py 2>&1 | tee driver_b.log
```

Part A, the controlled reopen:

1. Launch the driver with `settings_file:=/nonexistent.xml`. Write its console output to `driver_control.log`.
2. Run `grep -F 'Loading settings from file' driver_control.log`.
3. If step 2 prints no line, the capture does not show the failed-load line. Stop the check and fix the capture.
4. Stop the driver.
5. Launch the driver with the default arguments. Write its console output to `driver_a.log`.
6. With the stream stopped, write `ExposureTime` 10000.0 with the CLI.
7. Write `AcquisitionFrameRate` 20.0 with the CLI.
8. Read back `ExposureTime` and `AcquisitionFrameRate` with the CLI.
9. If a value in step 8 differs from the written value by more than 0.001, stop the check. Record that the camera did not take the part A values.
10. Stop the driver.
11. Launch the driver again with the default arguments. Write its console output to `driver_b.log`.
12. Run `grep -F 'Loading settings from file' driver_a.log driver_b.log`.
13. If step 12 prints a line, the check fails.

Notes on part A:

1. Steps 1 to 3 prove that the check can fail. A capture that misses stderr, or a match on the wrong text, stops the check at step 3.
2. Step 9 makes sure that the camera held 10000.0 and 20.0 before the reopen. Part B step 6 then fails if the file did not set the profile values.
3. `[F]` `AcquisitionFrameRate` is writable only while `AcquisitionFrameRateEnable` is true (c1 §3.6 item 2, c3 §3 item 2). Step 5 loads the file, which sets the enable to true.
4. `[A]` The camera keeps written values across a driver restart without a power cycle. If it does not, the camera returns to its own defaults. c1 read 69.7 Hz with the enable false as the default (c1 §3.6 item 2), so part B still fails on a failed load.
5. The launch in step 1 also loads no profile. The camera keeps its last values, and step 5 loads the file again.

Part B, `camera_feed_probe` with `mode:=bringup`, before any `stream_start`:

1. Read the driver parameter `use_ros_time`. Fail on `false`.
2. Read the driver parameter `settings_file`. Fail if it is not the installed path of `camera_settings.xml`, or if no file exists at that path.
3. Read the driver parameter `image_raw.enable_pub_plugins`. Fail if it is not `["image_transport/raw"]`.
4. Read the publishers of `<namespace>/image_raw` from the graph. Fail if the count is not 1.
5. List the topics under the namespace. Fail if a topic name starts with `<namespace>/image_raw/`.
6. Read back the profile through the controller readback code, with no corrective write. Fail on any difference. After part A, this proves that the file set `ExposureTime` and `AcquisitionFrameRate`.
7. Start the stream through the controller. Wait at most 2000 ms for the first frame on a raw subscription. Fail at the limit.
8. Fail if the first `header.stamp` differs from the receipt time on `CLOCK_REALTIME` by more than 1 s.
9. Stop the stream.

Notes on part B:

1. The prefix rule in step 5 finds each plugin topic, because each extra image topic from a plugin is a subtopic of `image_raw` (`ros:ros-perception/image_common/image_transport/src/publisher.cpp:142-147`). This replaces the ic6 item 3.2 wording (N6).
2. Step 4 makes step 5 fail when `image_raw` has no publisher. An empty topic list cannot pass.
3. The 2000 ms limit is about 18 times the measured 110 ms from `stream_start` to the first frame (c1 §3.5 items 1 and 2).

Old behavior: the launch file has no `settings_file` argument, so the driver loads no file, and part A stops at step 3. Part B step 1 fails, because `use_ros_time` is false (facts 1.1.5). Step 2 fails, because `settings_file` is empty. Step 6 fails, because the camera keeps 10000.0 and 20.0 from part A. Step 8 fails, because the stamp is about 12674 s of camera clock (c1 §3.4 item 3). New behavior: all steps pass.

### Host check

`[F]` The driver README asks for the Cyclone DDS tuning in the ROS DDS tuning guide (`driver:README.md:35-36`). The Cyclone DDS README gives `net.core.rmem_max=8388608` and `net.core.rmem_default=8388608` (`ros:ros2/rmw_cyclonedds/README.md:30-31`).

1. Run `sysctl net.core.rmem_max net.core.rmem_default` on the driver host.
2. If a value is less than 8388608, record it in the probe report.

No code depends on these values (ic6 item 4, T11). v1 proposed a project `cyclonedds.xml` (v1 §15.5). v2 does not add it, because one host with tuned kernel buffers needs no file, and no measurement shows a loss without it.

`[F]` `env.sh` keeps a `RMW_IMPLEMENTATION` value that the user already set (`scripts/env.sh:127-134`). The probe report prints the RMW in use, because `transport_lost` and the loan rules depend on Cyclone DDS (d12, facts 1.3.13).
