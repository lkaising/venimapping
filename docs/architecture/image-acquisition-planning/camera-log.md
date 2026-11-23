# Camera checks

## c1 (claude, 2026-11-23T00:56:55-05:00)

Question: With autostream 0, answer T1 to T5, T7, and T8 in coordinator/facts.md. (1) Which PixelFormat values does the camera offer (features/enum_info_get), and which are on the driver gate list (driver vimbax_camera.cpp:1621-1651)? (2) What are Width, Height, WidthMax, HeightMax, and PayloadSize at a gate-listed format? (3) What frame rate arrives on /vimbax_camera/image_raw, measured with ros2 topic hz for 30 s or less? (4) Does the local device module list DeviceTimestampFrequency? Record two header stamps and the host clock at the same moments. (5) How long from the stream_start call to the first image_raw header? (6) While the stream is active, what does features/access_mode_get report for PixelFormat, Width, AcquisitionFrameRate, ExposureTime, and TriggerMode? (7) Does AcquisitionFrameRateEnable exist? Read it only. Do not write it. Rules: Write only PixelFormat, and only while stopped. Call stream_start only if the current PixelFormat is on the gate list, because a gate failure leaves the driver at kStarting and the runner cannot stop it. If the current format is not on the gate list, set Mono8 first. If Mono12 is offered, repeat (2), (3), and (5) at Mono12 for 10 s and record the encoding field. Do not call the status service while a stream runs. Collect driver log lines that contain 'frames missing' or 'Frame with status'.

Result file: `docs/architecture/image-acquisition-planning/claude/camera/c1.md`

Runner cleanup:

- Stream stopped and verified: True
- Features restored and verified: True
- Driver processes left: []

