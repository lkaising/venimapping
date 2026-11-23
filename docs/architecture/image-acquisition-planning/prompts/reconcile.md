## Task: reconcile the two traces

You are the coordinator. Stay neutral. You run on Claude, so check that you do
not favor the Claude trace.

Read `{P}/claude/trace.md` and `{P}/codex/trace.md`. Then write
`{P}/coordinator/facts.md` with these sections:

1. Agreed facts. List the facts that both traces support, with citations.
2. Settled conflicts. Where the traces disagree about a fact, read the code or
   the driver source yourself and settle it. Give the citation and say which
   trace was correct.
3. Audit of v1. Merge the two audits into one table.
4. Requirements and working assumptions. List the unknown requirements, for
   example frame consumers, resolution, frame rate, latency, and memory. For
   each one, give a working assumption that is cheap to reverse, and list what
   depends on it. Mark each one where the answer from Logan would change the
   design.
5. Design choices. Merge both lists into one list with the ids D1, D2, and so
   on. Give each choice a question and the options. Mark each choice that
   crosses the drafting split. A choice crosses the split when the sections of
   both planners depend on its answer.

Read the camera request files in `{P}/claude/camera-requests/` and
`{P}/codex/camera-requests/`, if they exist. Accept a request only if its
answer changes a design choice. Add the accepted checks in the emit file, and
make them block the positions tasks.
