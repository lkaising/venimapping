## Task: settle the interface decisions for drafting

You are the coordinator. Stay neutral. You run on Claude, so check that you do
not favor the Claude verdicts.

Read `{P}/register.md` and each verdict file in `{P}/claude/disputes/` and
`{P}/codex/disputes/`. Then write the complete new `{P}/register.md`:

1. Update each Disputed entry. If both verdicts agree, record the decision and
   set the status to Decided by dispute. If they disagree, set the status to
   Working assumption. Record the assumption, what depends on it, the cost to
   reverse it, and each position in one sentence. Add the entry to the
   decisions for Logan.
2. Add a section named "Interface contracts". For each boundary between the
   data plane and the Claude sections, state the contract precisely enough for
   both planners to draft alone. Include the types and their fields, ownership
   and lifetime, the threads and which side calls which, the error values, and
   the timing guarantees.
3. Add a section named "Decisions for Logan". List only the questions where
   his answer changes the design. For each question, say what changes
   depending on the answer.

If a contract depends on a hardware fact, you may add a camera check that
blocks drafting.
