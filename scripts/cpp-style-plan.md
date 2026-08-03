# C++ Style Configuration Plan

| | |
|---|---|
| Status | Draft — one open decision (D6) blocks implementation |
| Scope | Root `.clang-format` policy file; C++ formatter settings in `scripts/ide.sh` |
| Date | 2026-08-02 |

This document is the source of truth for adding C++ style configuration to the
workspace. It records the investigated facts, the decisions already made, the
one decision still open, the exact artifacts to produce, and the rollout plan.

---

## 1. Background

The workspace has no C++ style configuration of any kind. There is no
`.clang-format`, `.clang-tidy`, `.clangd`, or `.editorconfig` in the repository
or in its git history on any branch; neither package declares ament lint hooks
(no `ament_lint_auto`, no `BUILD_TESTING` block); no user-global fallback
exists (`~/.clang-format` is absent); and the `.vscode/settings.json` written
by `scripts/ide.sh` contains only Python keys. The observed C++ style is a
purely human convention with zero automated enforcement.

The goal is to codify that convention so that VS Code formats C++ the way the
project is already written, with the policy expressed in one reviewable file
that also works outside VS Code (CLI `clang-format`, CI, other editors).

**Ground truth**: `src/venimapping_camera/src/vimbax_camera_gateway.cpp` was
manually cleaned to the intended style and is the reference for every style
question. Where files disagree, that file wins.

## 2. The project style

### 2.1 Empirical basis

The style was characterized by running `clang-format 18.1.3` over all seven
C++ files (1,301 tracked lines) with candidate configurations and counting
changed diff lines against the originals:

| Base style (stock) | Diff lines |
|---|---:|
| Google | 331 |
| Chromium | 359 |
| LLVM | 454 |
| Mozilla / GNU / WebKit / Microsoft | 808–1,862 |

Google is decisively the base. With line-wrapping neutralized
(`ColumnLimit: 0`), Google plus a single brace override reproduces the tree
almost exactly — the residual is five function braces (section 2.3). The code
is hand-formatted, but by an author whose internalized style is nearly
clang-format-Google output.

### 2.2 Conventions

Deltas from stock Google:

- **Out-of-line function definitions take Allman (own-line) braces.** All
  other braces — classes, structs, enums, namespaces, control flow, lambdas —
  stay attached, including `} else {` and `} catch (...) {`.
- **`PointerAlignment: Left`** (`const std::string& name`, `char** argv`),
  uniformly west-const.
- **100-column ceiling** (nothing exceeds it except one unbreakable `#error`
  string); banner comments target 80.
- **One parameter/argument per line when a call or signature wraps** (no
  bin-packing). This is the ground-truth convention; see section 2.3.
- **Include groups are semantic and hand-ordered**: own header first, then
  C++ standard library in angle brackets, then ROS/third-party in quotes,
  then project headers in quotes; blank-line separated, alphabetical within
  each group (`IncludeBlocks: Preserve`, not Google's `Regroup`).
- Every `if` body is braced; no unbraced single-statement bodies exist.

Conventions matching Google that the config restates for self-documentation:
2-space indent, no tabs, 4-space continuation, ` public:` at offset -1,
non-indented namespaces with `}  // namespace x` closers, constructor
initializers `: member{...}` at +4 with colon leading, break after binary
operators, break before ternary operators, two spaces before trailing
comments, one blank line maximum, short inline-only single-line functions.

Non-clang-format conventions worth recording:

| Area | Convention |
|---|---|
| Types, functions | `PascalCase`; trivial accessors `lower_case` (Google-sanctioned) |
| Locals, params, public struct members | `snake_case` |
| Private data members | `snake_case_` |
| Enumerators | `kPascalCase` (`GatewayDiagnostic`); `ErrorDomain` uses bare lowercase — a known inconsistency |
| Headers | `.hpp`, `#pragma once` (no include guards) |
| Comments | `//` only; no Doxygen; prose blocks above declarations; 80-column file banners |
| Aliases | `using` only, never `typedef` |

### 2.3 Known inconsistencies

1. **In-class attached braces (inexpressible in clang-format).** Five in-class
   member function definitions use attached braces while out-of-line
   definitions use Allman: `expected.hpp:38` (`FromDriver`), `expected.hpp:46`
   (`FromGateway`), `camera_gateway_probe.cpp:49/:53/:58`
   (`Pass`/`Fail`/`Skip`). `BraceWrapping.AfterFunction` cannot distinguish
   in-class from out-of-line, so any config re-braces these five sites to
   Allman on first format. This is accepted: Allman-for-definitions is the
   dominant convention; one-line inline accessors are unaffected
   (`AllowShortFunctionsOnASingleLine: Inline`).
2. **`camera_gateway_probe.cpp` predates the settled style.** It is formatted
   to ~80 columns with bin-packed parameters (the older habit); the newer
   files are 100-column with one-parameter-per-line. The file declares itself
   temporary/disposable. Normalization will rewrap it; that churn is accepted.

### 2.4 Relationship to ROS 2 / ament style

The project style is Google-derived but is **not** the ament/ROS 2 formatter
style, and deliberately does not adopt it:

| Dimension | This project | ament_clang_format (Jazzy) |
|---|---|---|
| Class/struct/enum/namespace braces | attached | Allman |
| Pointer alignment | `Left` | `Middle` |
| Access modifier offset | -1 | -2 |
| Continuation indent | 4 | 2 |
| Wrapped arguments | align / one-per-line | `AlwaysBreak` |

Shared ground: Google base, 100 columns, 2-space indent, Allman function
braces, attached control-flow braces. Since the packages run no ament lint
hooks, there is no CI that conflicts with the project config. (Upstream
context: ROS 2 core gates on uncrustify, not clang-format, and the two ament
configs are known to be mutually unsatisfiable — ament_lint issue #146 — so
ament's `.clang-format` is not authoritative even upstream.)

## 3. Environment constraints

These facts shape the design and must hold for the artifacts to work:

- **Editor stack is cpptools, not clangd.** `ms-vscode.cpptools 1.32.2` is
  installed; clangd and the clangd extension are not. Formatting flows through
  `C_Cpp.*` settings. A `.clangd` file would be inert.
- **clang-format binary resolution.** With `C_Cpp.clang_format_path` unset,
  cpptools uses the newer of PATH clang-format (18.1.3) and its own bundled
  binary — in practice the bundled one. Two consequences:
  - A `.clang-format` containing a key unknown to the active binary makes
    formatting **fail silently** in cpptools. The policy file must use only
    long-stable keys (everything in section 5.1 parses on clang-format ≥ 14).
  - Minor output drift between clang-format majors is possible. Mitigation in
    section 8.
- **User-level VS Code settings** (`~/.config/Code/User/settings.json`) set
  `editor.tabSize: 4` with `editor.detectIndentation: false` — the one real
  conflict; the `[cpp]` block must override both. Also relevant:
  `files.autoSave: "onFocusChange"` means format-on-save fires on focus
  change; `editor.rulers: [100]`, trim-trailing-whitespace, and
  insert-final-newline are already set and agree with the style. No `C_Cpp.*`
  or `[cpp]` keys exist at user level.
- **Git layout.** `.vscode/` is gitignored (settings are per-machine); a root
  `.clang-format` is tracked (policy is shared). clang-format discovers the
  nearest config upward from each source file, so the repo root covers all of
  `src/`.
- **ide.sh contracts.** Every artifact ide.sh writes is regenerated
  byte-identically and lives in a gitignored path; `settings.json` is created
  only when absent and never edited afterward. Both contracts are preserved.

## 4. Decisions

- **D1 — Codify the project's own style, not ament's.** Least churn, matches
  the ground-truth file, and no CI conflict exists. Adopting ament style would
  restructure every file.
- **D2 — `.clang-format` lives at the repo root and is checked into git.**
  It is durable source policy: authored once, changed only through reviewed
  commits, working before any build and outside VS Code. **ide.sh never
  generates or touches it.** This keeps the invariant that everything ide.sh
  writes is gitignored and disposable.
- **D3 — ide.sh wires the editor, nothing more.** The C++ formatter keys are
  added to the settings document that `ide_write_settings()` produces for a
  **fresh** `settings.json` only. The never-edit contract for an existing
  file stands; the existence probe and warning are extended (section 6).
- **D4 — `BinPackParameters/BinPackArguments: false`.** Matches the
  ground-truth one-per-line convention. Note: at `ColumnLimit: 100` this still
  cannot preserve every hand-split signature (clang-format joins parameters
  that all fit on one continuation line); at `ColumnLimit: 0` it actively
  normalizes the probe file's legacy packed calls. Both effects are intended.
- **D5 — Defer** `.clang-tidy` (static analysis, needs a curated check set,
  separately reviewed), `.editorconfig` (unneeded and can flip cpptools'
  engine selection), `.clangd` (different language server, separate
  decision), ament lint enforcement (needs a pinned clang-format major and a
  clean baseline first), and `.vscode/extensions.json` (optional nicety,
  interacts with the `.vscode/` ownership model).
- **D6 — OPEN: `ColumnLimit: 100` versus `ColumnLimit: 0`.** See below.

### D6: the column-limit decision

Measured with clang-format 18.1.3 against the current tree (diff lines,
section 5.1 config except where noted):

| Configuration | Ground-truth file | All 7 files |
|---|---:|---:|
| Section 5.1 config, `ColumnLimit: 100`, Google bin-packing | 147 | 402 |
| Section 5.1 config, `ColumnLimit: 100` | 132 | 378 |
| Section 5.1 config, `ColumnLimit: 0` | **0** | **81** |

- **`ColumnLimit: 100` — full enforcement.** The formatter owns wrapping:
  it joins any hand-broken line that fits under 100 and re-wraps to its own
  preference. That erases the ground-truth file's discretionary semantic
  breaks (one-per-line `Create(...)` parameters, per-argument
  `std::unexpected(GatewayError(...))` layouts, the per-client constructor
  initializer structure) — ~132 lines of the reference file rewritten at
  normalization and overridden on every save thereafter.
- **`ColumnLimit: 0` — structural enforcement, author-owned wrapping.** The
  formatter normalizes braces, indentation, pointer alignment, spacing, and
  include order but respects existing line breaks. The ground-truth file is
  reproduced **byte-identically**; the total normalization diff is 81 lines
  (five in-class braces plus probe-file unpacking). The trade: nothing
  automatically wraps an over-long line — the 100 limit is held by the
  `[cpp]` ruler and review discipline, which is how the tree was written
  (nothing exceeds 100 today).

**Recommendation: `ColumnLimit: 0`.** The ground-truth file is the style, and
its wrapping choices are part of it; the config that reproduces it exactly is
the config that codifies it. Format-on-save becomes non-destructive. If hard
enforcement is later wanted, flipping the one key (plus a one-time rewrap
commit) upgrades the policy.

## 5. Artifacts

### 5.1 `.clang-format` (repo root, committed)

```yaml
---
Language: Cpp
BasedOnStyle: Google

ColumnLimit: 0          # D6 pending; 100 if full enforcement is chosen
IndentWidth: 2
TabWidth: 2
UseTab: Never
ContinuationIndentWidth: 4

AccessModifierOffset: -1

DerivePointerAlignment: false
PointerAlignment: Left
ReferenceAlignment: Pointer

BreakBeforeBraces: Custom
BraceWrapping:
  AfterClass: false
  AfterControlStatement: Never
  AfterEnum: false
  AfterFunction: true
  AfterNamespace: false
  AfterStruct: false
  BeforeCatch: false
  BeforeElse: false
  SplitEmptyFunction: true

AllowShortFunctionsOnASingleLine: Inline

BinPackParameters: false
BinPackArguments: false

IncludeBlocks: Preserve
SortIncludes: CaseSensitive

ReflowComments: false
...
```

Notes:

- Several keys restate Google defaults deliberately: they document the policy
  and insulate it from Google-preset drift across clang-format majors.
- `ReflowComments: false` protects hand-wrapped prose comments and the
  80-column banners.
- `KeepEmptyLinesAtTheStartOfBlocks` is intentionally absent: clang-format 18
  preserves the blank line after `namespace x {` without it (verified).
- `Standard` is left at Google's `Auto`; the code's C++23 constructs are
  detected correctly.
- Every key parses on clang-format ≥ 14, satisfying the unknown-key
  constraint in section 3.

### 5.2 `.vscode/settings.json` (generated by ide.sh when absent)

```json
{
    "C_Cpp.formatting": "clangFormat",
    "C_Cpp.clang_format_style": "file",
    "C_Cpp.clang_format_fallbackStyle": "none",
    "[cpp]": {
        "editor.defaultFormatter": "ms-vscode.cpptools",
        "editor.detectIndentation": false,
        "editor.formatOnSave": true,
        "editor.insertSpaces": true,
        "editor.rulers": [100],
        "editor.tabSize": 2
    },
    "python.defaultInterpreterPath": "/usr/bin/python3",
    "python.envFile": "${workspaceFolder}/.vscode/ros.env"
}
```

Key purposes:

- `C_Cpp.formatting: "clangFormat"` pins the engine; the default (`"default"`)
  can silently switch to the vcFormat engine when an `.editorconfig` sits
  nearer the source than the `.clang-format`.
- `C_Cpp.clang_format_style: "file"` is the extension default, restated so a
  future user-level override cannot change project behavior.
- `C_Cpp.clang_format_fallbackStyle: "none"` fails loudly if the policy file
  is missing instead of silently formatting to Visual Studio style.
- `[cpp].editor.defaultFormatter` keeps cpptools authoritative if another
  formatter extension is ever installed.
- `[cpp].editor.tabSize/insertSpaces/detectIndentation` override the
  user-level 4-space configuration while typing; the ruler mirrors the
  100-column ceiling (visual only — the limit itself is policy/review).
- `C_Cpp.clang_format_path` is deliberately not set (machine-scoped, and the
  bundled binary is fine for this key set); see section 8 for the drift
  contingency that would introduce it.

## 6. `scripts/ide.sh` changes

All changes are confined to `ide_write_settings()` plus its messages. No new
artifact, no new preflight requirement (the script itself never runs
clang-format; VS Code bundles its own), no change to the summary line fields.

1. **Fresh-file document**: extend the Python generator's `doc` to the full
   section 5.2 content. Key order is insertion order; keep C++ keys first,
   Python keys last, matching 5.2.
2. **Existence probe**: the current probe greps for the two Python keys. Add
   the two C++ markers `"C_Cpp.formatting"` and `"editor.defaultFormatter"`.
   All four present → the existing "already configures ... left untouched"
   info path. Any missing → warn path.
3. **Warn path**: keep the never-edit stance; name the missing keys and offer
   the regeneration route:

   ```text
   [venimapping] WARN: .vscode/settings.json exists; this script never edits it --
   [venimapping] WARN: missing keys: C_Cpp.formatting editor.defaultFormatter
   [venimapping] WARN: merge the block from scripts/cpp-style-plan.md section 5.2,
   [venimapping] WARN: or delete the file and rerun scripts/ide.sh to regenerate it
   ```

   The function still returns 0 in this path: preserving a user-owned file is
   intentional, not a failure.
4. **Success message**: reflect the new scope, e.g.
   `wrote .vscode/settings.json (C++ format-on-save; interpreter /usr/bin/python3)`.
5. **Policy-file check (warn-only)**: if `${VENIMAPPING_WS}/.clang-format`
   is absent, warn that VS Code C++ formatting will error until it is
   committed (a consequence of `fallbackStyle: "none"`). Non-fatal, does not
   affect the summary.

## 7. Normalization

Before format-on-save is enabled, the tracked C++ is normalized once so the
baseline is clean and later diffs stay semantic:

```bash
git ls-files '*.cpp' '*.hpp' | xargs /usr/bin/clang-format -i
```

Expected impact under the recommended (`ColumnLimit: 0`) config: 81 diff
lines total — the five in-class function braces move to Allman
(`expected.hpp`, `camera_gateway_probe.cpp`) and the probe file's legacy
packed parameters unpack to one-per-line. `vimbax_camera_gateway.cpp`,
`camera_gateway.hpp`, `gateway_util.hpp`, and `gateway_util.cpp` are
unchanged or nearly so. Under `ColumnLimit: 100` the diff is ~378 lines,
including ~132 in the ground-truth file.

## 8. Verification

- `git ls-files '*.cpp' '*.hpp' | xargs clang-format --dry-run -Werror`
  exits 0 after normalization (the enforcement gate; also suitable for CI
  later).
- In VS Code, Format Document on `vimbax_camera_gateway.cpp` produces no
  edits. This also cross-checks the bundled clang-format against the system
  18.1.3 used for normalization; if version drift ever produces edits here,
  set `"C_Cpp.clang_format_path": "/usr/bin/clang-format"` in the generated
  settings and renormalize — that is the designated contingency, not a
  default.
- Delete `.vscode/settings.json`, rerun `scripts/ide.sh`, confirm the file
  matches section 5.2 and a second run reports "left untouched". Restore a
  Python-keys-only file, rerun, confirm the warn path fires and the run still
  reports `settings=ok`.
- Repeated `scripts/ide.sh` runs remain byte-identical across all artifacts.
- `shellcheck scripts/ide.sh` stays clean.

## 9. Rollout

Three commits after this document, in order:

1. `style(camera): add .clang-format and normalize C++ sources` — the root
   policy file (D6 resolved) plus the section 7 normalization, together, so
   the tree is compliant the moment the policy exists.
2. `feat(scripts): generate C++ formatter settings in ide.sh` — the section 6
   changes.
3. Local migration (no commit): this machine's existing `settings.json`
   contains only the two Python keys and no personal customization — delete
   it and rerun `scripts/ide.sh`.

## 10. Deferred work

- **`.clang-tidy`**: naming enforcement (would catch the `ErrorDomain`
  enumerator inconsistency), modern-C++ and bug-prone checks. Needs a curated
  check set and a noise review against rclcpp-heavy code first; cpptools
  auto-discovers the file once added, and enabling is one workspace setting.
- **Include completeness**: several headers rely on transitive standard
  library includes (deliberate, per history). A formatter cannot address
  this; an include-cleaner pass is a separate lint task and must not be
  enabled implicitly.
- **CI enforcement**: the `--dry-run -Werror` gate from section 8, or
  `ament_cmake_clang_format` pointed at the root config via `CONFIG_FILE`
  (it does not auto-discover). Requires pinning a clang-format major.
- **Python style**: out of scope here; the workspace has ruff installed and
  user-level defaults that do not conflict with anything above.
