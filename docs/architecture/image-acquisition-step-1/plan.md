# Step 1 harness plan

This harness implements and verifies step 1 of the image acquisition design,
"Step 1. Bring-up parameters and files" in section 13 of
`docs/architecture/image-acquisition-design-v2.md`. It runs with no person
present. One command starts it, and the same command resumes it.

The planning harness in `docs/architecture/image-acquisition-planning/` is the
model. This harness copies and adapts its runner code. It does not import it.

## Commands

Run each command from the worktree root,
`/home/labuser/workspace/projects/venimapping-image-acq-step-1`.

1. Preflight: `python3 docs/architecture/image-acquisition-step-1/runner/preflight.py`
2. Run: `python3 docs/architecture/image-acquisition-step-1/runner/run.py`
3. Resume: the run command again.
4. Dry run: `python3 docs/architecture/image-acquisition-step-1/runner/dryrun/dryrun.py <empty folder>`

The run exits with status 0 when step 1 is complete and the remote has the
last commit. It exits with 2 when it stops for Logan, and with 3 when step 1
is complete but the last push failed.

## Stages

The pipeline is linear. Each stage starts after the stage before it is done.

| Stage | Tool | Work | Reason |
|---|---|---|---|
| implement | Claude | Writes the six text files of step 1 | The files need judgment, for example the launch test. Claude has two accounts, so a quota pause on one account does not stop the run. |
| build | runner | `colcon build` and `colcon test` for `venimapping_bringup` | Exit checks 1 and 2 have a fixed pass rule. Code runs them. |
| settings | runner, camera | Makes `camera_settings.xml` with the steps in v2 section 10 and scans it | The steps are a fixed sequence of service calls. Code does them in order, with no `status` call between steps 2 and 6. |
| review | Codex | Reviews the step 1 changes and the settings file against v2 | The second tool finds defects that the implementer misses. The review comes before the rig check, so that the rig check runs on the final files. |
| fix | Claude | Answers each review finding | Claude wrote the files, so Claude fixes them. The runner skips the stage if the review has no findings. |
| build | runner | Builds and tests again | The fix can break the test. |
| rig | runner, camera | Part A steps 1 to 16, exit checks 4 to 10, the P11 check, and the host check | Each check has a fixed pass rule. Code does each launch, init wait, `grep`, and readback. |
| report | runner | Writes `output/report.md` | The report comes from the check results, so it cannot claim a result that no check gave. |

The runner adds stages only after a failed check:

1. A failed build or test adds a repair stage (Claude) and a new build stage.
   The limit is 2 repair rounds.
2. A failed rig check that a file change can fix adds a repair stage, a build
   stage, and a new rig stage. The limit is 1 repair round.
3. A repair stage that changes no file stops the run. Its notes say what Logan
   must do.

A rig failure that a file change can fix is a failure of part A step 4, part
A step 16, exit checks 4 to 8, or exit check 9 when the profile file differs
from v2. Each other rig failure stops the run, because no file change can fix
it. Examples are an init wait at its limit, a camera that does not take a
written value, and a failed gateway probe.

A normal run has 3 agent tasks and 5 runner stages. The planning run needed
dozens of tasks. Step 1 needs few, because v2 already gives each file value
and each check.

## File write rules

1. An agent task writes only to its own output root, outside the worktree.
   The runner copies the current version of each step 1 text file there
   first. After the task, the runner copies the changed files into the
   worktree and commits them.
2. The implement, repair, and fix tasks may change only these files, all in
   `src/venimapping_bringup/`: `config/camera.yaml`,
   `config/acquisition_profile.yaml`, `launch/camera.launch.py`,
   `CMakeLists.txt`, `package.xml`, and `test/test_camera_config.py`. Each
   task also writes one notes file in the output folder.
3. The review task writes only `output/review.md` and `output/review.json`.
4. No agent task may write `config/camera_settings.xml`. Only the settings
   stage makes it, on the camera.
5. A file outside these lists stops the run, and the runner imports nothing
   from that task. A changed file in the worktree, a changed driver checkout,
   or a deleted step 1 file also stops the run.
6. Runner stages write only to the output folder and, for the settings stage,
   to `config/camera_settings.xml`.
7. Each commit names only its own paths, so an unrelated change in the
   worktree is never committed.

The output folder is `docs/architecture/image-acquisition-step-1/output/`.
The run folder, with the state, the attempts, and the locks, is
`/home/labuser/workspace/projects/venimapping-image-acq-step-1-run`. It is
outside the worktree.

## Camera rules

1. No agent task can use the camera. Claude gets no shell except read-only
   git. Codex runs in a sandbox with no network, so it cannot reach the
   camera or DDS. Each prompt also forbids a driver, a launch, and a ROS
   command.
2. After each agent task, the runner stops the run if a camera driver
   process runs. It leaves that process alone.
3. The runner owns each driver launch. Each launch runs in its own process
   group, and the runner records the group before it waits. The console
   output goes through `2>&1 | tee <name>.log`.
4. The init wait is the v2 command,
   `timeout 60 sh -c 'until grep -qF "Initialization done!" "$1"; do sleep 0.5; done' sh <name>.log`.
5. Each feature write goes through one function with an allow-list:
   `PixelFormat`, `Width`, `Height`, `TriggerSelector`, `TriggerMode`,
   `ExposureTime`, `AcquisitionFrameRateEnable`, and `AcquisitionFrameRate`.
   A write to any other feature is refused. So the runner cannot change IP
   settings, firmware, or user sets.
6. The runner calls `settings/save` once, in step 7 of the settings stage. The
   save function accepts only an absolute `.xml` path inside the run folder
   or the bring-up config folder. The runner never calls `settings/load`,
   `stream_start`, or a command feature.
7. The runner makes the settings file on a driver that `ros2 run` starts with
   a runner parameter file: `camera_id` `0GPF3`, `autostream` 0, and
   `buffer_count` 7. That driver has no `settings_file`, as v2 asks, and the
   agent files cannot change it.
8. The runner scans the saved file before any driver loads it. The scan
   needs each of the seven profile values. It also looks for each feature
   that matches a denied pattern in `settings.json`, for example
   `GevPersistentIPAddress` or `UserSetDefault`. The driver writes each
   feature in the file on each open, so such a feature could change IP
   settings or user sets. `camera.xml_denied_policy` decides what happens:
   1. `stop`: the run stops, and the file stays in the logs only.
   2. `strip`: the runner removes each denied name from the package copy,
      scans the copy again, and keeps the saved file unchanged in the logs.
      The report lists each removed name.
   3. `load`: the package gets the file as saved, and the report lists the
      denied names.
   On this camera, the saved file holds 2206 feature entries, among them the
   IP configuration, the persistent IP, the user set selection, and
   `DeviceUserID`. So `stop` always stops the run, and `settings.json` sets
   `strip`.
9. At the end of each camera stage, the runner stops each of its driver
   groups, checks that no `vimbax_camera_node` process is left, and stops the
   ROS daemon. At the end of the run, it checks again.
10. A camera driver that the runner did not start stops the run before a
    camera stage. The runner leaves that driver alone.

## Restore rule

1. The first camera stage takes one baseline snapshot of each allow-listed
   feature, before its first write. `TriggerMode` is read under
   `FrameStart`. The runner keeps the baseline in the run state and in
   `camera-baseline.json` in the run folder. A resumed run uses the same
   baseline, so a restore never writes values from the middle of a run.
2. After each camera stage that wrote a feature, the runner starts a driver
   without `settings_file`, stops the stream, and writes back each baseline
   value that differs. It then reads each value back.
3. The order keeps each write valid. The shape values come first. Then
   `TriggerSelector` `FrameStart` and `TriggerMode`, then `ExposureTime`.
   If the baseline enable is true, the runner writes the enable and then the
   rate. If it is false, the runner writes only the enable, because the rate
   is then read only. `TriggerSelector` comes last.
4. If the restore or its readback fails, the run stops, and the state marks
   the camera as not clean. The next start tries the cleanup first.
5. The restore does not undo the purpose of step 1. Step 1 makes a file that
   the driver loads on each open with the default launch. The restore changes
   only the volatile camera values, and it runs after the save and after the
   rig check. The next default launch applies the profile again.

## Results that contradict v2

The runner never edits v2. It records each such result in `output/report.md`.

1. P11, camera write persistence. The rig stage tests it after the exit
   checks. It starts a driver with `settings_file:=/nonexistent.xml`, writes
   `ExposureTime` 10000.0 and `AcquisitionFrameRate` 20.0, restarts the
   driver the same way, and reads the values back. If they did not survive,
   the run continues with the v2 fallback in section 10, part A note 5. The
   report then lists the values after the restart. Part A still fails on a
   failed load, because the failed-load `grep` runs on each launch log.
2. The 60 s init wait limit. The report lists each init wait and its time. A
   wait at the limit stops the run, because a new limit is a change to v2.
3. The `launch` and `tee` line order. The report gives the line numbers of
   the failed-load line and the init line in the control log.
4. The parameter override order, P2, and the host check. The report gives the
   result of exit checks 4, 5, and 9, and the `sysctl` values.
5. Part A step 11 asks for a readback within 0.001 of 10000.0 and 20.0. The
   camera rounds an `ExposureTime` write to its increment of 13.172 us, so
   10000.0 reads back as 10004.707. The runner passes step 11 when a float
   readback is within one increment of the written value, as
   `features/float_info_get` reports it, and differs from the profile value.
   The report lists each rounding under part A step 11. P11 compares the
   values after the restart with the values that the camera held.

## Stop and resume

1. Each stage ends with a checkpoint commit and a push. A commit carries the
   trailers `Step1-Stage`, `Step1-Attempt`, and `Step1-Tool`.
2. `output/RUN.md` is the status file. It gives the status, the stop reason,
   what Logan must do, the resume command, each stage, the tool pauses, the
   camera state, and the last errors.
3. A run lock in the run folder stops a second runner. A camera lock guards
   each camera stage.
4. A quota error pauses that tool until the reported reset. Claude launches
   alternate between the two accounts and skip a paused account. A transient
   error retries after 30, 90, and 270 s.
5. A stage that a crash or a signal cut short runs again. An interrupted agent
   is killed on the next start. A stage that the runner committed but did not
   record is adopted from its commit. An open camera stage gets its cleanup
   first.
6. On a stop, the runner commits `RUN.md`, writes `final-status.txt` in the
   run folder, and exits with status 2. A failed rig or settings stage commits
   its logs first.
7. At the end, the runner pushes and checks that the remote branch has the
   last commit. The runner pushes only `HEAD:refs/heads/feat/image-acquisition-step-1`,
   never with force.

## Dry run

`runner/dryrun/dryrun.py` runs the real runner against a throwaway repository
and remote. Fakes stand in for `claude`, `codex`, `colcon`, `ros2`, and the
driver. The fake driver loads the settings file, prints the failed-load line
and the init line, and keeps the camera state. The fake `ros2` serves each
service call, parameter read, and graph read.

The scenarios:

1. main: the success path, with an interrupted agent, a transient error, a
   failed test and its repair, a quota pause on both Claude accounts, a Codex
   quota pause, a failed push, a crash after a commit, a SIGKILL during part
   A, a restore from the baseline, a failed rig check and its repair, and a
   failed final push.
2. forbidden: a task that writes outside its paths, and the resume.
3. init: a driver that never prints `Initialization done!`, and the resume.
4. rigfail: a camera that does not take the part A values, a foreign driver
   before a camera stage, and the resume.
5. p11: a camera that resets on each driver start.
6. restore: a restore write that fails, and the resume.
7. decoy: an agent that starts a driver.
8. xml: a saved file with an IP feature.
9. exhaust: a repair that changes no file, and a second rig failure.

## Measured on the camera in pass 2

1. A driver without a settings file prints the init line after 13 to 15 s.
   With the stripped settings file it takes 19 to 23 s (18.59 s and 22.62 s
   in rehearsal 5). The load alone takes 6 to 10 s.
2. A `status` call steps through each trigger selector and leaves
   `ExposureActive` selected. So the baseline selector is `ExposureActive`.
3. `ExposureTime` has the increment 13.172 us. `AcquisitionFrameRate` has
   none.
4. No driver loaded the untrimmed saved file on the camera. Rehearsal 2 used
   `stop` and stopped at the scan. Rehearsals 3 to 5 loaded only the
   stripped file. The only failed-load lines in pass 2 come from the control
   and P11 launches, which use `/nonexistent.xml` on purpose (error -3,
   `VmbErrorNotFound`).
5. The stripped file loaded with no failed-load line in `driver_a.log` and
   `driver_b.log`. After the reopen, check E9 read the full profile back from
   the part A values. See `evidence/rehearsal5-rig-results.json`.
6. The SDK load returns success although the file holds hundreds of read-only
   entries, so it skips features that it cannot write. A successful load
   therefore does not prove that each value took. Only a readback does.
7. A query-only probe read the write flag and description of each camera
   feature, with no write: `evidence/featinfo_full.tsv`. Its columns are the
   module, the name, the data type, the flags (R read, W write, V volatile,
   M modify write), streamable, visibility, category, tooltip, and
   description. Commands in the saved file, such as `UserSetSave`,
   `DeviceReset`, and `LUTSaveAll`, are stored as `IgnoredFeature`.
8. Pass 2 added these denied patterns. The strip removes each match from the
   package copy:
   1. `^CorrectionSetDefault$`: it sets the correction set that the camera
      uses after a reset, so a load writes power-up behavior.
   2. `^(GevSCPSPacketSize|GVSPPacketSize)$`: the load runs after the driver
      adjusts the packet size on open, so the file would replace the
      adjusted value with a size that fits only a 9000 byte MTU.
   3. `^TestPendingAck$`: a test feature. A write makes the camera delay its
      reply by the written value.
   4. `^TLParamsLocked$`: the transport layer sets it during acquisition. A
      profile file has no reason to write it.

## Not tested on hardware

These are notes for the later steps. Step 1 does not test them.

1. Cold start after power loss. No check has power cycled the camera. The
   saved file names the factory `Default` user set as the power-up set. That
   the stripped file restores the profile from a cold boot is an assumption.
2. Reconnect and the reload time. No check has pulled the cable. The reload
   after a reconnect, its time, and the restart that follows are not
   measured.
3. Streaming with `net.core.rmem_max` at 4 MB. The stream module asks for a
   64 MB socket buffer (`GVSPHostReceiveBufferSize` 67108864), and the OS
   caps it at `rmem_max`. No step 1 check streams.

## What pass 2 must prove on the camera

1. The `ros2 service call` output on this driver matches the parser, for each
   feature type and for `status`.
2. The launches, the `tee` capture, the init waits, and the `grep` checks work
   with the real driver, and the init time is well below 60 s.
3. The snapshot, the restore order, and the readback work on the real camera.
4. `settings/save` writes a file, and the scan reads its real format. The
   denied patterns fit the features that the real file holds.
5. A SIGINT to a launch group stops the driver, and no process is left.
6. The preflight passes.
