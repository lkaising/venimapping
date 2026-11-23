## Task: camera check {check}

The runner started the camera driver in the namespace above. It also saved the
original value of each feature in the list above. After you finish, the runner
stops the stream, restores the listed features, verifies them, and stops the
driver.

Follow these rules:

1. Answer only the question above.
2. Change only the listed features. Use the driver services under the
   namespace, for example `features/float_set`.
3. Do not save or load settings. Do not call `settings_save` or
   `settings_load`. Do not change IP settings or firmware.
4. Keep each stream at or below the longest stream time above. Stop each
   stream that you start with the `stream_stop` service.
5. Do not start a driver or a launch file.
6. `ros2 topic hz` does not stop by itself. Run it with a time limit of 60
   seconds or less.
7. If the check cannot answer the question, say so. That is a valid result.

You can use `ros2 service call`, `ros2 topic hz`, `ros2 topic echo --once`,
`ros2 topic list`, `ros2 node list`, `ros2 interface show`, and
`ros2 run venimapping_camera camera_gateway_probe`.

Write `{P}/{tool}/camera/{check}.md` with these parts:

1. The question.
2. The commands that you ran, in order, with the key output.
3. The result, with numbers.
4. What the result changes in the plan, by design choice id or register id.
5. The limits of the result, for example one sample or one camera setting.
