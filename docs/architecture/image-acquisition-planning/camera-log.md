# Camera checks

## c1 (claude, 2026-11-23T00:56:55-05:00)

Question: With autostream 0, answer T1 to T5, T7, and T8 in coordinator/facts.md. (1) Which PixelFormat values does the camera offer (features/enum_info_get), and which are on the driver gate list (driver vimbax_camera.cpp:1621-1651)? (2) What are Width, Height, WidthMax, HeightMax, and PayloadSize at a gate-listed format? (3) What frame rate arrives on /vimbax_camera/image_raw, measured with ros2 topic hz for 30 s or less? (4) Does the local device module list DeviceTimestampFrequency? Record two header stamps and the host clock at the same moments. (5) How long from the stream_start call to the first image_raw header? (6) While the stream is active, what does features/access_mode_get report for PixelFormat, Width, AcquisitionFrameRate, ExposureTime, and TriggerMode? (7) Does AcquisitionFrameRateEnable exist? Read it only. Do not write it. Rules: Write only PixelFormat, and only while stopped. Call stream_start only if the current PixelFormat is on the gate list, because a gate failure leaves the driver at kStarting and the runner cannot stop it. If the current format is not on the gate list, set Mono8 first. If Mono12 is offered, repeat (2), (3), and (5) at Mono12 for 10 s and record the encoding field. Do not call the status service while a stream runs. Collect driver log lines that contain 'frames missing' or 'Frame with status'.

Result file: `docs/architecture/image-acquisition-planning/claude/camera/c1.md`

Runner cleanup:

- Stream stopped and verified: True
- Features restored and verified: True
- Driver processes left: []

## c2 (claude, 2026-11-23T01:03:47-05:00)

Question: Answer T6 in coordinator/facts.md. Does the camera offer TriggerSelector FrameStart, TriggerSource Software, and the TriggerSoftware command? With FrameStart, TriggerMode On, and TriggerSource Software, does one features/command_run TriggerSoftware give exactly one image_raw frame after a quiet interval of 2 s? What is the time from the command_run call to the frame header, over five commands? Rules: Keep the current PixelFormat. Call stream_start only if it is on the driver gate list. Before any write, set TriggerSelector to FrameStart and read TriggerMode and TriggerSource. Do not call the status service between a TriggerSelector write and a TriggerMode or TriggerSource write, because status moves TriggerSelector. After the test, run stream_stop, set TriggerSelector to FrameStart, and write back the TriggerMode and TriggerSource values that you read. The runner then restores TriggerSelector. If the camera lacks FrameStart, Software, or TriggerSoftware, report that and do not stream.

Result file: `docs/architecture/image-acquisition-planning/claude/camera/c2.md`

Runner cleanup:

- Stream stopped and verified: True
- Features restored and verified: True
- Driver processes left: []

## c3 (codex, 2026-11-23T01:43:39-05:00)

Question: Answer R4 and T8 in coordinator/facts.md for register entry d18. With full-sensor Mono8 in free run and autostream 0: (1) While stopped, after features/bool_set AcquisitionFrameRateEnable true, what do features/access_mode_get and features/float_info_get report for AcquisitionFrameRate? (2) Does features/float_set AcquisitionFrameRate 30.0 succeed, and what does features/float_get read back? (3) With that setting, what rate does 'timeout 20 ros2 topic hz /vimbax_camera/image_raw' report after stream_start? Report the last rate, the window size, the interval minimum and maximum, and whether the rate is within 29 to 31 Hz. Rules: First call stream_stop. Then read PixelFormat with features/enum_get, Width and Height with features/int_get, AcquisitionFrameRateEnable with features/bool_get, and AcquisitionFrameRate with features/float_get. If PixelFormat is not Mono8 or the size is not 1296 x 1032, report the values and do not write or stream. Write only AcquisitionFrameRateEnable and AcquisitionFrameRate, and only while stopped. Do not call the status service. If AcquisitionFrameRate stays read only or 30.0 is outside its range, record that, skip the stream, and restore. Start ros2 topic hz before stream_start. Call stream_stop before any restore. To restore, while stopped and with the enable still true, write AcquisitionFrameRate back to the value that you read first. Then write AcquisitionFrameRateEnable back to the value that you read first. Read both back. If a write fails, record the error code and continue the restore.

Result file: `docs/architecture/image-acquisition-planning/codex/camera/c3.md`

Runner cleanup:

- Stream stopped and verified: True
- Features restored and verified: True
- Driver processes left: []

