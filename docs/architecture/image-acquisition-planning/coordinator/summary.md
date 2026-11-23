# Coordinator summary

## What the run produced

The run produced `docs/architecture/image-acquisition-design-v2.md`, a standalone design for image acquisition in `venimapping_camera`. It has 15 sections. They give the current state, the measured camera behavior, the data plane, the control plane, the error vocabulary, bring-up, four test tiers, the source tree with CMake rules, a nine-step implementation sequence with one conditional step, the deferred scope, the empirical gates, and nine decisions for Logan (L1 to L9).

## Register status counts

`register.md` holds 29 decisions, d1 to d29:

| Status | Count | Entries |
|---|---|---|
| Agreed | 16 | d1, d2, d4, d7, d8, d11, d15, d16, d17, d21, d23, d24, d25, d27, d28, d29 |
| Settled | 12 | d3, d5, d6, d9, d10, d12, d13, d14, d18, d19, d22, d26 |
| Decided by dispute | 0 | |
| Working assumption | 1 | d20, the timestamp source. It is L1. |

`register.md` is still the `register-final` text. Issues i12, i28, i29, and i32 to i36 in `issues.md` record the later contract amendments. v2 states each amended rule in its owning section.

## Camera checks that ran

`camera-log.md` records three checks. After each one, the runner stopped the stream, restored and verified the features, and left no driver process.

1. c1 (Claude): formats, size, free-run rate, stamps, start latency, and access modes.
2. c2 (Claude): the software trigger and the `TriggerSelector` dependency.
3. c3 (Codex): the 30 Hz rate profile with `AcquisitionFrameRateEnable` true.

## Issues

`issues.md` has 36 issues. 35 are Closed and 0 are Open. One, i30, is For Logan. It is the d20 timestamp dispute, and v2 gives it as L1 with both positions.

## Meaning-check findings

The table in `codex/meaning-check.md` has 18 findings. This task applied all 18 and rejected none. Each restores substance that the prose pass lost or changed.

One related edit goes beyond the cited lines. The bring-up host check repeated the claim that a tuned host needs no `cyclonedds.xml`. The fix for the deferred-scope row changed that claim, so the host check now uses the same wording.

The one pre-existing inconsistency is about the get image cutoff. The freshness text said that the caller skips a frame whose sequence came before `subscribe`. The take loop skips `receive_seq <= R`, and `R` is read before `subscribe`. The data-plane contract and register d24 settle the rule. So section 8, "Freshness", items 3 and 4 now apply the `receive_seq <= R` predicate. They also say that the skipped frame can be the only pending frame. No open question was needed.

## Prose-pass unclear passages

1. The 110 ms start (item 1). The derived estimate now says that 110 ms runs to the `stream_start` reply, and that the first frame comes earlier.
2. R7 cost (item 2). The cost to reverse is Low for a cold limit of about 200 ms or more. A lower limit needs a linger (L6).
3. The 67 ms warm limit (item 3). It is now a derived estimate of two frame periods at 30 Hz, from c1 §4.
4. P11 (item 4). The meaning-check fixes for the bring-up note and the persistence gate resolve it. No check measured a restart without a power cycle.
5. L1 option 3 (item 5). The dual-stamp patch is now a fifth patch, not one of the four L3 candidates.
6. Inputs 11 and 12 (item 6). Not changed. The `take` rule is a new contract in section 7, so no project code exists to cite.

## Location of planning files

All paths are under `docs/architecture/image-acquisition-planning/`:

1. `register.md`, `issues.md`, and `camera-log.md`: decisions, issues, and the camera run log.
2. `coordinator/`: facts, the prose-pass report, and this summary.
3. `claude/` and `codex/`: traces, positions, drafts, reviews, fixes, rechecks, dispute verdicts, and camera requests.
4. `claude/camera/c1.md`, `claude/camera/c2.md`, `codex/camera/c3.md`: the camera check records that v2 cites as evidence.
5. `codex/meaning-check.md`: the meaning check of the prose pass.

The planning folder keeps the planning history, the v1 comparisons, and the settled disagreements. v2 does not repeat them.
