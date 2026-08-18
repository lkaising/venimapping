# C++ Static Analysis Configuration Plan

| | |
|---|---|
| Status | Implemented locally, section 9 verification passing (all gates, 2026-08-18); awaiting human commits per section 10 steps 2–3 |
| Scope | Root `.clang-tidy` policy file; toolchain update; analysis settings in `scripts/ide.sh` |
| Date | 2026-08-18 |

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
| Ubuntu 24.04 archive | `clang-tidy-19` (19.1.1), `clang-tidy-20` (20.1.2, `noble-updates`) | Plain `apt install`; installs alongside 18, does not replace it. `clang-tidy-20` is the T-D choice |

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
| `expected.hpp:27,28` (`driver`, `gateway`) | `readability-identifier-naming` | The known `ErrorDomain` inconsistency; rename to `kDriver`/`kGateway` at every reference including comments (2 definition sites, 3 use sites, 3 comment lines) |
| `expected.hpp:53,57,60` (`domain`, `code`, `text`) | `readability-identifier-naming` | False positives: Google-sanctioned lower_case trivial accessors — `NOLINT` trailers per resolved T1 |
| `expected.hpp:53,57,60` | `modernize-use-nodiscard` | Add `[[nodiscard]]` per resolved T2 |
| `gateway_util.hpp:19` (`GatewayDiagnostic`) | `performance-enum-size` | Single annotated `NOLINT` per resolved T3 |
| `vimbax_camera_gateway.cpp:134-135` | `performance-unnecessary-value-param` | Real: the constructor copies `camera_namespace` but only reads it; take `const std::string&` through the whole path (section 8 item 4). `Create()` at `:103` is not flagged today only because it moves; changing the constructor alone would surface `performance-move-const-arg` at `:122` plus a value-param finding at `:103`, so the fix extends through `Create()` |

**Provenance, and the clang-tidy-20 delta.** Everything above was measured
under clang-tidy 18.1.3 and stands as the record of that measurement; it
reproduces exactly — 10 findings, 0 errors, row for row — re-running the
5.1 config under 18 on 2026-08-18. Section 7's verification re-measures
under `clang-tidy-20` (T-D), and the group wildcards in `Checks` enable
checks that did not exist in 18, so the finding set can grow. It does:
**14 findings, 0 errors** under 20 — the same 10, plus four new
`performance-unnecessary-value-param` hits at `vimbax_camera_gateway.cpp`
`:302`, `:321`, `:349` and `:358`. All four are `.transform()`
continuations of the form `[](auto response) { ... }`, where the
`shared_ptr` response parameter is taken by value but only dereferenced;
18's copy of the check does not reach into lambda parameters. Nothing from
the 18 baseline disappeared, and the set under 20 is identical with and
without `ExtraArgs`. All four are resolved and fixed — section 8.1 — which
returns the tree to exactly this 10-finding baseline under 20.

## 3. Environment constraints

- **cpptools integration is one key.** `C_Cpp.codeAnalysis.clangTidy.enabled`
  turns analysis on; it runs automatically on open/save by default. With
  `...clangTidy.path` unset the bundled binary (22.1.3) runs; `.clang-tidy`
  is discovered upward from each source like `.clang-format`. Key names
  verified against the installed extension's `package.json`.
- **Version skew.** CLI 18 (or 20 after the toolchain update) versus bundled
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
- **T-D — Update the CLI toolchain to `clang-tidy-20`** (section 7). This
  removes the *dependence* on T-C for CLI runs and closes most of the skew
  gap. `/usr/bin/clang-tidy` remains 18; the newer binary is invoked
  explicitly as `clang-tidy-20`. Both 19 and 20 carry the `__cpp_concepts`
  fix, so either removes the `ExtraArgs` dependence; 20 is chosen because it
  is equally available from the noble archive (20.1.2 via `noble-updates`,
  plain `apt install`) and sits closer to the cpptools-bundled 22, halving
  the CLI-versus-editor skew at no extra install cost. Newer majors (21/22)
  were rejected because they require the third-party apt.llvm.org repo,
  against this plan's minimal-machine-prep stance; the documented closure
  for the residual skew remains pinning
  `C_Cpp.codeAnalysis.clangTidy.path`. clang-format is deliberately not
  updated: no friction exists there, and a newer major would risk
  invalidating the normalization baseline for nothing.
- **T-E — Editor-only, warnings-only.** No CI gate, no `WarningsAsErrors`.
  Enforcement escalation is deferred work.
- **T1 — RESOLVED: option (a), `NOLINT` trailers.** Each of `domain()`,
  `code()` and `text()` in `expected.hpp` takes a trailing
  `// NOLINT(readability-identifier-naming)`; the `FunctionCase` option
  stays. clang-tidy cannot express "trivial accessors may be lower_case",
  so the choice was between annotating and surrendering enforcement. The
  accessors are Google-sanctioned — a trivial accessor named after the
  member it returns — so renaming them (option (c)) abandons that
  convention, and dropping `FunctionCase` (option (b)) disarms the
  motivating check for every future function. Three self-documenting
  annotations keep the check armed, and any future trivial accessor requires
  a deliberate annotation — which is the desired sign-off moment.
- **T2 — RESOLVED: add `[[nodiscard]]` to the same three accessors.**
  `modernize-use-nodiscard` stays enabled. For pure const accessors on an
  error type the attribute is semantically correct — discarding
  `error.code()` is always a bug — so this is a genuine improvement, not
  check-appeasement. The no-churn argument for disabling the check is void:
  T1 already touches exactly these lines. The static factories
  `FromDriver`/`FromGateway` are not flagged (the check targets const member
  functions only), so the tree is quiet once the three accessors are
  annotated.
- **T3 — RESOLVED: a single `NOLINT` stating the contract.** The
  `GatewayDiagnostic` enum in `gateway_util.hpp` takes a trailing
  `// NOLINT(performance-enum-size): int32_t base matches the Error::code() contract`
  and the check stays enabled. `GatewayError()` feeds the enum value
  directly into `Error::code()`, whose type is `std::int32_t`, so the base
  *is* the contract expressed in the type. A global disable would let a
  genuinely oversized future enum slip through unnoticed. `ErrorDomain`
  already uses `std::uint8_t` and does not trip the check, so this stays a
  one-off annotation rather than a recurring cost.

## 5. Artifacts

### 5.1 `.clang-tidy` (repo root, committed)

As trialed (10 findings, 0 errors, section 2.3). T1–T3 resolved without
touching this file: no option removed, no per-check disable added — all
three outcomes are source annotations (section 8).

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
  readability-identifier-naming.FunctionCase: CamelCase   # kept per T1
  readability-identifier-naming.NamespaceCase: lower_case
  readability-identifier-naming.ParameterCase: lower_case
  readability-identifier-naming.PrivateMemberCase: lower_case
  readability-identifier-naming.PrivateMemberSuffix: _
  readability-identifier-naming.TypeAliasCase: CamelCase
  readability-identifier-naming.VariableCase: lower_case
...
```

Notes:

- `modernize-use-nodiscard` stays enabled per T2 (the three accessors gain
  `[[nodiscard]]`); `performance-enum-size` stays enabled per T3 (one
  annotated `NOLINT` on `GatewayDiagnostic`).
- The naming options reproduce the conventions table in the style plan;
  `EnumConstantPrefix: k` + `CamelCase` accepts the existing
  `kPascalCase` enumerators (verified — zero false positives on
  `GatewayDiagnostic`).
- `ExtraArgs` exists per section 2.2 / T-C.

### 5.2 `settings.json` addition (generated by ide.sh when absent)

One key, inserted after the two `C_Cpp.clang_format_*` keys
(`clang_format_style`, `clang_format_fallbackStyle`) and `C_Cpp.formatting`:

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
sudo apt install clang-tidy-20
```

Two things are then verified, both read-only against the tree, both with the
config passed explicitly (`--config-file=`): clang-tidy discovers
`.clang-tidy` upward from the *source* files, so a trial config parked in
`/tmp` is never found by discovery.

1. **Workaround independence.** Strip the whole `ExtraArgs` block from a
   copy of the section 5.1 config and run every TU
   (`git ls-files '*.cpp'`, `-p build`) through `clang-tidy-20`. Expected:
   zero parse errors — findings are fine, errors are not. Negative control:
   the same stripped config under system `clang-tidy` (18) must still fail
   on `std::expected`, and the unstripped config under 18 must parse
   cleanly; together these confirm the workaround is exactly what carries
   18. If clang-tidy-20 needs the workaround too, 20 brings no benefit —
   stay on 18 + workaround and strike T-D.
2. **Finding-set drift.** Run the full curated 5.1 config under
   `clang-tidy-20` and diff the finding set against the section 2.3
   baseline, which was measured under 18. The group wildcards in `Checks`
   enable checks that did not exist in 18, so the set can grow. Every new
   finding gets a disposition — fix it, `NOLINT` it, or disable the check
   with rationale — folded into section 8 before commit 1. The result is
   recorded in the section 2.3 provenance note.

## 8. Normalization

Before the config lands, the baseline is made clean so analysis starts at
zero findings. Every edit, enumerated:

In `expected.hpp`:

1. Rename `ErrorDomain::driver`/`gateway` to `kDriver`/`kGateway` at every
   reference — 8 sites (2 definitions at `:27-28`; 3 uses at `:41`, `:50`,
   `camera_gateway_probe.cpp:40`; 3 comment lines at `:55-56` and
   `vimbax_camera_gateway.hpp:65`), section 2.3. The probe's `"driver"` /
   `"gateway"` display strings stay untouched — they are output text, not
   references.
2. `domain()`, `code()` and `text()` each take one combined edit: prepend
   `[[nodiscard]]` (T2) and append `// NOLINT(readability-identifier-naming)`
   (T1). Three accessors, three edited lines.

In `detail/gateway_util.hpp`:

3. Append to the `GatewayDiagnostic` enum (T3):
   `// NOLINT(performance-enum-size): int32_t base matches the Error::code() contract`

Items 2 and 3 use trailing `NOLINT`s, not `NOLINTNEXTLINE` — a considered
choice: the resulting lines exceed the 100-column ruler, but
`ColumnLimit: 0` makes them mechanically safe and the annotation
self-documents at the site.

In `vimbax_camera_gateway.hpp` and `vimbax_camera_gateway.cpp`:

4. Pass `camera_namespace` as `const std::string&` through the whole path —
   four edit points: the `Create()` declaration (`.hpp:72-75`) and
   definition (`.cpp:101-103`), the private constructor declaration
   (`.hpp:110-112`) and definition (`.cpp:134-135`); the
   `std::move(camera_namespace)` at `.cpp:122` becomes a plain pass of
   `camera_namespace`. The parameter is never stored — it only feeds
   `MakeClient`/`ServiceName`, which take `string_view` — so no copy exists
   anywhere on the path and the move was already inert in spirit. Changing
   the constructor alone would trade the one baseline finding for two
   (`performance-move-const-arg` at `:122`,
   `performance-unnecessary-value-param` at `:103`); the end-to-end
   `const&` makes both impossible rather than suppressed. The sole caller
   (`camera_gateway_probe.cpp:434`) passes an lvalue and is unaffected.

That accounts for all 10 findings of the section 2.3 baseline, and item 4's
end-to-end form is what preserves the section 9 zero-findings gate.

### 8.1 The clang-tidy-20 delta — RESOLVED, and already applied

The four `performance-unnecessary-value-param` findings that only
clang-tidy 20 reports (section 2.3) are resolved as proposed: each
`.transform()` continuation now takes its `response` parameter by
`const auto&`.

| Site | Function | Edit |
|---|---|---|
| `vimbax_camera_gateway.cpp:302` | `FeatureEnumGet` | `[](auto response)` → `[](const auto& response)` |
| `vimbax_camera_gateway.cpp:321` | `FeatureEnumInfoGet` | as above |
| `vimbax_camera_gateway.cpp:349` | `FeaturesListGet` | as above |
| `vimbax_camera_gateway.cpp:358` | `CameraStatusGet` | as above |

The deciding argument is that `const auto&` is never worse. On the current
chains it costs nothing — `expected::transform` hands the continuation an
rvalue either way — and if a future refactor ever transforms an lvalue, the
by-reference form is the one that avoids a real `shared_ptr` copy. It also
unifies all ten `.transform()` lambdas in the file on a single parameter
form. The bodies are untouched: `shared_ptr` constness is shallow, so every
`std::move(response->field)` still moves.

The counter-argument was weighed rather than dismissed, and it is correct on
its own terms — because the chain is an rvalue the by-value parameter is
move-constructed, not copied, so the check overstated the cost and a
`NOLINT` trailer would have been defensible. What sank it is that the
by-value form had no advantage of its own to defend: not clearer, not
faster, not more general. Annotating would have meant carrying four
permanent suppressions to preserve nothing.

This edit is applied to the tree already, ahead of the rest of section 8;
the remainder lands with commit 1. Re-measured after it: the full 5.1
config under `clang-tidy-20` reports exactly the 10-finding section 2.3
baseline, 0 errors — the four lambda findings gone, nothing new introduced,
and the 18 and 20 finding sets now agree.

## 9. Verification

- `git ls-files '*.cpp'` piped to the chosen clang-tidy binary with
  `-p build` reports zero findings and zero errors after normalization.
- Repro check: the same run with `ExtraArgs` stripped still parses under
  clang-tidy-20 (section 7); still fails under 18 (confirming the workaround
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
- **`std::string_view` for the `camera_namespace` path**: considered while
  extending `const std::string&` through `Create()` (section 8 item 4) and
  deferred — an idiomatic further step, but a public-API style change beyond
  the check's ask.
