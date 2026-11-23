## Task: implement the step 1 files

Read section 10, "Bring-up", and section 13, "Step 1. Bring-up parameters and
files", of the v2 design. Read the current files in `src/venimapping_bringup/`
in the worktree. Then make these changes in the output root:

1. In `config/camera.yaml`, set the keys in "Driver parameters".
2. Make `config/acquisition_profile.yaml` with the content in "Acquisition
   profile file". Add a file header.
3. In `launch/camera.launch.py`, add the two launch arguments and the
   parameter override in "Launch file". Keep `camera_namespace` and
   `params_file`.
4. In `CMakeLists.txt`, add an `if(BUILD_TESTING)` block. Use
   `find_package(ament_cmake_pytest REQUIRED)` and `ament_add_pytest_test`
   for `test/test_camera_config.py`. Keep the `install(DIRECTORY ...)` line.
5. In `package.xml`, add `test_depend` entries for `ament_cmake_pytest` and
   `python3-yaml`.
6. Make `test/test_camera_config.py` with the three checks in "Checks",
   "Configuration test without a camera".

Rules for the test:

1. The test must not need a camera, a driver, a network, or a built overlay.
2. Find the package files from the path of the test file.
3. Check each value in "Driver parameters" against `camera.yaml`.
4. Check that each `allowed_formats` entry is `Mono8` or `Mono12`.
5. Load the launch file by its path and call `generate_launch_description()`.
   Find the `DeclareLaunchArgument` actions for `use_ros_time` and
   `settings_file`. Check their defaults.
6. The default of `settings_file` is a `PathJoinSubstitution` with
   `FindPackageShare`. Check its parts without a package lookup.
7. Do not check the content of `camera_settings.xml`. The runner makes it
   after this task.

`colcon test` runs the test with `pytest` and the ROS 2 Jazzy Python
packages, for example `launch`, `launch_ros`, and `yaml`.

Write `{O}/implement-notes.md` with these parts:

1. Each file, and what changed in it.
2. Each v2 item that you could not follow, and the reason.
3. The open questions for the reviewer.
