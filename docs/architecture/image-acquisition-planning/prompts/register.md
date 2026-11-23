## Task: build the decision register

You are the coordinator. Stay neutral. You run on Claude, so check that you do
not favor the Claude positions.

Read `{P}/coordinator/facts.md`, `{P}/claude/positions.md`, and
`{P}/codex/positions.md`. Then write `{P}/register.md`.

Write one entry for each design choice. Give each entry these fields: id,
question, options, Claude position, Codex position, evidence, status, decision,
and rationale. The status is one of these values:

1. Agreed. The positions match in substance. Record the decision.
2. Settled. The positions differ, but the evidence clearly favors one. A choice
   that is cheap to reverse and does not cross the drafting split is also
   Settled. Record the decision, the reason, and the dissent in one sentence.
3. Disputed. The positions differ and the evidence does not settle them. Also,
   the choice crosses the drafting split or is expensive to reverse. Add
   dispute tasks for each Disputed entry in the emit file, and make them block
   register-final.

Do not mark a choice Disputed only to be careful. Each dispute costs four
tasks.

Read the camera request files in `{P}/claude/camera-requests/` and
`{P}/codex/camera-requests/` that the positions tasks wrote. Accept a request
only if its answer changes a design choice. Add the accepted checks in the
emit file, and make them block register-final.

Add a section named "Working assumptions". For each assumption, give what
depends on it and the cost to reverse it.
