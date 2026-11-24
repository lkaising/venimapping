# Step 1 report

The runner writes this file from the results of the checks. Each check has a fixed pass rule in `docs/architecture/image-acquisition-step-1/runner/`.

- Written: 2026-11-24T08:55:50-05:00
- Run base commit: `62c32048c48`
- Rig check stage: rig-1, logs in `docs/architecture/image-acquisition-step-1/output/rig/rig-1-a1`
- Build and test stage: build-2, logs in `docs/architecture/image-acquisition-step-1/output/colcon/build-2-a1`
- Settings file stage: settings

## Exit check

| Item | Check | Result | Key output |
|---|---|---|---|
| 1 | `colcon build --packages-select venimapping_bringup` succeeds | PASS | colcon build --packages-select venimapping_bringup ended with exit 0 |
| 2 | `colcon test --packages-select venimapping_bringup` passes | PASS | colcon test exit 0, test-result exit 0, Summary: 8 tests, 0 errors, 0 failures, 0 skipped, test_camera_config results found: True |
| 3 | Bring-up part A, steps 1 to 16 | PASS | See part A below |
| 4 | `use_ros_time` prints `True` | PASS | use_ros_time is True |
| 5 | `settings_file` is the installed path, and the file exists | PASS | settings_file is /home/labuser/workspace/projects/venimapping-image-acq-step-1/install/venimapping_bringup/share/venimapping_bringup/config/camera_settings.xml, the installed path; the file exists |
| 6 | `image_raw.enable_pub_plugins` is only `image_transport/raw` | PASS | image_raw.enable_pub_plugins is ['image_transport/raw'] |
| 7 | `ros2 topic info` prints `Publisher count: 1` | PASS | Publisher count: 1 |
| 8 | No topic starts with `/vimbax_camera/image_raw/` | PASS | topics under /vimbax_camera/image_raw/: none |
| 9 | CLI reads of the seven profile values match the profile file | PASS | camera {'PixelFormat': 'Mono8', 'Width': 1296, 'Height': 1032, 'TriggerMode': 'Off', 'AcquisitionFrameRateEnable': True, 'AcquisitionFrameRate': 30.000001907348633, 'ExposureTime': 4999.455}; differs: none |
| 9b | CLI reads of the kept features outside the profile match the settings file (a runner check, not in v2) | PASS | kept features outside the profile: {'AcquisitionFrameRateMode': 'Basic', 'ExposureAuto': 'Off', 'ExposureMode': 'Timed', 'OffsetX': 0, 'OffsetY': 0}; differs: none |
| 10 | `camera_gateway_probe` passes | PASS | exit 0; [INFO] [1795528477.488532252] [camera_gateway_probe]: probe complete: all checks passed (1 skipped) |

## Part A, the controlled reopen

| Step | Action | Result | Key output |
|---|---|---|---|
| 1 | Launch with `settings_file:=/nonexistent.xml`, log to `driver_control.log` | PASS | launched with settings_file:=/nonexistent.xml |
| 2 | Init wait on `driver_control.log` | PASS | init wait on driver_control.log ended with status 0 after 15.08 s |
| 3 | `grep -F 'Loading settings from file' driver_control.log` | PASS | [vimbax_camera_node-1] [ERROR] [1795528427.000704767] [vimbax_camera.vimbax_camera]: Loading settings from file /nonexistent.xml failed with error -3 (VmbErrorNotFound) |
| 4 | Step 3 printed a line | PASS | the control log has the failed-load line |
| 5 | Stop the driver | PASS | stopped the control driver |
| 6 | Launch with the default arguments, log to `driver_a.log` | PASS | launched with the default arguments |
| 7 | Init wait on `driver_a.log` | PASS | init wait on driver_a.log ended with status 0 after 13.57 s |
| 8 | Write `ExposureTime` 10000.0 | PASS | wrote ExposureTime 10000.0 |
| 9 | Write `AcquisitionFrameRate` 20.0 | PASS | wrote AcquisitionFrameRate 20.0 |
| 10 | Read back both values | PASS | read back {'ExposureTime': 10004.707, 'AcquisitionFrameRate': 20.0} |
| 11 | Each value is within 0.001 of the written value | PASS | each value taken; v2 step 11 asks for 0.001, and the camera rounded: {'ExposureTime': 'rounded: wrote 10000.0, the camera holds 10004.707, increment 13.172'} |
| 12 | Stop the driver | PASS | stopped driver_a |
| 13 | Launch again with the default arguments, log to `driver_b.log` | PASS | launched again with the default arguments |
| 14 | Init wait on `driver_b.log` | PASS | init wait on driver_b.log ended with status 0 after 13.57 s |
| 15 | `grep -F 'Loading settings from file' driver_a.log driver_b.log` | PASS | grep exit 1, no line |
| 16 | Step 15 printed no line | PASS | neither driver_a.log nor driver_b.log has the failed-load line |

## Camera settings file

The runner made `src/venimapping_bringup/config/camera_settings.xml` in stage settings with the steps in v2 section 10. Logs: `docs/architecture/image-acquisition-step-1/output/settings/settings-a1`.

| Step | Result | Key output |
|---|---|---|
| S0 | PASS | init wait on driver_settings.log ended with status 0 after 14.58 s |
| S0 | PASS | the driver without settings_file is up and the stream is stopped |
| S1 | PASS | wrote PixelFormat Mono8, Width 1296, Height 1032 |
| S2 | PASS | wrote TriggerSelector FrameStart, then TriggerMode Off |
| S3 | PASS | wrote AcquisitionFrameRateEnable true |
| S4 | PASS | wrote AcquisitionFrameRate 30.0 |
| S5 | PASS | wrote ExposureTime 4999.455 |
| S6 | PASS | no status call between steps 2 and 7; the readback matches the profile: {'PixelFormat': 'Mono8', 'Width': 1296, 'Height': 1032, 'TriggerMode': 'Off', 'AcquisitionFrameRateEnable': True, 'AcquisitionFrameRate': 30.000001907348633, 'ExposureTime': 4999.455} |
| S7 | PASS | settings/save wrote /home/labuser/workspace/projects/venimapping-image-acq-step-1-run/attempts/settings/1/camera_settings.xml (339695 bytes) |
| S7b | PASS | kept 13 names in the package copy: ['AcquisitionFrameRate', 'AcquisitionFrameRateEnable', 'AcquisitionFrameRateMode', 'ExposureAuto', 'ExposureMode', 'ExposureTime', 'Height', 'OffsetX', 'OffsetY', 'PixelFormat', 'TriggerMode', 'TriggerSelector', 'Width']; removed 208 names; listed but not in the saved file: none; names outside the keep list: none; scan of the copy: 13 features; profile values mis |
| S8 | PASS | copied the file to src/venimapping_bringup/config/camera_settings.xml |

The saved file holds 297 features. Denied features: CorrectionSetDefault, DeviceFirmwareID, DeviceFirmwareIDSelector, DeviceFirmwareUploadType, DeviceFirmwareVersion, DeviceFirmwareVersionSelector, DeviceReset, DeviceUserID, GVSPPacketSize, GevCurrentDefaultGateway, GevCurrentIPAddress, GevCurrentIPConfigurationDHCP, GevCurrentIPConfigurationLLA, GevCurrentIPConfigurationPersistentIP, GevCurrentSubnetMask, GevDeviceGateway, GevDeviceIPAddress, GevDeviceMACAddress, GevDeviceSubnetMask, GevIPConfigurationStatus, GevMACAddress, GevPersistentDefaultGateway, GevPersistentIPAddress, GevPersistentSubnetMask, GevSCPSPacketSize, TLParamsLocked, TestPendingAck, UserSetDefault, UserSetLoad, UserSetSave, UserSetSelector.

| Feature | Expected | In the file | Match |
|---|---|---|---|
| PixelFormat | Mono8 | Mono8 | yes |
| Width | 1296 | 1296 | yes |
| Height | 1032 | 1032 | yes |
| TriggerMode | Off | Off, Off, Off, Off, Off, Off, Off | yes |
| AcquisitionFrameRateEnable | True | 1 | yes |
| AcquisitionFrameRate | 30.0 | 30 | yes |
| ExposureTime | 4999.455 | 4999.455 | yes |

Policy `keep`: the package copy holds only the names in `camera.xml_keep_features` and `camera.xml_keep_selectors` of `settings.json`. The saved file in the logs is unchanged. This differs from v2 section 10, which installs the saved file as it is. The package copy holds 13 names: `AcquisitionFrameRate`, `AcquisitionFrameRateEnable`, `AcquisitionFrameRateMode`, `ExposureAuto`, `ExposureMode`, `ExposureTime`, `Height`, `OffsetX`, `OffsetY`, `PixelFormat`, `TriggerMode`, `TriggerSelector`, `Width`. The runner removed 208 names; `results.json` of the settings stage lists them. Listed but not in the saved file: none.

The driver writes these kept features outside the profile on each open: `AcquisitionFrameRateMode`, `ExposureAuto`, `ExposureMode`, `OffsetX`, `OffsetY`. Exit check 9b reads each one back after the reopen.

## Working assumptions that the run tested

| Id | Assumption | Result | Evidence |
|---|---|---|---|
| P11 | The camera keeps service writes across a driver restart without a power cycle | Holds | the values survived the restart; written {"ExposureTime": 10004.707, "AcquisitionFrameRate": 20.0}, after the restart {"ExposureTime": 10004.707, "AcquisitionFrameRate": 20.0, "AcquisitionFrameRateEnable": true} |
| Init wait limit | The driver prints the init line within 60 s | Holds | 6 init waits, longest 15.08 s |
| Line order | `launch` and `tee` keep the line order of one stream | Holds | {"load_line": 12, "init_line": 19, "in_order": true} |
| Override order | A later `parameters` entry overrides an earlier one | Holds | Exit checks 4 and 5 read both values back |
| P2 | The settings file and the profile file describe the same values | Holds | Exit check 9 after the controlled reopen, and the file scan |
| Part A step 11 | The camera holds 10000.0 and 20.0 within 0.001 | Contradicted | {"ExposureTime": "rounded: wrote 10000.0, the camera holds 10004.707, increment 13.172"} |
| Host check | `net.core.rmem_max` and `net.core.rmem_default` are 8388608 or more | Below | {"net.core.rmem_max": "4194304", "net.core.rmem_default": "212992"} |

Init waits:

| Log | Status | Seconds |
|---|---|---|
| driver_settings.log | 0 | 14.58 |
| driver_control.log | 0 | 15.08 |
| driver_a.log | 0 | 13.57 |
| driver_b.log | 0 | 13.57 |
| p11_write.log | 0 | 14.58 |
| p11_read.log | 0 | 13.57 |

Rule for a result that contradicts v2: the runner records the result here and does not edit v2. If P11 is contradicted, the run continues with the v2 fallback in section 10, part A note 5. Part A still fails on a failed load, because the failed-load `grep` runs on each launch log and the camera defaults keep `AcquisitionFrameRateEnable` false. A slow init wait stops the run, because a new limit is a change to v2 that Logan decides. A float write that the camera rounds to its own increment passes part A step 11 when the readback is within one increment of the written value and differs from the profile value. v2 asks for 0.001, so each such rounding is listed in the row for part A step 11.

## Review

Codex reviewed the step 1 changes in stage review. Claude answered each finding in stage fix (status done). The review is in `docs/architecture/image-acquisition-step-1/output/review.md`, and the answers are in `docs/architecture/image-acquisition-step-1/output/fixes.md`.

| Id | Severity | File | Finding |
|---|---|---|---|
| r1 | blocking | src/venimapping_bringup/launch/camera.launch.py | A matching wildcard in `params_file` can override both `use_ros_time` and `settings_file`. |
| r2 | major | src/venimapping_bringup/launch/camera.launch.py | The launch file truncates an absolute `settings_file` path when the path contains a space followed by `#`. |

## Camera cleanup

After each camera stage, the runner stopped each driver, wrote back each baseline value that differed, read each value back, and checked that no driver process was left.

- settings attempt 1: outcome ok, logs `docs/architecture/image-acquisition-step-1/output/settings/settings-a1`
- rig-1 attempt 1: outcome ok, logs `docs/architecture/image-acquisition-step-1/output/rig/rig-1-a1`

## Differences from the v2 command text

1. The build uses `--symlink-install`, as the project README does.
2. The CLI steps use `ros2 service call` on the driver services, with a time limit for each call.
3. The runner stops the ROS daemon after each driver stop, so that no graph read sees an earlier driver. A graph read that does not pass at once is repeated for up to 15 s.
4. The topic list check runs twice, 1 s apart. A plugin topic in either list fails the check.
5. `camera_gateway_probe` runs with `enable_writes:=false` and `exercise_stream:=false`, its read-only defaults, set explicitly.
6. The settings file is made on a driver that `ros2 run` starts with a runner parameter file and no `settings_file`.
7. Part A step 11 passes a float readback within one camera increment of the written value, where v2 asks for 0.001. See the row for part A step 11 above.
8. The settings file policy is `keep`. With `keep`, the package copy holds only the profile features and the features they depend on. With `strip`, it has no denied feature. v2 installs the saved file as it is. See the camera settings file section.
