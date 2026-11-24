# Implement notes for step 1

These notes cover the step 1 files in `src/venimapping_bringup/`. The source is v2 section 10, "Bring-up", and section 13, "Step 1. Bring-up parameters and files".

## Files and changes

### `config/camera.yaml`

1. The file header did not change.
2. The file has the new keys from "Driver parameters": `buffer_count: 7`, `use_ros_time: true`, `use_sim_time: false`, and `image_raw.enable_pub_plugins: ["image_transport/raw"]`.
3. The keys `camera_id: "0GPF3"` and `autostream: 0` did not change.
4. The file sets no `camera_info_url` and no `settings_file`, as v2 says.

### `config/acquisition_profile.yaml`

1. This is a new file with the content from "Acquisition profile file".
2. The file has the project header: the file name, the purpose, and the copyright line.
3. `trigger_mode` keeps the quotes from v2. Without them, a YAML 1.1 parser such as PyYAML reads `Off` as the boolean `false`.

### `launch/camera.launch.py`

1. The file header did not change.
2. The arguments `camera_namespace` and `params_file` did not change.
3. The new argument `use_ros_time` has the default `"true"` and the v2 description.
4. The new argument `settings_file` has the default `PathJoinSubstitution([FindPackageShare("venimapping_bringup"), "config", "camera_settings.xml"])` and the v2 description.
5. The `Node` `parameters` list has `LaunchConfiguration("params_file")` first. A dict with `use_ros_time` and `settings_file` follows it, so the two launch arguments win over the file.
6. The imports did not change. The file already imported each name that the new code uses.

### `CMakeLists.txt`

1. The file header and the `install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})` line did not change.
2. A new `if(BUILD_TESTING)` block calls `find_package(ament_cmake_pytest REQUIRED)` and `ament_add_pytest_test(test_camera_config test/test_camera_config.py)`.
3. The test name is `test_camera_config`. `ament_add_pytest_test` writes the result to `test_results/venimapping_bringup/test_camera_config.xunit.xml`.

### `package.xml`

1. The file has two new lines: `<test_depend>ament_cmake_pytest</test_depend>` and `<test_depend>python3-yaml</test_depend>`.

### `test/test_camera_config.py`

1. This is a new file with the project header.
2. The test finds the package folder from `Path(__file__).resolve().parents[1]`. It needs no camera, no driver, no network, and no built overlay.
3. `test_camera_yaml_has_driver_parameters` loads `config/camera.yaml`. It compares the `ros__parameters` dict of `/**/vimbax_camera` with the v2 values. It also checks the YAML types, because Python accepts `True == 1` in a dict compare. It checks that `camera_info_url` and `settings_file` are not in the file.
4. `test_profile_allowed_formats_are_mono8_or_mono12` loads `config/acquisition_profile.yaml`. It checks that `allowed_formats` is a list that is not empty. It checks that each entry is `Mono8` or `Mono12`.
5. `test_launch_arguments_have_defaults` loads `launch/camera.launch.py` by its path with `importlib.util.spec_from_file_location`. It calls `generate_launch_description()` and finds each `DeclareLaunchArgument` in `entities`.
6. The launch test checks that `camera_namespace`, `params_file`, `use_ros_time`, and `settings_file` exist. It checks that the `use_ros_time` default is one `TextSubstitution` with the text `true`.
7. For the `settings_file` default, the test reads the `PathJoinSubstitution.substitutions` property. It checks three parts: a `FindPackageShare` with the `package` text `venimapping_bringup`, then `config`, then `camera_settings.xml`. No part calls `perform`, so no package lookup occurs.
8. `FindPackageShare` is a subclass of `PathJoinSubstitution` in Jazzy (`launch_ros/substitutions/find_package.py:33`). The test therefore also checks that the outer default is not a `FindPackageShare`.
9. The test does not read `camera_settings.xml`.

## V2 items that I did not follow

None. Each value, key, name, and default comes from v2 section 10 with no change.

## Open questions for the reviewer

1. I did not run the test, because the session refused the `pytest` shell command. The runner build and test stages are the first run of the test.
2. The test imports `launch` and `launch_ros`. `package.xml` lists them only as `exec_depend`, because v2 asks only for the two `test_depend` entries. REP 140 does not promise `exec_depend` packages at test time. Should `package.xml` also get `test_depend` entries for `launch` and `launch_ros`?
3. The `camera.yaml` check compares the full parameter dict. So a new driver key in a later step also needs a change to `EXPECTED_DRIVER_PARAMETERS`. Is this strict compare correct, or should the test check only the v2 keys?
4. The test does not check the order of the `Node` `parameters` list. V2 puts that check on the rig, which reads both values back. Should the test without a camera also check that the override dict comes after `params_file`?
5. The profile test checks only `allowed_formats`, as v2 "Checks" asks. The runner compares the other six profile values with v2 in exit check 9. Should the test also check them?
