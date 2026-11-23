## Task: judge dispute {issue}

Work alone. The other planner judges the same dispute from the same
checkpoint. You cannot see its verdict until both are done.

Read entry {issue} in `{P}/register.md` or `{P}/issues.md`. Read
`{P}/claude/disputes/{issue}-position.md` and
`{P}/codex/disputes/{issue}-position.md`. Check their citations against the
code and the driver source.

Judge the evidence, not the author. You may rule against the position of your
own planner.

Write `{P}/{tool}/disputes/{issue}-verdict.md` with these parts:

1. Verdict. One of these: adopt the Claude recommendation, adopt the Codex
   recommendation, adopt a combination that you state exactly, or no
   consensus.
2. Reasons, with the citations that you checked. Name each citation that does
   not support its claim.
3. If there is no consensus, the working assumption to draft against, what
   depends on it, and the cost to reverse it.
