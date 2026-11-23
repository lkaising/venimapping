## Task: finish v2 for review

Read `{V2}`, `{P}/codex/meaning-check.md`, `{P}/coordinator/prose-pass.md`,
`{P}/register.md`, `{P}/issues.md`, and `{P}/camera-log.md`. When verifying a
finding against pre-prose `{V2}`, inspect
`git -C <worktree> show <before>:{V2}`, where `<before>` is the commit of the
last `integrate-*` task in the completed tasks list.

### Resolve meaning-check findings

For each finding in `{P}/codex/meaning-check.md`:

1. If the finding identifies lost or altered technical substance (a contract,
   number, name, interface, locking/threading rule, recovery step, measurement,
   citation, test or exit-check detail, assumption, open decision, engineering
   rationale, or broken cross-reference), fix it directly in the owning section
   of `{V2}` using clear standalone prose.
2. Follow the prose-pass style guidance: use ASD-STE100 as a guide (active
   voice, consistent terms, plain words, sentence-case headings), use judgment
   on the 20- and 25-word limits when keeping a condition with its exception
   makes a rule clearer, place `[F]`/`[A]`/`[Q]` where findings or decisions
   are defined, and keep searchable IDs such as `L1` to `L9` and useful `R`/`T`
   IDs.
3. **Do not restore removed planning history.** Never re-introduce draft-status
   banners, section-owner labels, integration-round recaps, register-amendment
   logs, `Changes from v1` tables, or settled/withdrawn disagreement logs. If a
   finding is factually incorrect or asks to restore pure planning history with
   no lost technical substance, keep the text in `{V2}` and record the reason
   in `{P}/coordinator/summary.md`.
4. Review any unclear passages listed in `{P}/coordinator/prose-pass.md`.
   Clarify wording only where the project code, driver source, or pre-prose
   `{V2}` settles it without inventing behavior.

### Final completeness check on `{V2}`

Before writing `{V2}`, verify that it stands on its own without truncation or
abridgment and contains:

- Current-state constraints, working assumptions (`[A]`), and architecture
  overview.
- Complete data-plane, control-plane, error-vocabulary, and bring-up contracts.
- A compact `Measured camera behavior` section preserving measurements, units,
  test conditions, sample sizes or windows, source references, and clear
  separation of measured results, derived estimates, and open questions.
- All four testing tiers, the proposed source tree with CMake target/export
  rules, and the ordered implementation sequence with per-step exit checks.
- Deferred-scope triggers, empirical gates, unresolved decisions for Logan
  (including any unresolved dispute such as the timestamp source question), and
  any issue still marked `Open` in `{P}/issues.md`.
- Zero leftover planning-run scaffolding, v1 comparison tables,
  settled-disagreement scoreboards, or dangling planning-folder citations.

### Required outputs

1. Write the complete final `{V2}`.
2. Write `{P}/coordinator/summary.md` in one page or less. Include:
   - What the run produced.
   - The number of decisions in each register status (from `{P}/register.md`,
     noting any post-register amendments recorded in `{P}/issues.md`).
   - The camera checks that ran (from `{P}/camera-log.md`).
   - The issues closed and left (from `{P}/issues.md`).
   - Disposition of `{P}/codex/meaning-check.md` findings (count applied, plus
     each rejected finding with a brief reason).
   - The location of each planning file, noting that planning history, v1
     comparisons, and settled disagreements remain archived in the planning
     folder rather than in `{V2}`.
