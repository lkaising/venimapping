# Step 1 review fixes

All five findings are about `src/venimapping_bringup/config/camera_settings.xml`. Only the runner makes that file, on the camera. This task cannot write it. No step 1 file changed.

## Why no other step 1 file can fix these findings

1. The driver gives the `settings_file` path directly to `VmbSettingsLoad` (`driver:vimbax_camera/src/vimbax_camera.cpp:1308-1328`).
2. The driver uses one fixed persist setting: `VmbFeaturePersistNoLUT`, module flags `RemoteDevice | LocalDevice | Streams`, and 10 iterations (`driver:vimbax_camera/src/vimbax_camera.cpp:1358-1367`).
3. No parameter in `camera.yaml` and no argument in `camera.launch.py` can filter the features that the SDK writes from the file. The content of the XML file alone sets the scope of the load.
4. The launch file only sets the path. Its default is `FindPackageShare("venimapping_bringup")/config/camera_settings.xml`, as v2 section 10 requires (`camera.launch.py`, v2 lines 1331-1337).
5. A content check of the XML file in `test_camera_config.py` is not in v2. The v2 test has three checks: `camera.yaml` values, `allowed_formats`, and the two launch defaults (v2 lines 1466-1470). Such a check would also fail on the current XML file and stop the build before the runner can correct the file.

## Problem with v2

The v2 save procedure has no step that removes features from the saved file (v2 lines 1403-1413). It saves all readable features of three modules (v2 line 1367). V2 accepts a change outside the profile with a file review only (v2 line 1401). The runner already removes 31 names, which is more than v2 specifies. The five findings show that this removal list is not complete. The removal list and a scan that rejects a forbidden name must go into v2 section 10. This task cannot edit v2.

## r1

- Status: Not fixed
- Severity: blocking
- What changed: Nothing. The fix is in `camera_settings.xml`, which only the runner makes.
- Evidence: The review cites `MulticastIPAddress` 4026470193 and `MulticastEnable` 0 at `camera_settings.xml:5213-5214`. The rig probe marks both writable (`featinfo_full.tsv:377-378`). The stream module is in the load flags (`driver:vimbax_camera/src/vimbax_camera.cpp:1364`). The SDK therefore writes both features on each open and each reopen (v2 line 1364).
- Action for Logan: Add `MulticastIPAddress` and `MulticastEnable` to the runner removal list. Make the runner scan reject a package copy that holds either name.

## r2

- Status: Not fixed
- Severity: major
- What changed: Nothing. The fix is in `camera_settings.xml`, which only the runner makes.
- Evidence: The review cites `GainAuto` off, `Gain` 0 dB, preset defect-pixel correction, and lens shading coefficients at `camera_settings.xml:99-109`, `:996-1002`, and `:1144-4255`. The controller readback checks only the seven profile values and the selector write (v2 line 1399). Other features in the file get no readback.
- Action for Logan: Remove the image formation, exposure control, and acquisition mode features that the review lists under r2. Keep each feature that one of the seven profile values needs. `ExposureTime` needs `ExposureMode=Timed` and `ExposureAuto=Off` (review, `featinfo_full.tsv:165-187`). Record each kept dependency and verify it in the rig check.

## r3

- Status: Not fixed
- Severity: major
- What changed: Nothing. The fix is in `camera_settings.xml`, which only the runner makes.
- Evidence: The file sets all seven `TriggerMode` entries to `Off`, sets `Line2` to `Output`, and enables the `Test` event (`camera_settings.xml:263-389`, `:4256-4280`, `:5081-5117`). V2 needs only `TriggerSelector` `FrameStart` with `TriggerMode` `Off` (v2 line 1406).
- Action for Logan: Keep the `FrameStart` selector group and its `TriggerMode` entry. Remove the other six trigger groups and the line, counter, timer, action, event, and device features that the review lists under r3.

## r4

- Status: Not fixed
- Severity: major
- What changed: Nothing. The fix is in `camera_settings.xml`, which only the runner makes.
- Evidence: The file sets `GevHeartbeatTimeout` to 730 ms, selects the socket `GVSPDriver`, and sets `GVSPMaxRequests` to 1 (`camera_settings.xml:16-24`, `:5201-5212`, `:5232`). The local device and stream modules are in the load flags (`driver:vimbax_camera/src/vimbax_camera.cpp:1363-1364`). The SDK therefore applies the transport values of the save host to each host that opens the camera.
- Action for Logan: Remove the local device and stream transport features that the review lists under r4. Let the driver and the SDK set transport values on the host that opens the camera.

## r5

- Status: Not fixed
- Severity: minor
- What changed: Nothing. The fix is in `camera_settings.xml`, which only the runner makes.
- Evidence: `FileSelector` groups include `Firmware` and `UserSet1` to `UserSet4`, with `FileOperationSelector` values `Write` and `Delete` (`camera_settings.xml:397-419`, `:535-626`, `:5125-5126`). `FileOperationExecute` is an `IgnoredFeature` entry, so the load starts no file operation. The load still leaves the file selectors in a different state.
- Action for Logan: Remove the `FileSelector` groups and the final `FileSelector` value from the package copy.
