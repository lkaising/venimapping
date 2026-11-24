# Step 1 review

| Id | Severity | File | Finding | Evidence | Suggested fix |
|---|---|---|---|---|---|
| r1 | blocking | `src/venimapping_bringup/config/camera_settings.xml` | The settings file can overwrite the stream's multicast IP address and disable multicast on each open. | The stream sets `MulticastIPAddress` to 4026470193 and `MulticastEnable` to 0. The rig's feature probe marks both writable. The runner's denied patterns omit both names. See `camera_settings.xml:5213` to 5214, `featinfo_full.tsv:377` to 378, and `runner/settings.json:44` to 56. | Have the runner strip both multicast features from the package copy. Make the scan reject a package copy that still contains either feature. |
| r2 | major | `src/venimapping_bringup/config/camera_settings.xml` | The settings file can reset image formation, exposure control, and acquisition modes outside the seven-value profile. | The file turns off auto gain, sets gain to 0 dB, enables preset defect-pixel correction, and writes 1 to every saved lens shading coefficient. See `camera_settings.xml:99` to 109, 996 to 1002, and 1144 to 4255, and `featinfo_full.tsv:191` to 208 and 315 to 317. | Have the runner remove the extra image and acquisition features listed under r2. Keep any feature that the seven profile values require. Record the dependency and verify it during the rig check. |
| r3 | major | `src/venimapping_bringup/config/camera_settings.xml` | The settings file can disable six triggers outside `FrameStart` and change physical I/O and event settings. | The file sets all seven trigger modes to `Off`, sets `Line2` to `Output`, and enables only the `Test` event notification. See `camera_settings.xml:263` to 389, 4256 to 4280, and 5081 to 5117, and `featinfo_full.tsv:39` to 40, 179 to 184, and 211 to 219. | Keep the `FrameStart` selector and its `TriggerMode` entry. Have the runner remove the other trigger groups and the extra signal features listed under r3. |
| r4 | major | `src/venimapping_bringup/config/camera_settings.xml` | The settings file can replace GigE control and stream recovery settings with values from the save rig. | The file sets the heartbeat timeout to 730 ms, selects the socket stream driver, and limits missing-packet requests to one. See `camera_settings.xml:16` to 24, 5201 to 5212, and 5232, and `featinfo_full.tsv:364` to 367, 372, and 381 to 392. | Have the runner omit the control and stream features listed under r4. Let the driver and SDK set transport behavior for the host that opens the camera. |
| r5 | minor | `src/venimapping_bringup/config/camera_settings.xml` | The settings file can change the file access target and operation selector outside the acquisition profile. | `FileSelector` includes `Firmware` and `UserSet1` through `UserSet4` and ends at `UserData`. The groups include `FileOperationSelector` values `Write` and `Delete`. `FileOperationExecute` and `FileAccessBuffer` are `IgnoredFeature` entries. See `camera_settings.xml:397` to 419, 535 to 626, 995, and 5125 to 5126, and `featinfo_full.tsv:299` to 310. | Have the runner remove the `FileSelector` groups and the final `FileSelector` value. |

## Features outside the profile

The driver calls `SettingsLoad` on open and reconnect. It includes the local device, remote device, and stream modules. The SDK tries to set the values in the XML. Write access can depend on the selector or mode at load time. See `vimbax_camera_node.cpp:370` to 400 and 556 to 568, `vimbax_camera.cpp:1308` to 1328 and 1358 to 1367, and `cAPIManual.html:1470` to 1479.

In this inventory, `camera_settings.xml` means the package copy. The rig's query-only probe is `docs/architecture/image-acquisition-step-1/evidence/featinfo_full.tsv`. The inventory lists writable entries and marks entries whose access needs a check in a different mode.

### Image formation and acquisition in r2

The file sets `AcquisitionFrameRateMode`, `AcquisitionMode`, `ExposureAuto`, `ExposureAutoMin`, `ExposureAutoMax`, and `ExposureMode`. `ExposureTime` requires `ExposureMode=Timed` and `ExposureAuto=Off`. See `camera_settings.xml:29` to 30 and 391 to 395 and `featinfo_full.tsv:165` to 187.

The auto control entries are `AutoModeRegionSelector`, `AutoModeRegionWidth`, `AutoModeRegionHeight`, `AutoModeRegionOffsetX`, `AutoModeRegionOffsetY`, `IntensityAutoPrecedence`, and `IntensityControllerSelector`. The file also sets `IntensityControllerRate`, `IntensityControllerRegion`, `IntensityControllerTolerance`, `IntensityControllerAlgorithm`, and `IntensityControllerTarget`. The gain entries are `GainAuto`, `GainAutoMin`, `GainAutoMax`, `GainSelector`, and `Gain`. See `camera_settings.xml:49` to 55, 996 to 1002, and 1131 to 1139, and `featinfo_full.tsv:154` to 169 and 191 to 193.

The image geometry entries are `BinningSelector`, `BinningHorizontalMode`, `BinningHorizontal`, `BinningVertical`, `BinningVerticalMode`, `MultipleRegionArrangement`, `MultipleRegionEnable`, `OffsetX`, and `OffsetY`. They also include `SubRegionSelector`, `SubRegionWidth`, `SubRegionHeight`, `SubRegionOffsetX`, `SubRegionOffsetY`, `ReverseX`, `ReverseY`, `SensorBitDepth`, and `SensorShutterMode`. The test pattern entries are `TestPatternGeneratorSelector` and `TestPattern`. See `camera_settings.xml:56` to 62, 4282 to 4285, 4298 to 4302, and 5006 to 5058, and `featinfo_full.tsv:127` to 153.

The image processing entries are `BlackLevelSelector`, `BlackLevel`, `Gamma`, `ContrastEnable`, `ContrastShape`, `ContrastBrightLimit`, and `ContrastDarkLimit`. They also include `AdaptiveNoiseSuppressionFactor`, `ConvolutionMode`, `CustomConvolutionValueSelector`, `CustomConvolutionValue`, `Sharpness`, `CorrectionSelector`, `CorrectionMode`, and `CorrectionSet`. The shading and LUT entries are `LensShadingCenterOffsetX`, `LensShadingCenterOffsetY`, `LensShadingEnable`, `LensShadingIndex`, `LensShadingValue`, `LUTSelector`, and `LUTIndex`. See `camera_settings.xml:48`, 63 to 66, 98 to 109, 159 to 234, 1140 to 4255, and 5004 to 5054. See `featinfo_full.tsv:194` to 208, 315 to 325, and 341 to 344.

The sequencer entries are `SequencerConfigurationMode`, `SequencerMode`, `SequencerFeatureSelector`, `SequencerSetSelector`, and `SequencerPathSelector`. The payload entries are `ChunkModeActive`, `ChunkSelector`, and `ChunkEnable`. See `camera_settings.xml:67` to 95 and 4304 to 5002 and `featinfo_full.tsv:263` to 276 and 326 to 329.

Verify write access for `SubRegionMode` with multiple regions enabled. Verify `SequencerFeatureEnable`, `SequencerSetStart`, `SequencerSetNext`, `SequencerTriggerSource`, and `SequencerTriggerActivation` in sequencer configuration mode. The probe records these entries as read-only in its captured state. See `camera_settings.xml:4304` to 5002 and 5006 to 5054 and `featinfo_full.tsv:148`, 266, 271, and 274 to 276.

### Triggers, I/O, and events in r3

The extra `TriggerMode` entries apply to `AcquisitionStart`, `AcquisitionEnd`, `AcquisitionActive`, `ExposureStart`, `ExposureEnd`, and `ExposureActive`. Their groups write `TriggerSelector` while the SDK restores those entries. The file also sets `TriggerSource`, `TriggerActivation`, `TriggerDelay`, `ClockTriggerFrequency`, `ClockTriggerTimestamp`, and `ExposureActiveMode`. See `camera_settings.xml:96` to 97, 390, and 5081 to 5117, and `featinfo_full.tsv:179` to 190.

The line and serial entries are `LineSelector`, `LineMode`, `LineDebounceMode`, `LineDebounceDuration`, and `SerialHubEnable`. The `Line2` group also holds `LineInverter` and `LineSource`. Verify access to these two entries with `Line2` selected. See `camera_settings.xml:4256` to 4280 and 5003 and `featinfo_full.tsv:211` to 219.

The action and event entries are `ActionSelector`, `ActionGroupMask`, `ActionGroupKey`, `EventSelector`, and `EventNotification`. The counter entries are `CounterSelector`, `CounterTriggerActivation`, `CounterTriggerSource`, `CounterValue`, `CounterDuration`, `CounterEventSource`, `CounterEventActivation`, `CounterResetSource`, and `CounterResetActivation`. The timer entries are `TimerSelector`, `TimerDuration`, `TimerDelay`, `TimerTriggerActivation`, and `TimerTriggerSource`. The file also sets `SoftwareSignalSelector`. See `camera_settings.xml:39` to 47, 110 to 158, 263 to 389, 5005, and 5059 to 5073, and `featinfo_full.tsv:36` to 40, 230 to 248, and 339 to 340.

The device controls are `DeviceIndicatorLuminance`, `DeviceIndicatorMode`, and `DevicePowerSavingMode`. The file also sets the diagnostic selectors `DeviceTemperatureSelector` and `AcquisitionStatusSelector`. See `camera_settings.xml:31` to 37, 236 to 244, and 253 to 259, and `featinfo_full.tsv:21` to 23, 33, and 177 to 178.

### Transport in r4

The local device entries are `GVCPCmdRetries`, `GVCPCmdTimeout`, `GevHeartbeatInterval`, `GevHeartbeatTimeout`, and `StreamSelector`. The camera entries are `DeviceLinkThroughputLimit`, `DeviceLinkThroughputLimitMode`, `GevPAUSEFrameReception`, `GevSupportedOptionSelector`, `PtpEnable`, `PtpOperationMode`, `TransferSelector`, and `TransferControlMode`. See `camera_settings.xml:16` to 24, 240 to 241, 1003 to 1128, 4289 to 4297, and 5075 to 5080, and `featinfo_full.tsv:16` to 17, 249 to 258, 282 to 286, 311 to 313, 351, and 364 to 367.

The stream entries are `GVSPBurstSize`, `GVSPDriver`, `GVSPHostReceiveBufferSize`, `GVSPMaxLookBack`, `GVSPMaxRequests`, `GVSPMaxWaitSize`, `GVSPMissingSize`, `GVSPProtocol`, `GVSPTiltingSize`, `GVSPTimeout`, and `StreamBufferHandlingMode`. The stream also sets `FramePacketStatisticsCounterSelector`, `FrameRateSelector`, and `FrameStatisticsCounterSelector`. See `camera_settings.xml:5150` to 5212 and 5232 and `featinfo_full.tsv:372`, 381 to 389, and 392 to 398.

## Checks verified

`camera.yaml` and `acquisition_profile.yaml` match v2 section 10. The launch file keeps the existing namespace and parameter-file defaults. It declares the two new defaults and puts both overrides after `params_file`. See `camera.launch.py:19` to 62.

CMake registers the pytest suite under `BUILD_TESTING`. The manifest declares both required test dependencies. The runner recorded all three configuration tests passing under `colcon test`. See `CMakeLists.txt:14` to 19, `package.xml:14` to 20, and `output/colcon/build-1-a1/commands.log:56` to 95.

The suite checks the driver YAML, allowed format list, and both new launch defaults. An in-memory replay rejected the run base files in all three tests. The replay used a null log handler to keep launch from creating a log file. See `test_camera_config.py:42` to 118 and base commit `9dee1f0e37207f56b741006e3548f68a221fe689`.

The package XML holds all seven profile values and sets `TriggerSelector` to `FrameStart`. The matching selector group holds `TriggerMode=Off`. See `camera_settings.xml:27` to 28, 395, 1129, 4287, 5096 to 5097, and 5117 to 5118.

The runner removed the camera IP configuration, firmware settings, user-set controls, and both writable packet-size entries. The probe marks the remaining `DeviceStreamChannelPacketSize` entry read-only. See `output/settings/settings-a1/commands.log:227`, `camera_settings.xml:250`, and `featinfo_full.tsv:18` and 297.

The remaining firmware and user-set file entries select a file or operation. A file operation requires the ignored `FileOperationExecute` command. See `camera_settings.xml:397` to 419, 535 to 626, and 5125 to 5126, and `featinfo_full.tsv:299` to 310.

The settings log records a stopped stream and the required writes in order. Both `status` calls precede the profile writes. The runner saved to an absolute `.xml` path, stripped 31 names, and copied the file to the package. See `output/settings/settings-a1/commands.log:79` to 159 and 161 to 229.
