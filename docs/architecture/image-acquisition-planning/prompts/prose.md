## Task: rewrite v2 as a standalone engineering design

Turn `{V2}` from an integrated planning checkpoint into a standalone
engineering design document. Write for an engineer who never followed the
planning run and has not read v1 or the planning folder. After reading `{V2}`,
that engineer should understand what we are building, why the important choices
were made, how to implement it, and how to verify it.

Read `{V2}`, `{P}/issues.md`, `{P}/coordinator/facts.md`, and
`{P}/camera-log.md`. Work from whichever integration checkpoint feeds this
task; do not assume a fixed round number or issue list. Check `{P}/issues.md`
for any prose-pass notes and for any issue whose status is still `Open`.

### Structure and consolidation

There is no target word count and no prescribed outline. Reorganize `{V2}` into
the clearest standalone structure for an engineering reader. Consolidate
duplicated material so each topic has one authoritative home, with internal
cross-references where other sections depend on it. Examples of duplication to
consolidate include repeated current-state summaries, repeated file
inventories, repeated CMake target/export rules, and repeated camera
measurements.

### What to preserve in full

Do not omit, soften, abridge, or replace with placeholders any technical
substance. Keep all of the following intact:

1. **Contracts and mechanics:** every public and internal type, field, method
   signature, code sketch, ownership and lifetime rule, threading and locking
   invariant, admission/epoch/freshness rule, stream state transition,
   failure/outage/wedge recovery sequence, error code and caller action, and
   bring-up parameter, file, and check.
2. **Measured camera behavior:** keep a compact section titled
   `Measured camera behavior` as the primary home for the unique hardware
   characterization results already captured in `{V2}`. Preserve all
   measurements, units, test conditions, sample sizes or windows where
   recorded, and source references to the camera check records. Keep measured
   results, derived estimates, and questions left open clearly distinguishable.
   Consolidate repeated measurement details out of other sections and point
   back to `Measured camera behavior` from the design rules they support.
3. **Verification, layout, and delivery:** all four testing tiers (fakes,
   synchronization and observation hooks, test cases, and hardware check
   procedures), the complete proposed source tree and CMake target/export
   rules, and the full ordered implementation sequence with per-step files,
   dependencies, and exit checks.
4. **Assumptions, deferred scope, and open decisions:** all working assumptions
   with their dependencies, reversal costs, and triggers; deferred scope and
   triggers to revisit it; empirical gates (such as the probe threshold that
   decides an executor split); all unresolved decisions for Logan (such as the
   timestamp source question) with options, consequences, and defaults; and any
   issue still marked `Open` in `{P}/issues.md`, surfaced explicitly as an open
   question or decision.

### What to cut or transform

Before cutting any section, table, or bullet, extract every unique engineering
rationale, rejected-alternative trade-off, constraint, or caveat and fold it
into the owning design section or open decisions. Then remove:

1. **Planning-run scaffolding:** draft-status headers, section-owner and
   coordinator attribution banners, integration-round recaps, and closed-issue
   tallies.
2. **Register and amendment logs:** register summary tables and round-by-round
   contract-amendment patch logs. Verify first that every accepted rule and
   contract detail appears in full in its owning design section.
3. **v1 comparisons:** any `Changes from v1` section, per-section "What this
   section changes from v1" tables, and v1-diff framing in prose or test
   tables. Frame rejected or deferred alternatives on their engineering merits,
   preserving any rationale, constraint, or caveat that previously appeared
   only in a v1 comparison.
4. **Settled and withdrawn disagreements:** planner-vs-planner scoreboards and
   accounts of how settled disagreements were negotiated. State each lasting
   design rule and its engineering rationale directly. Keep genuine unresolved
   decisions in the open decisions section.
5. **Internal planning-folder pointers:** remove references to draft section
   files, draft line numbers, and planning-specific IDs (such as register,
   contract, issue, note, audit, or conflict IDs) from the main prose unless an
   ID provides a useful link to an unresolved decision or source record. Where
   a claim cites `facts` shorthand, resolve it back to its direct `path:line`,
   `driver:path:line`, `ros:path:line`, or SDK citation from
   `{P}/coordinator/facts.md`.
6. **Draft-bug descriptions in test tables:** rewrite test failure-mode or
   old-behavior notes that refer to earlier draft bugs or v1 behavior so they
   describe the real current-codebase behavior, driver behavior, or regression
   each test guards against.

### Evidence labels, IDs, and writing style

1. Keep `[F]`, `[A]`, and `[Q]` where they help readers distinguish evidence,
   assumptions, and open questions. Place the tag where a finding, assumption,
   or open question is defined, and do not repeat it on every later reference.
   For this final document, this supersedes the per-claim labeling rule in
   `common.md`.
2. Keep stable, searchable IDs that readers will use to cross-reference the
   design, such as `L1` to `L9` and useful `R` or `T` IDs. State each rule or
   finding in full where it is defined so the reader can understand it without
   opening another file.
3. Use the ASD-STE100 rules in `common.md` as a guide: prefer active voice,
   consistent terms, plain words, sentence-case headings, and short, clear
   sentences. Use your judgment on the 20- and 25-word limits when keeping a
   technical condition together with its exception makes a rule easier to
   follow.
4. If a passage is genuinely unclear or contradictory in a way that affects
   technical meaning, leave its substance intact and list it in the report
   rather than guessing.

### Required outputs

1. Write the complete revised `{V2}`.
2. Write a concise `{P}/coordinator/prose-pass.md` containing:
   - An old-to-new section map.
   - Notes on deliberate cuts or substantive rewrites that could affect
     technical meaning, stating where any retained rationale, constraint, or
     caveat moved.
   - Any unclear passages left intact.
