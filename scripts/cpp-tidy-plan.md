# C++ Static Analysis Configuration Plan

| | |
|---|---|
| Status | Draft — implementation sidelined; three open decisions (T1–T3) |
| Scope | Root `.clang-tidy` policy file; toolchain update; analysis settings in `scripts/ide.sh` |
| Date | 2026-08-17 |

This document is the source of truth for adding clang-tidy static analysis to
the workspace. It is the companion to the (now implemented) C++ style
configuration plan and follows the same shape: investigated facts, decisions,
exact artifacts, and a rollout order. Implementation is deliberately deferred;
nothing here is scheduled.

---

## 1. Background

The workspace has no static analysis of any kind: no `.clang-tidy`, no ament
lint hooks, no CI. The style layer (`.clang-format`, format-on-save through
cpptools) is in place; clang-tidy is the natural next layer — it catches what
a formatter cannot (bug-prone patterns, pessimizations, naming violations) and
cpptools runs it natively once a `.clang-tidy` exists.

The concrete motivator recorded in the style plan's deferred-work list:
naming enforcement would mechanize the project conventions and catch the one
known violation, the lowercase `ErrorDomain` enumerators.

## 2. Investigated facts

### 2.1 Toolchain matrix

| Component | Version | Notes |
|---|---|---|
| `/usr/bin/clang-tidy` | 18.1.3 | Same LLVM release as the clang-format used for normalization |
| `/usr/bin/c++` (libstdc++) | GCC 13.3.0 | Provides the standard library clang-tidy parses against |
| cpptools (active) | 1.33.8 | 1.32.2 also on disk; 1.33.8 is the loaded one |
| cpptools bundled clang-tidy | 22.1.3 | Used when `C_Cpp.codeAnalysis.clangTidy.path` is unset |
| Ubuntu 24.04 archive | `clang-tidy-19` (19.1.1), `clang-tidy-20` | Plain `apt install`; installs alongside 18, does not replace it |

### 2.2 The parse blocker (and its fix)

System clang-tidy 18 cannot parse the project at all: every TU dies on
`std::expected`. Cause: libstdc++ 13 guards `<expected>` (and the
`__cpp_lib_expected` macro) behind `__cpp_concepts >= 202002L`
(`/usr/include/c++/13/expected:34`), and clang 18 still advertises the older
value; clang 19 fixed this. Verified on a minimal repro and on the full tree:

- Without intervention: 3 errors on the repro, ~45 across the tree.
- With `-D__cpp_concepts=202002L -Wno-builtin-macro-redefined`: clean parse,
  exit 0.
- The flags work from inside `.clang-tidy` via `ExtraArgs`, so the config
  file is self-contained — no wrapper scripts, no editor arguments.

Two clarifications worth recording:

- The `#error` guard at `expected.hpp:14-16` is not the problem; it fires as
  designed when the frontend/stdlib pairing hides `std::expected`. Removing
  it would only replace one clear diagnostic with the same failure as ~45
  confusing cascade errors.
- cpptools' bundled clang-tidy 22 does not need the workaround. Redefining
  the macro to the value clang ≥ 19 already uses is harmless there.

### 2.3 Noise measurement

All measurements with clang-tidy 18.1.3 plus the section 2.2 workaround (a
clean parse; an earlier errored run produced phantom findings —
`bugprone-empty-catch`, `misc-const-correctness` — that do not exist under a
clean parse). Header findings surface via `HeaderFilterRegex`; all five
project headers are reached through the three TUs.

Full breadth — `bugprone-*, performance-*, modernize-*, readability-*,
misc-*, concurrency-*, cppcoreguidelines-*` — yields 140 findings, of which
116 come from two checks that contradict documented project decisions:

| Check | Count | Conflict |
|---|---:|---|
| `modernize-use-trailing-return-type` | 67 | Pure style conflict |
| `misc-include-cleaner` | 49 | Transitive includes are deliberate (style plan, deferred work) |
| everything else | 24 | See the curated run below |

The curated section 5.1 config yields **10 findings, 0 errors**:

| Site | Check | Disposition |
|---|---|---|
| `expected.hpp:27,28` (`driver`, `gateway`) | `readability-identifier-naming` | The known `ErrorDomain` inconsistency; rename to `kDriver`/`kGateway` (2 definition sites, 3 use sites, 1 comment) |
| `expected.hpp:53,57,60` (`domain`, `code`, `text`) | `readability-identifier-naming` | False positives: Google-sanctioned lower_case trivial accessors — open decision T1 |
| `expected.hpp:53,57,60` | `modernize-use-nodiscard` | Open decision T2 |
| `gateway_util.hpp:19` (`GatewayDiagnostic`) | `performance-enum-size` | Open decision T3 |
| `vimbax_camera_gateway.cpp:135` | `performance-unnecessary-value-param` | Real: the constructor copies `camera_namespace` but only reads it; take `const std::string&`. (`Create()` at `:103` is correctly not flagged — it moves.) |

## 3. Environment constraints

- **cpptools integration is one key.** `C_Cpp.codeAnalysis.clangTidy.enabled`
  turns analysis on; it runs automatically on open/save by default. With
  `...clangTidy.path` unset the bundled binary (22.1.3) runs; `.clang-tidy`
  is discovered upward from each source like `.clang-format`. Key names
  verified against the installed extension's `package.json`.
- **Version skew.** CLI 18 (or 19 after the toolchain update) versus bundled
  22. A curated explicit check list keeps this benign — no `-*`-relative
  defaults to drift — but check behavior can still differ across majors.
  Full closure would pin `...clangTidy.path` to the system binary; not done
  by default, same stance as the style plan's clang-format contingency.
- **Compile flags come from the ide.sh-merged database** for CLI runs
  (`-p build`); cpptools uses its own IntelliSense configuration. Both parse
  the same tree; findings matched in trials.
- **ide.sh contracts.** Everything ide.sh writes is gitignored and
  regenerated byte-identically; an existing `settings.json` is never parsed,
  merged, or edited. `.clang-tidy` is committed policy — ide.sh never
  generates or touches it, exactly as with `.clang-format`.
- **rclcpp parse cost.** A full three-TU CLI sweep takes on the order of a
  minute; the editor analyzes per-file on save, which is acceptable.

## 4. Decisions

- **T-A — Curated allowlist, not group defaults.** `Checks` starts from `-*`
  and names the groups explicitly, with per-check disables for the measured
  conflicts (`use-trailing-return-type`, `include-cleaner`,
  `easily-swappable-parameters`, `use-std-print` — the latter suggests
  `std::print`, which GCC 13's libstdc++ does not ship).
  `readability-*` and `cppcoreguidelines-*` are excluded wholesale for now
  (their residual is magic-numbers/cognitive-complexity-class noise) except
  `readability-identifier-naming`, which is the motivating check.
- **T-B — `.clang-tidy` lives at the repo root and is checked into git.**
  Same rationale as `.clang-format`: durable, reviewable, works outside
  VS Code. ide.sh never touches it.
- **T-C — Keep the `ExtraArgs` workaround in the config.** It is required on
  clang-tidy 18, harmless on ≥ 19 and on the bundled 22. It can be deleted
  once nothing that runs the config is on 18, but nothing forces that.
- **T-D — Update the CLI toolchain to `clang-tidy-19`** (section 7). This
  removes the *dependence* on T-C for CLI runs and closes most of the skew
  gap. `/usr/bin/clang-tidy` remains 18; the newer binary is invoked
  explicitly as `clang-tidy-19`. clang-format is deliberately not updated:
  no friction exists there, and a newer major would risk invalidating the
  normalization baseline for nothing.
- **T-E — Editor-only, warnings-only.** No CI gate, no `WarningsAsErrors`.
  Enforcement escalation is deferred work.
- **T1 — OPEN: the three lower_case accessors versus `FunctionCase`.**
  clang-tidy cannot express "trivial accessors may be lower_case". Options:
  (a) three `NOLINT(readability-identifier-naming)` trailers — full
  enforcement, three annotations; (b) drop the `FunctionCase` option — zero
  annotations, but future misnamed functions go uncaught; (c) rename the
  accessors — abandons a Google-sanctioned convention. Leaning (a): the
  annotations are self-documenting and the check stays armed.
- **T2 — OPEN: `modernize-use-nodiscard` on the same three accessors.**
  Adding `[[nodiscard]]` is arguably correct and settles it; disabling the
  check is the no-churn alternative. Independent of T1 but touches the same
  lines — resolve together.
- **T3 — OPEN: `performance-enum-size` on `GatewayDiagnostic`.** Its
  `std::int32_t` base matches the `Error::code()` contract, which reads as
  deliberate. Options: disable the check, or a single `NOLINT` with a
  comment stating the contract. Leaning the `NOLINT`: the check stays armed
  for future enums.

## 5. Artifacts

### 5.1 `.clang-tidy` (repo root, committed)

As trialed (10 findings, 0 errors, section 2.3). T1–T3 may remove the
`FunctionCase` option or add per-check disables; the annotated lines mark
the dependencies.

```yaml
---
Checks: >
  -*,
  bugprone-*,
  -bugprone-easily-swappable-parameters,
  concurrency-*,
  misc-*,
  -misc-include-cleaner,
  modernize-*,
  -modernize-use-trailing-return-type,
  -modernize-use-std-print,
  performance-*,
  readability-identifier-naming
WarningsAsErrors: ''
HeaderFilterRegex: 'venimapping_camera'
ExtraArgs:
  - '-D__cpp_concepts=202002L'
  - '-Wno-builtin-macro-redefined'
CheckOptions:
  readability-identifier-naming.ClassCase: CamelCase
  readability-identifier-naming.StructCase: CamelCase
  readability-identifier-naming.EnumCase: CamelCase
  readability-identifier-naming.EnumConstantCase: CamelCase
  readability-identifier-naming.EnumConstantPrefix: k
  readability-identifier-naming.FunctionCase: CamelCase   # T1 pending
  readability-identifier-naming.NamespaceCase: lower_case
  readability-identifier-naming.ParameterCase: lower_case
  readability-identifier-naming.PrivateMemberCase: lower_case
  readability-identifier-naming.PrivateMemberSuffix: _
  readability-identifier-naming.TypeAliasCase: CamelCase
  readability-identifier-naming.VariableCase: lower_case
...
```

Notes:

- `modernize-use-nodiscard` stays enabled or joins the disables per T2;
  `performance-enum-size` likewise per T3.
- The naming options reproduce the conventions table in the style plan;
  `EnumConstantPrefix: k` + `CamelCase` accepts the existing
  `kPascalCase` enumerators (verified — zero false positives on
  `GatewayDiagnostic`).
- `ExtraArgs` exists per section 2.2 / T-C.

### 5.2 `settings.json` addition (generated by ide.sh when absent)

One key, inserted after the three `C_Cpp.clang_format_*` keys:

```json
    "C_Cpp.codeAnalysis.clangTidy.enabled": true,
```

Everything else about the document is unchanged from the style plan's 5.2.

## 6. `scripts/ide.sh` changes

Confined to `ide_write_settings()` and its messages, mirroring the style
rollout:

1. **Fresh-file document**: add the section 5.2 key to the generator's `doc`.
2. **Existence probe**: add `C_Cpp.codeAnalysis.clangTidy.enabled` to the
   probed-marker list (making five). Warn path and its never-edit stance are
   already generic ("missing keys: ..."); no message changes needed.
3. **Policy-file check**: extend the existing `.clang-format` warn-only check
   to also warn when `.clang-tidy` is absent. Non-fatal, does not affect the
   summary.

## 7. Toolchain update

Machine prep, no commit (parallel to the style plan's "local migration"):

```bash
sudo apt install clang-tidy-19
```

Then verify the expectation this plan could not test read-only: that
clang-tidy-19 parses `std::expected` against libstdc++ 13 **without** the
`ExtraArgs` workaround (temporarily strip the two lines and run the section 8
gate with `clang-tidy-19`). If it does not, 19 brings no benefit — stay on
18 + workaround and strike T-D.

## 8. Normalization

Before the config lands, the baseline is made clean so analysis starts at
zero findings:

- Rename `ErrorDomain::driver/gateway` to `kDriver`/`kGateway` (6 sites,
  section 2.3).
- Constructor `camera_namespace` parameter to `const std::string&`
  (`vimbax_camera_gateway.cpp:134`).
- T1/T2/T3 outcomes: `NOLINT` trailers and/or `[[nodiscard]]` and/or config
  disables.

## 9. Verification

- `git ls-files '*.cpp'` piped to the chosen clang-tidy binary with
  `-p build` reports zero findings and zero errors after normalization.
- Repro check: the same run with `ExtraArgs` stripped still parses under
  clang-tidy-19 (section 7); still fails under 18 (confirming the workaround
  is what carries 18).
- In VS Code: analysis produces zero squiggles on the normalized tree; a
  deliberately misnamed local produces a `readability-identifier-naming`
  squiggle; both cross-check bundled 22 against the CLI binary.
- Fresh `settings.json` regeneration matches section 5.2; probe/warn paths
  behave per section 6; repeated runs byte-identical; `shellcheck` clean.

## 10. Rollout

After this document, in order:

1. Machine prep (no commit): section 7 toolchain update and its
   verification.
2. `refactor(camera): add .clang-tidy and resolve its baseline findings` —
   the root policy file (T1–T3 resolved) plus the section 8 normalization,
   together, so the tree is clean the moment the policy exists.
3. `feat(scripts): enable clang-tidy analysis in ide.sh` — the section 6
   changes.
4. Local migration (no commit): delete `.vscode/settings.json`, rerun
   `scripts/ide.sh`.

## 11. Deferred work

- **CI enforcement**: the section 9 gate with `WarningsAsErrors: '*'` or
  `ament_cmake_clang_tidy`; requires pinning a clang-tidy major first.
- **Broadening the check set**: `cppcoreguidelines-*` and wider
  `readability-*` once thresholds (magic numbers, cognitive complexity) are
  worth curating; `misc-include-cleaner` only if the transitive-include
  stance is ever reversed.
- **Dropping `ExtraArgs`**: once no consumer of the config runs clang-tidy
  18 (T-C).
- **`.clang-tidy` fix-its in the editor**: cpptools exposes code actions for
  auto-fixable checks; evaluate after the baseline has soaked.
