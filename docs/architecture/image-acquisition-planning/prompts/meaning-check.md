## Task: check that the prose pass kept the meaning

This is the final cross-review. Compare v2 before the prose pass with v2 after
it. The completed tasks list gives the commits. The version before is at the
commit of the last integrate task. The version after is at the commit of the
prose task. Use `git -C <worktree> diff <before> <after> -- {V2}`.

Write `{P}/codex/meaning-check.md` with a table that has the columns Location,
Before, After, and Problem. Report only changes in meaning, lost content, and
changed decisions, numbers, names, or interfaces. Also check that the data
plane section still matches your draft in substance. If you find no problems,
say so in one line.
