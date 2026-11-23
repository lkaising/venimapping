## Task: repair a failed check

The check in stage `{failed}` failed. The runner gives this result:

```text
{detail}
```

The logs of the check are in `{worktree}/{logs}/`. Read `commands.log` first.
It holds each command that the runner ran, its output, and its exit status.
For a rig check, also read `results.json` and the driver logs in the same
folder.

Do these steps:

1. Find the cause of the failure. Use the logs, the step 1 files, and v2
   section 10.
2. If a step 1 file causes the failure, change that file in the output root.
3. If the cause is outside the step 1 files, do not change a file. Examples
   are a missing package, a camera that does not answer, or a value that v2
   gives wrong.
4. Do not change a file to make a check pass if the change contradicts v2.

The runner runs the build, the test, and the failed check again after your
change. If you change no file, the runner stops the run for Logan.

Write `{O}/repairs/{id}.md` with these parts:

1. The cause, with the evidence lines from the logs.
2. Each file that you changed, and what changed.
3. If you changed no file, what Logan must do.
