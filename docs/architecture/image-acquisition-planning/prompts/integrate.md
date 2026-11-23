## Task: integrate v2, round {round}

You are the coordinator. Stay neutral. You run on Claude, so check that you do
not favor the Claude sections or reviews.

Build the complete v2 at `{V2}` from the section files, the register, the
facts, and both source tree files. Use this structure:

1. Summary. What v2 proposes, in one page or less.
2. Current state. The acquisition path today, from facts.md.
3. Requirements and working assumptions.
4. Architecture overview.
5. Data plane, from the Codex section.
6. Control plane, policy layer, and error vocabulary, from the Claude
   sections.
7. Bring-up.
8. Testing.
9. Proposed source tree, merged from both source tree files.
10. Implementation sequence.
11. Camera findings, from `{P}/camera-log.md` and the check files, if checks
    ran.
12. Changes from v1. Each v1 choice that v2 keeps, changes, or drops, with the
    reason.
13. Decisions for Logan. Each question, the options, what changes depending on
    the answer, and the recommended default.
14. Recorded disagreements. Each disagreement that remains, with both
    positions and the evidence.

Do not change the substance of a section. If a section has a problem, record
an issue for its owner.

Write `{P}/issues.md` with each open and closed issue. The sources are the
reviews, the rechecks, the fix responses, the dispute verdicts, and the
problems that you find while you integrate. Give each issue an id (i1, i2, and
so on, never reused), a source, an owner, a severity, a status, and a one-line
history. The status is Open, Closed, or For Logan. Keep the issues from earlier
rounds.

Add the tasks for this round in the emit file:

1. For the open issues, add one fix task for each owner, with the issue ids
   and the sections. Add a recheck task for the other planner that depends on
   the fix task.
2. If a fix and a recheck did not settle a consequential disagreement, add
   dispute tasks for it. Do this only once for each issue.
3. If you add any task, also add the next integrate round. Its round number is
   one more than {round}. It depends on all the new tasks and blocks prose.
4. Set progress.closed to the number of issues that this round closed.
5. If no issue is Open, add no tasks. The prose pass starts next.

Read the camera request files that the draft, review, and fix tasks
wrote. Accept a request only if its answer changes the design. Add each
accepted check in the emit file, and make the next integrate round depend on
it.

Work only on concrete issues. Do not open issues about wording.
