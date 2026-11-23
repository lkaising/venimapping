## Emit file

This task can add tasks to the run. To add tasks, write the optional emit file
`{P}/coordinator/emits/{id}.json`. Leave it out if you add no tasks. Use this
form:

```json
{
  "progress": {"closed": 0, "open": 0, "for_logan": 0},
  "tasks": [
    {"id": "camera-c1", "template": "camera-check", "tool": "codex",
     "params": {"check": "c1"},
     "camera": {"question": "...",
                "features": [{"name": "ExposureTime", "type": "float"}]},
     "deps": [], "blocks": ["positions-claude"]}
  ]
}
```

The runner rejects the whole emit file and stops the run if one rule fails.

1. Use only these templates: {emits}.
2. Use lowercase letters, digits, and hyphens in task ids. Each id must be new.
3. Use letters, digits, commas, periods, underscores, and hyphens in parameter
   values. Do not use spaces.
4. List in "deps" the tasks that must finish first. List in "blocks" the
   existing tasks that must wait for the new task. You may block only these
   tasks: {may_block}.
5. Give each camera check to the planner that asked for it. Keep each check
   short. List in "features" each feature that the check changes, because the
   runner restores and verifies only the listed features.
6. Give each dispute four tasks: dispute-position on claude and on codex, then
   dispute-judge on claude and on codex. Each judge depends on both positions.
   The "issue" parameter names the register entry or issue, for example "d3".
7. Give each fix task to the owner of the sections it changes. Give each
   recheck task to the other planner. The "sections" parameter is a comma list
   of section names from the section owners list. The "issues" parameter is a
   comma list of issue ids, for example "i3,i7".
8. Set "progress" in integrate tasks only. "closed" is the number of issues
   that this round closed.
