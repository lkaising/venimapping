## Task: answer the review findings

Codex reviewed the step 1 changes. Read `{worktree}/{O}/review.md` and
`{worktree}/{O}/review.json`. For each finding, do one of these:

1. If the finding is correct, change the step 1 file in the output root.
2. If the finding is not correct, keep the file. Give the reason, with
   evidence from v2, the driver source, or the code.
3. If the finding is about `camera_settings.xml`, you cannot change that
   file. Write "Not fixed" and the reason. The runner records it for Logan.

The runner runs the build, the test, and the rig check after your changes.

Write `{O}/fixes.md` with one entry for each finding. Give the id, one of
Fixed, Rejected, or Not fixed, what changed, and the evidence.
