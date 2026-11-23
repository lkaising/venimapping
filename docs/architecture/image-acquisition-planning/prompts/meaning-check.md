## Task: check that the prose pass kept all technical substance

This is the final technical cross-review. Compare `{V2}` before the prose pass
with `{V2}` after it. From the completed tasks list, find `<before>` as the
commit of the last `integrate-*` task and `<after>` as the commit of the
`prose` task.

Use the last integrated `{V2}` (`<before>`) as the baseline for technical
fidelity. Because the prose pass reorganized sections, consolidated duplicates,
and cut planning history, do not rely on `git diff` alone. Read all four
sources:

1. Pre-prose `{V2}` via `git -C <worktree> show <before>:{V2}` (the technical
   baseline).
2. Post-prose `{V2}` in the worktree.
3. `{P}/coordinator/prose-pass.md` (use its section map and cut notes to audit
   moves and removals).
4. `{P}/codex/sections/data-plane.md` (consult for context on data-plane
   intent, not as the baseline).

Use `git -C <worktree> diff <before> <after> -- {V2}` as a secondary check
where helpful.

### Authorized edits (do not flag unless technical substance was lost)

The prose pass was explicitly authorized to:

- Reorganize the document and consolidate duplicated summaries, file lists,
  CMake rules, and repeated measurements.
- Remove draft banners, section-owner labels, integration-round recaps,
  closed-issue tallies, register-amendment logs, `Changes from v1` sections and
  tables, v1-comparison framing, and settled or withdrawn disagreement logs.
- Replace internal planning IDs and `facts` shorthand with self-contained
  prose, direct code/driver/ROS/SDK citations, and internal cross-references,
  while keeping `[F]`/`[A]`/`[Q]` at definition points and searchable IDs such
  as `L1` to `L9` and useful `R`/`T` IDs.
- Rewrite test failure-mode notes to describe real codebase/driver behavior or
  guarded regressions instead of draft bugs or v1 behavior.
- Relax the 20- and 25-word sentence limits when keeping a condition with its
  exception makes a technical rule clearer.

Do not report authorized history cuts or wording cleanup as problems.

### What to check and report

Report only real technical regressions, omissions, or standalone-document
defects introduced by the prose pass:

1. **Altered contracts or mechanics:** changed types, fields, signatures,
   error codes, numbers, thresholds, units, QoS or bring-up parameters,
   locking/threading/ownership rules, state transitions, recovery sequences,
   source-tree paths, CMake targets or exports, or implementation step order
   and exit checks.
2. **Lost substance or rationale:** dropped edge cases, constraints, caveats,
   source citations, test cases or fake hooks, hardware check steps, or
   engineering rationale—including rationale that previously appeared only in a
   removed v1 comparison, register amendment, or disagreement entry. Audit each
   cut listed in `{P}/coordinator/prose-pass.md` against pre-prose `{V2}`.
3. **Data-plane fidelity:** flag any change in data-plane substance introduced
   by the prose pass relative to pre-prose `{V2}`. Consult
   `{P}/codex/sections/data-plane.md` for context, and flag any pre-existing
   inconsistency between pre-prose `{V2}` and that draft separately rather than
   as a prose-pass regression.
4. **Measured camera behavior:** missing measurements, units, test conditions,
   sample sizes or windows, source references, or blurred boundaries between
   measured results, derived estimates, and open questions.
5. **Assumptions and unresolved decisions:** dropped, softened, or altered
   working assumptions (including dependencies and reversal costs/triggers),
   deferred-scope triggers, empirical gates, `[F]`/`[A]`/`[Q]` distinctions at
   definition points, unresolved decisions for Logan (such as the timestamp
   question), or any issue still `Open` in `{P}/issues.md`.
6. **Completeness and standalone hygiene:** accidental truncation or abridgment
   in long sections (especially Testing, Source tree, Implementation sequence,
   and Decisions for Logan), ungrounded claims added by the rewrite, broken
   internal cross-references, or dangling planning-folder references and jargon
   left in the prose.

### Required output

Write `{P}/codex/meaning-check.md`.

- If the prose pass introduced no problems, say so in one line.
- Otherwise, report prose-pass problems in a Markdown table with these columns:

  `| Location (before -> after) | Before | After | Problem | Substance to restore |`

  In `Substance to restore`, state only the missing or altered technical rule,
  measurement, citation, assumption, or rationale. Do not ask to restore
  removed planning-history sections, v1 comparisons, or settled-disagreement
  tables.
- If you notice any pre-existing inconsistency between pre-prose `{V2}` and
  `{P}/codex/sections/data-plane.md`, list it separately under a
  `### Pre-existing inconsistencies` heading below the table (or below the
  one-line clean result) so `finish` does not mistake it for a prose-pass
  regression.
