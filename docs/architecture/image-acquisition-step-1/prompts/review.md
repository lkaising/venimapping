## Task: review the step 1 changes

Claude wrote the step 1 files, and the runner made
`src/venimapping_bringup/config/camera_settings.xml` on the camera. You are
the second tool. Find the defects before the runner does the rig check.

Run `git -C {worktree} diff {base}..HEAD -- src/venimapping_bringup` to see
the changes. Read section 10 and section 13 step 1 of the v2 design. Also
read `{worktree}/{O}/implement-notes.md` and the settings logs in
`{worktree}/{O}/settings/`.

Check these items:

1. Each file has the values, keys, names, and defaults in v2 section 10.
2. The launch file passes `use_ros_time` and `settings_file` after
   `params_file`, so that they win over the file.
3. The test does each check in "Configuration test without a camera". It
   fails on the files at the run base commit.
4. The test runs under `colcon test` without a camera, a driver, or a
   network.
5. `CMakeLists.txt` and `package.xml` have the changes in "Package changes".
6. `camera_settings.xml` holds the seven profile values.
7. `camera_settings.xml` holds no feature that changes IP settings,
   firmware, or user sets. List each feature in the file that the driver
   writes on each open and that is outside the profile, if it can change the
   camera in a way that step 1 does not intend.
8. The settings log shows the steps in "Camera settings file", in order,
   with no `status` call between steps 2 and 6.

Do not change a file. Do not report the style of comments or prose. Check
each citation that a finding uses.

Write `{O}/review.md` with a table. Use the columns Id, Severity, File,
Finding, Evidence, and Suggested fix. Use the ids r1, r2, and so on. Use these
severity values:

1. Blocking means that a check of step 1 fails or v2 is not met.
2. Major means a real gap or a wrong value.
3. Minor means a small error that changes the meaning.

Also write `{O}/review.json` with the same findings in this form:

```json
{"findings": [{"id": "r1", "severity": "major",
  "file": "src/venimapping_bringup/launch/camera.launch.py",
  "summary": "one sentence"}]}
```

If you find no defect, write `{"findings": []}` and say so in `review.md`.
