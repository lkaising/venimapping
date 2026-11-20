# ------------------------------------------------------------------------------
#  Filename: audit_includes.py
#
#  Purpose:  Finds direct C++ includes that can be removed together and verifies the set.
#
#  Usage:    Run through scripts/audit-includes.sh, which prepares the scratch copy.
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import threading
import traceback

# --- Configuration ------------------------------------------------------------

AUDIT_SCOPE = "src"
HEADER_SUFFIXES = (".h", ".hh", ".hpp", ".hxx")
SOURCE_SUFFIXES = (".cc", ".cpp", ".cxx")
COLCON_DEFAULTS = os.path.join(".devcontainer", "colcon-defaults.yaml")
BUILD_COMMAND = ["colcon", "build", "--symlink-install"]

# One syntax check of an rclcpp translation unit peaks near 1 GiB.
COMPILE_MEMORY = 5 << 28

CONSUMER_PREFIX = "include_audit_consumer."
CONSUMER_PROBE = """\
cmake_language(DEFER DIRECTORY "${CMAKE_SOURCE_DIR}" CALL include_audit_add_consumers)

function(include_audit_targets dir out)
  get_property(targets DIRECTORY "${dir}" PROPERTY BUILDSYSTEM_TARGETS)
  get_property(subdirs DIRECTORY "${dir}" PROPERTY SUBDIRECTORIES)
  foreach(subdir IN LISTS subdirs)
    include_audit_targets("${subdir}" nested)
    list(APPEND targets ${nested})
  endforeach()
  set(${out} "${targets}" PARENT_SCOPE)
endfunction()

function(include_audit_add_consumers)
  include_audit_targets("${CMAKE_SOURCE_DIR}" targets)
  foreach(target IN LISTS targets)
    get_target_property(type ${target} TYPE)
    if(type MATCHES "^(STATIC|SHARED|MODULE|OBJECT|INTERFACE)_LIBRARY$")
      add_library(include_audit_consumer.${target} OBJECT "${INCLUDE_AUDIT_TU}")
      target_link_libraries(include_audit_consumer.${target} PRIVATE ${target})
    endif()
  endforeach()
endfunction()
"""

# --- Diagnostics --------------------------------------------------------------


class StageError(Exception):
    def __init__(self, stage: str, message: str, detail: str = ""):
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.detail = detail


def say(message: str) -> None:
    print(f"[venimapping] {message}", flush=True)


def step(message: str) -> None:
    print(f"\n[venimapping] ==> {message}", flush=True)


def read_text(path: str) -> str:
    with open(path, encoding="utf-8", errors="surrogateescape", newline="") as handle:
        return handle.read()


def write_text(path: str, text: str) -> None:
    with open(
        path, "w", encoding="utf-8", errors="surrogateescape", newline=""
    ) as handle:
        handle.write(text)


def under(path: str, directory: str) -> bool:
    return path == directory or path.startswith(directory.rstrip(os.sep) + os.sep)


def tail(text: str, count: int = 40) -> str:
    return "\n".join(text.rstrip("\n").splitlines()[-count:])


# --- Directive scanning -------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Directive:
    path: str
    line: int
    last: int
    text: str
    spelled: str | None
    include_next: bool
    conditions: tuple[str, ...]
    pragma: str | None
    editable: bool

    @property
    def key(self) -> tuple[str, int]:
        return (self.path, self.line)


DIRECTIVE_RE = re.compile(r"\s*#\s*([A-Za-z_]\w*)(.*)\Z", re.DOTALL)
HEADER_NAME_RE = re.compile(r'\s*(<[^<>]+>|"[^"]+")\s*\Z')
RAW_STRING_RE = re.compile(r'(?:u8|u|U|L)?R"([^ ()\\\t\v\f]{0,16})\(')
IWYU_RE = re.compile(r"IWYU\s+pragma:\s*(keep|export|begin_exports|end_exports)\b")
OPENERS = ("if", "ifdef", "ifndef")
BRANCHES = ("elif", "elifdef", "elifndef", "else")


def strip_comments(line: str, in_block: bool, raw_end: str | None):
    """Blank comments and raw string bodies in one logical line; return the new state."""
    out: list[str] = []
    quote = None
    i, n = 0, len(line)
    while i < n:
        if raw_end is not None:
            end = line.find(raw_end, i)
            stop = n if end < 0 else end + len(raw_end)
            out.append(" " * (stop - i))
            i = stop
            raw_end = None if end >= 0 else raw_end
            continue
        if in_block:
            end = line.find("*/", i)
            stop = n if end < 0 else end + 2
            out.append(" " * (stop - i))
            i = stop
            in_block = end < 0
            continue
        char = line[i]
        if quote:
            if char == "\\":
                out.append(line[i : i + 2])
                i += 2
                continue
            if char == quote:
                quote = None
            out.append(char)
            i += 1
            continue
        if line.startswith("//", i):
            out.append(" " * (n - i))
            break
        if line.startswith("/*", i):
            out.append("  ")
            i += 2
            in_block = True
            continue
        raw = RAW_STRING_RE.match(line, i)
        if raw and (i == 0 or not (line[i - 1].isalnum() or line[i - 1] == "_")):
            out.append(" " * (raw.end() - i))
            i = raw.end()
            raw_end = ")" + raw.group(1) + '"'
            continue
        if char == '"' or (char == "'" and not (i and line[i - 1].isalnum())):
            quote = char
        out.append(char)
        i += 1
    return "".join(out), in_block, raw_end


def include_guard(items: list[tuple]) -> int | None:
    """Index of the #ifndef that wraps the whole file as an include guard."""
    if len(items) < 3 or items[0][0] != "ifndef" or items[1][0] != "define":
        return None
    macro = items[0][1].split()[:1]
    if not macro or items[1][1].split()[:1] != macro:
        return None
    depth = 0
    for index, item in enumerate(items):
        word = item[0]
        if word in OPENERS:
            depth += 1
        elif word in BRANCHES and depth == 1:
            return None
        elif word == "endif":
            depth -= 1
            if depth == 0:
                return 0 if index == len(items) - 1 else None
    return None


def scan_directives(rel_path: str, text: str) -> list[Directive]:
    physical = text.split("\n")
    exported: set[int] = set()
    exporting = False
    for number, raw in enumerate(physical, 1):
        pragma = IWYU_RE.search(raw)
        if pragma and pragma.group(1) == "begin_exports":
            exporting = True
        elif pragma and pragma.group(1) == "end_exports":
            exporting = False
        elif exporting:
            exported.add(number)

    items = []
    in_block, raw_end = False, None
    i = 0
    while i < len(physical):
        first = i
        logical = physical[i].rstrip("\r")
        while logical.endswith("\\") and i + 1 < len(physical):
            i += 1
            logical = logical[:-1] + physical[i].rstrip("\r")
        hidden_start = in_block
        raw_start = raw_end is not None
        code, in_block, raw_end = strip_comments(logical, in_block, raw_end)
        match = DIRECTIVE_RE.match(code)
        if match and not raw_start:
            editable = not hidden_start and not in_block and raw_end is None
            items.append(
                (match.group(1), match.group(2).strip(), first + 1, i + 1, editable)
            )
        i += 1

    guard = include_guard(items)
    frames: list[str | None] = []
    directives = []
    for index, (word, args, first, last, editable) in enumerate(items):
        where = f"#{word} {args}".rstrip() + f" (line {first})"
        if word in OPENERS:
            frames.append(None if index == guard else where)
        elif word in BRANCHES and frames:
            frames[-1] = where
        elif word == "endif" and frames:
            frames.pop()
        elif word in ("include", "include_next"):
            name = HEADER_NAME_RE.match(args)
            pragma = IWYU_RE.search("\n".join(physical[first - 1 : last]))
            kind = (
                pragma.group(1)
                if pragma and pragma.group(1) in ("keep", "export")
                else None
            )
            if kind is None and first in exported:
                kind = "export"
            directives.append(
                Directive(
                    path=rel_path,
                    line=first,
                    last=last,
                    text=physical[first - 1].rstrip(),
                    spelled=name.group(1) if name else None,
                    include_next=word == "include_next",
                    conditions=tuple(frame for frame in frames if frame),
                    pragma=kind,
                    editable=editable,
                )
            )
    return directives


def blank(lines: list[str], directives) -> list[str]:
    """Empty the directive lines so every later line keeps its original number."""
    result = list(lines)
    for directive in directives:
        for number in range(directive.line, directive.last + 1):
            result[number - 1] = "\r" if result[number - 1].endswith("\r") else ""
    return result


# --- Compiler traces ----------------------------------------------------------

MARKER_RE = re.compile(r'# (\d+) "((?:[^"\\]|\\.)*)"((?: \d)*)\Z')
INCLUDE_LINE_RE = re.compile(r"#(include_next|include)\s+(.*)")


@dataclasses.dataclass
class Trace:
    """One preprocessor run: first entry of each file, every processed include, search dirs."""

    parent: dict[str, str | None]
    spelled: dict[str, str | None]
    directives: list[tuple[str | None, int, str, str | None]]
    quote_dirs: list[str]
    angle_dirs: list[str]


def search_dirs(stderr: str) -> tuple[list[str], list[str]]:
    quote: list[str] = []
    angle: list[str] = []
    current = None
    for line in stderr.splitlines():
        if line.startswith('#include "..." search starts here'):
            current = quote
        elif line.startswith("#include <...> search starts here"):
            current = angle
        elif line.startswith("End of search list"):
            current = None
        elif current is not None and line.startswith(" "):
            current.append(os.path.normpath(line.strip().split(" (")[0]))
    return quote, angle


def resolve(includer: str | None, spelled: str, quote: list[str], angle: list[str]):
    if len(spelled) < 3 or spelled[0] + spelled[-1] not in ('""', "<>"):
        return None
    dirs = angle
    if spelled[0] == '"':
        local = [os.path.dirname(includer)] if includer and includer[0] != "<" else []
        dirs = local + quote + angle
    for directory in dirs:
        candidate = os.path.normpath(os.path.join(directory, spelled[1:-1]))
        if os.path.isfile(candidate):
            return candidate
    return None


def parse_trace(output_path: str, stderr: str, directory: str) -> Trace:
    quote, angle = search_dirs(stderr)
    trace = Trace({}, {}, [], quote, angle)
    current: str | None = None
    line = 0
    pending = None

    def settle(target):
        nonlocal pending
        if pending is not None:
            includer, number, spelled, is_next = pending
            if target is None and not is_next:
                target = resolve(includer, spelled, quote, angle)
            trace.directives.append((includer, number, spelled, target))
            pending = None

    with open(output_path, encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            raw = raw.rstrip("\n")
            marker = MARKER_RE.match(raw) if raw.startswith("# ") else None
            if marker:
                name = re.sub(r"\\(.)", r"\1", marker.group(2))
                if not name.startswith("<"):
                    name = os.path.normpath(os.path.join(directory, name))
                flags = marker.group(3).split()
                if "1" in flags:
                    spelled = pending[2] if pending and pending[0] == current else None
                    settle(name if spelled is not None else None)
                    if name not in trace.parent:
                        trace.parent[name] = current
                        trace.spelled[name] = spelled
                elif "2" in flags:
                    settle(None)
                elif current is None:
                    trace.parent[name] = None
                current, line = name, int(marker.group(1))
                continue
            include = INCLUDE_LINE_RE.match(raw)
            if include:
                settle(None)
                pending = (
                    current,
                    line,
                    include.group(2).strip(),
                    include.group(1) != "include",
                )
            elif raw.strip():
                settle(None)
            line += 1
    settle(None)
    return trace


# --- Checks -------------------------------------------------------------------


@dataclasses.dataclass
class Check:
    subject: str
    label: str
    directory: str
    flags: list[str]
    source: str | None
    env: str
    target: str = ""
    public: bool = False


@dataclasses.dataclass
class Outcome:
    ok: bool
    error: str
    output: str
    trace: Trace | None


@dataclasses.dataclass
class Tree:
    root: str
    tu_dir: str


DROP_WITH_VALUE = {"-o", "-MF", "-MT", "-MQ"}
DROP = {"-c", "-MD", "-MMD", "-MP"}


def compile_flags(entry: dict) -> list[str]:
    """Compile DB arguments without the input, the output and dependency-file options."""
    args = entry["arguments"] if "arguments" in entry else shlex.split(entry["command"])
    source = os.path.normpath(os.path.join(entry["directory"], entry["file"]))
    flags: list[str] = []
    skip = False
    for arg in args:
        if skip:
            skip = False
        elif arg in DROP_WITH_VALUE:
            skip = True
        elif (
            arg not in DROP
            and os.path.normpath(os.path.join(entry["directory"], arg)) != source
        ):
            flags.append(arg)
    return flags


def first_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    for line in lines:
        if "error:" in line:
            return line
    return lines[-1] if lines else "the compiler failed without a message"


class Compiler:
    def __init__(self, workspace: str, jobs: int):
        self.workspace = workspace
        self.jobs = jobs
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=jobs)
        self.count = 0
        self._lock = threading.Lock()

    def submit(self, check: Check, tree: Tree, mode: str):
        return self.pool.submit(self._run, check, tree, mode)

    def _run(self, check: Check, tree: Tree, mode: str) -> Outcome:
        with self._lock:
            self.count += 1
            number = self.count
        old = os.path.join(self.workspace, AUDIT_SCOPE) + os.sep
        new = os.path.join(tree.root, AUDIT_SCOPE) + os.sep
        flags = [arg.replace(old, new) for arg in check.flags]
        if check.source:
            source = check.source.replace(old, new)
        else:
            source = os.path.join(tree.tu_dir, f"{number}.cpp")
            write_text(source, f'#include "{os.path.join(tree.root, check.subject)}"\n')
        output = os.path.join(tree.tu_dir, f"{number}.ii")
        if mode == "trace":
            command = flags + ["-E", "-dI", "-v", source, "-o", output]
        else:
            command = flags + ["-fsyntax-only", source]
        proc = subprocess.run(
            command,
            check=False,
            cwd=check.directory,
            capture_output=True,
            text=True,
            errors="replace",
        )
        trace = None
        if proc.returncode == 0 and mode == "trace":
            trace = parse_trace(output, proc.stderr, check.directory)
        if os.path.exists(output):
            os.remove(output)
        text = proc.stderr
        if mode == "trace":
            text = "\n".join(line for line in text.splitlines() if "error" in line)
        replacements = [(tree.root + os.sep, ""), (self.workspace + os.sep, "")]
        if check.source is None:
            replacements.insert(0, (source, "<standalone TU>"))
        for path, name in replacements:
            text = text.replace(path, name)
        return Outcome(proc.returncode == 0, first_error(text), tail(text, 25), trace)


def merge(results: dict[str, Outcome]) -> Outcome:
    failed = [
        results[mode]
        for mode in ("syntax", "trace")
        if mode in results and not results[mode].ok
    ]
    trace = results["trace"].trace if "trace" in results else None
    if failed:
        return Outcome(False, failed[0].error, failed[0].output, trace)
    return Outcome(True, "", "", trace)


# --- Trials -------------------------------------------------------------------


class Audit:
    """Bottom-up removal trials over the project C++ files of a scratch workspace."""

    def __init__(self, workspace: str, audit_dir: str, jobs: int):
        self.workspace = workspace
        self.src = os.path.join(workspace, AUDIT_SCOPE)
        self.audit_dir = audit_dir
        self.compiler = Compiler(workspace, jobs)
        self.canonical = Tree(workspace, os.path.join(audit_dir, "tu"))
        os.makedirs(self.canonical.tu_dir, exist_ok=True)
        self.files: list[str] = []
        self.lines: dict[str, list[str]] = {}
        self.directives: dict[str, list[Directive]] = {}
        for root, _, names in os.walk(self.src):
            for name in names:
                if name.endswith(HEADER_SUFFIXES + SOURCE_SUFFIXES):
                    rel = os.path.relpath(os.path.join(root, name), workspace)
                    text = read_text(os.path.join(workspace, rel))
                    self.files.append(rel)
                    self.lines[rel] = text.split("\n")
                    self.directives[rel] = scan_directives(rel, text)
        self.files.sort()
        self.checks: list[Check] = []
        self.baseline: dict[int, Outcome] = {}
        self.final: dict[int, Outcome] = {}
        self.deps: dict[int, set[str]] = {}
        self.active: set[tuple[str, int]] = set()
        self.targets: dict[tuple[str, int], str] = {}
        self.removed: list[Directive] = []
        self.kept: dict[tuple[str, int], str] = {}
        self.not_tried: dict[tuple[str, int], str] = {}
        self.trials = 0
        self.trees = 0

    def rel(self, path: str | None) -> str | None:
        if path and under(path, self.src):
            rel = os.path.relpath(path, self.workspace)
            return rel if rel in self.lines else None
        return None

    def run(self, indices, modes=("trace", "syntax")) -> dict[int, Outcome]:
        futures = {
            index: {
                mode: self.compiler.submit(self.checks[index], self.canonical, mode)
                for mode in modes
            }
            for index in indices
        }
        return {
            index: merge({mode: future.result() for mode, future in item.items()})
            for index, item in futures.items()
        }

    def record_baseline(self, outcomes: dict[int, Outcome]) -> None:
        for index, outcome in outcomes.items():
            self.baseline[index] = outcome
            if outcome.trace is None:
                continue
            self.deps[index] = {
                rel for rel in map(self.rel, outcome.trace.parent) if rel
            }
            for includer, number, _, target in outcome.trace.directives:
                rel = self.rel(includer)
                if rel:
                    self.active.add((rel, number))
                    if target and (rel, number) not in self.targets:
                        self.targets[(rel, number)] = target

    def classify(self) -> dict[str, list[Directive]]:
        covered = set().union(*self.deps.values()) if self.deps else set()
        candidates: dict[str, list[Directive]] = {}
        for rel in self.files:
            for directive in self.directives[rel]:
                reason = self.skip_reason(rel, directive, covered)
                if reason:
                    self.not_tried[directive.key] = reason
                else:
                    candidates.setdefault(rel, []).append(directive)
        return candidates

    def skip_reason(
        self, rel: str, directive: Directive, covered: set[str]
    ) -> str | None:
        if directive.spelled is None:
            return "Computed include. The audit cannot tell which header it names."
        if directive.include_next:
            return "#include_next depends on where the including file was found. Not tried."
        if rel not in covered:
            return "No check in this build compiles this file. Unverified."
        if directive.key not in self.active:
            where = directive.conditions[-1] if directive.conditions else None
            reason = f"inside {where}" if where else "the preprocessor never reached it"
            return f"No check processed this directive ({reason}). Unverified."
        target = self.targets.get(directive.key)
        if target is None:
            return "The audit could not resolve the header it names. Not tried."
        if directive.pragma:
            return f"Marked IWYU pragma: {directive.pragma}. Not tried."
        if rel.endswith(SOURCE_SUFFIXES) and self.rel(target):
            stem = os.path.splitext(os.path.basename(rel))[0]
            if os.path.splitext(os.path.basename(target))[0] == stem:
                return "Own declaration header of this source file. Not tried."
        if not directive.editable:
            return "Shares a line with a comment that spans lines. Not tried."
        return None

    def order(self) -> list[str]:
        """Leaves first: each file comes after every project file it includes."""
        edges: dict[str, set[str]] = {rel: set() for rel in self.files}
        for (rel, _), target in self.targets.items():
            included = self.rel(target)
            if included and included != rel:
                edges[rel].add(included)
        result = []
        while edges:
            ready = sorted(rel for rel, deps in edges.items() if not deps)
            pick = ready[0] if ready else min(edges)
            result.append(pick)
            del edges[pick]
            for deps in edges.values():
                deps.discard(pick)
        return result

    def affected(self, rel: str) -> list[Check]:
        """The file's own check first, so a failure names the most direct cause."""
        checks = [
            self.checks[i] for i, deps in sorted(self.deps.items()) if rel in deps
        ]
        return sorted(checks, key=lambda check: check.subject != rel)

    def make_tree(self, rel: str, removals: list[Directive]) -> Tree:
        """Trial copy of src/: symlinks to the accepted state, plus the edited file."""
        self.trees += 1
        root = os.path.join(self.audit_dir, "trees", str(self.trees))
        for current, dirs, names in os.walk(self.src):
            copy_dir = os.path.join(root, os.path.relpath(current, self.workspace))
            os.makedirs(copy_dir, exist_ok=True)
            linked = [
                name for name in dirs if os.path.islink(os.path.join(current, name))
            ]
            dirs[:] = [name for name in dirs if name not in linked]
            for name in names + linked:
                path = os.path.join(current, name)
                if os.path.relpath(path, self.workspace) != rel:
                    os.symlink(os.path.realpath(path), os.path.join(copy_dir, name))
        write_text(os.path.join(root, rel), "\n".join(blank(self.lines[rel], removals)))
        tu_dir = os.path.join(root, ".tu")
        os.makedirs(tu_dir)
        return Tree(root, tu_dir)

    def run_trials(self, rel: str, groups: list[list[Directive]], checks: list[Check]):
        """Compile each group of removals on top of the accepted state."""
        trees = [self.make_tree(rel, group) for group in groups]
        futures = [
            [self.compiler.submit(check, tree, "syntax") for check in checks]
            for tree in trees
        ]
        failures = []
        for group_futures in futures:
            failure = None
            for check, future in zip(checks, group_futures):
                outcome = future.result()
                if not outcome.ok and failure is None:
                    failure = f"Failed {describe(check, rel)}: {outcome.error}"
            failures.append(failure)
        for tree in trees:
            shutil.rmtree(tree.root)
        self.trials += len(groups)
        return failures

    def accept(self, rel: str, group: list[Directive]) -> None:
        self.lines[rel] = blank(self.lines[rel], group)
        write_text(os.path.join(self.workspace, rel), "\n".join(self.lines[rel]))
        self.removed.extend(group)

    def audit_file(self, rel: str, candidates: list[Directive]) -> None:
        checks = self.affected(rel)
        failures = self.run_trials(
            rel, [[directive] for directive in candidates], checks
        )
        passing = []
        for directive, failure in zip(candidates, failures):
            if failure:
                self.kept[directive.key] = failure
            else:
                passing.append(directive)
        if len(passing) == 1:
            self.accept(rel, passing)
        else:
            self.settle(rel, passing, checks)

    def settle(self, rel: str, group: list[Directive], checks: list[Check]) -> None:
        """Keep the group if it passes together, otherwise split it in halves."""
        if not group:
            return
        failure = self.run_trials(rel, [group], checks)[0]
        if failure is None:
            self.accept(rel, group)
        elif len(group) == 1:
            self.kept[group[0].key] = (
                "Passed alone, but failed with the removals accepted before it in this file. "
                + failure
            )
        else:
            middle = len(group) // 2
            self.settle(rel, group[:middle], checks)
            self.settle(rel, group[middle:], checks)

    def own_check(self, rel: str) -> int | None:
        for index, check in enumerate(self.checks):
            if check.subject == rel:
                return index
        return None

    def supply(self, directive: Directive) -> str:
        """What the final trace of the file's own check shows about the removed header."""
        target = self.targets[directive.key]
        outcome = self.final.get(self.own_check(directive.path))
        trace = outcome.trace if outcome else None
        if trace is None:
            return "No trace of this file's own check is available."
        if target not in trace.parent:
            return "No longer included in the file's own check. All checks pass without it."
        owner = os.path.join(self.workspace, directive.path)
        chain = [target]
        while trace.parent.get(chain[-1]) not in (owner, None):
            chain.append(trace.parent[chain[-1]])
        if trace.parent.get(chain[-1]) != owner:
            return "Still included, but not through this file's remaining includes."
        edges: dict[str, set[str]] = {}
        for includer, _, _, included in trace.directives:
            if includer and included:
                edges.setdefault(includer, set()).add(included)
        providers: dict[int, str] = {}
        for includer, number, spelled, included in trace.directives:
            if includer == owner and included and reaches(edges, included, target):
                providers.setdefault(number, spelled)
        if len(providers) > 1:
            listed = [providers[number] for number in sorted(providers)]
            shown = ", ".join(listed[:3])
            if len(listed) > 3:
                shown += f" and {len(listed) - 3} more"
            return f"Still included through {len(listed)} remaining includes: {shown}."
        names = [
            trace.spelled.get(path) or os.path.basename(path)
            for path in reversed(chain)
        ]
        text = f"Supplied by {names[0]}"
        if len(names) > 2:
            text += " through " + " -> ".join(names[1:-1])
        return text + "."


def describe(check: Check, rel: str) -> str:
    if check.subject == rel:
        return "its standalone check" if check.source is None else "its own compile"
    kind = "standalone check of" if check.source is None else "compile of"
    return f"{kind} {check.subject}"


def reaches(edges: dict[str, set[str]], start: str, goal: str) -> bool:
    stack, seen = [start], set()
    while stack:
        node = stack.pop()
        if node == goal:
            return True
        if node not in seen:
            seen.add(node)
            stack.extend(edges.get(node, ()))
    return False


# --- Workspace ----------------------------------------------------------------


@dataclasses.dataclass
class Env:
    name: str
    target: str
    public: bool
    directory: str
    flags: list[str]
    quote_dirs: list[str] = dataclasses.field(default_factory=list)
    angle_dirs: list[str] = dataclasses.field(default_factory=list)


def load_db(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def db_file(entry: dict) -> str:
    return os.path.normpath(os.path.join(entry["directory"], entry["file"]))


def db_key(entry: dict) -> tuple:
    args = entry["arguments"] if "arguments" in entry else shlex.split(entry["command"])
    return (entry["directory"], db_file(entry), tuple(args))


def db_target(entry: dict) -> str:
    output = entry.get("output", "")
    if not output:
        args = (
            entry["arguments"]
            if "arguments" in entry
            else shlex.split(entry["command"])
        )
        output = args[args.index("-o") + 1] if "-o" in args[:-1] else ""
    match = re.search(r"CMakeFiles/([^/]+)\.dir/", output)
    return match.group(1) if match else "unknown"


def cache_value(path: str, name: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            key, _, value = line.rstrip("\n").partition("=")
            if key.split(":")[0] == name:
                return value
    return ""


def fingerprint(root: str, rels: list[str]) -> dict[str, str]:
    hashes = {}
    for rel in rels:
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                hashes[rel] = hashlib.sha256(handle.read()).hexdigest()
    return hashes


def job_count() -> int:
    cpus = os.cpu_count() or 1
    try:
        with open("/proc/meminfo", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return max(
                        1, min(cpus, int(line.split()[1]) * 1024 // COMPILE_MEMORY)
                    )
    except OSError:
        pass
    return cpus


class Run:
    def __init__(self, args: argparse.Namespace):
        self.checkout = args.checkout
        self.workspace = args.workspace
        self.report = args.report
        self.started = args.started
        self.audit_dir = os.path.join(args.scratch, "audit")
        self.logs = os.path.join(self.audit_dir, "logs")
        os.makedirs(self.logs, exist_ok=True)
        self.env = dict(os.environ)
        self.env["COLCON_DEFAULTS_FILE"] = os.path.join(self.workspace, COLCON_DEFAULTS)
        self.stage = "setup"
        self.error: StageError | None = None
        self.interrupted = False
        self.verified = False
        self.begin = datetime.datetime.now().astimezone()
        self.facts: list[tuple[str, str]] = []
        self.snapshot: list[str] = []
        self.packages: list[str] = []
        self.envs: list[Env] = []
        self.header_checks: tuple[int, int] | None = None
        self.source_checks: tuple[int, int] | None = None
        self.build_result = "not run"
        self.changed_during_run: list[str] = []
        self.completed: list[str] = []
        self.snapshot_files = sorted(
            os.path.relpath(os.path.join(root, name), self.workspace)
            for root, _, names in os.walk(self.workspace)
            for name in names
        )
        self.hashes = fingerprint(self.workspace, self.snapshot_files)
        self.audit = Audit(self.workspace, self.audit_dir, job_count())

    def check_environment(self) -> None:
        for name, value in sorted(os.environ.items()):
            for piece in value.split(os.pathsep):
                if piece.startswith(os.sep) and under(
                    os.path.normpath(piece), self.checkout
                ):
                    raise StageError(
                        self.stage,
                        f"{name} points into the developer checkout: {piece}",
                    )
        for tool in ("colcon", "cmake", "git"):
            if shutil.which(tool) is None:
                raise StageError(self.stage, f"{tool} was not found on PATH")
        if not os.path.isfile(self.env["COLCON_DEFAULTS_FILE"]):
            raise StageError(self.stage, f"the snapshot has no {COLCON_DEFAULTS}")

    def git(self, *args: str) -> str | None:
        proc = subprocess.run(
            ["git", "-C", self.checkout, *args],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
        return proc.stdout.rstrip("\n") if proc.returncode == 0 else None

    def describe_snapshot(self) -> None:
        head = self.git("rev-parse", "--short", "HEAD") or "no commit"
        branch = self.git("symbolic-ref", "--short", "-q", "HEAD") or "detached HEAD"
        status = (
            self.git("status", "--porcelain=v1", "--untracked-files=all") or ""
        ).splitlines()
        changed = [line[3:] for line in status if line[:2] != "??"]
        untracked = [line[3:] for line in status if line[:2] == "??"]
        self.snapshot = [
            f"working tree of {self.checkout}",
            (
                f"HEAD {head} on {branch}, with {len(changed)} changed and "
                f"{len(untracked)} untracked files"
            ),
        ]
        listed = changed + untracked
        self.snapshot += [f"  {path}" for path in listed[:15]]
        if len(listed) > 15:
            self.snapshot.append(f"  and {len(listed) - 15} more")

    def build(self, name: str) -> None:
        log_path = os.path.join(self.logs, f"{name}-build.log")
        say("$ " + " ".join(BUILD_COMMAND))
        with open(log_path, "w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                BUILD_COMMAND,
                cwd=self.workspace,
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )
            for line in proc.stdout:
                log.write(line)
                print("  " + line, end="", flush=True)
            code = proc.wait()
        if code != 0:
            output = read_text(log_path).replace(self.workspace + os.sep, "")
            raise StageError(
                self.stage, f"colcon build exited with status {code}", tail(output, 60)
            )

    def search(self, env: Env) -> None:
        command = env.flags + ["-E", "-v", "-x", "c++", os.devnull, "-o", os.devnull]
        proc = subprocess.run(
            command,
            check=False,
            cwd=env.directory,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if proc.returncode != 0:
            raise StageError(
                self.stage,
                f"the compiler rejected the flags of {env.name}",
                tail(proc.stderr),
            )
        env.quote_dirs, env.angle_dirs = search_dirs(proc.stderr)

    def derive_envs(self) -> None:
        listing = subprocess.run(
            ["colcon", "list", "--names-only"],
            check=False,
            cwd=self.workspace,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.packages = sorted(listing.stdout.split())
        probe = os.path.join(self.audit_dir, "consumer_probe.cmake")
        probe_tu = os.path.join(self.audit_dir, "consumer_probe.cpp")
        write_text(probe, CONSUMER_PROBE)
        write_text(probe_tu, "\n")
        own: dict[str, list[dict]] = {}
        consumers: dict[str, dict] = {}
        for package in self.packages:
            build = os.path.join(self.workspace, "build", package)
            db_path = os.path.join(build, "compile_commands.json")
            if not os.path.isfile(db_path):
                continue
            before = sorted(db_key(entry) for entry in load_db(db_path))
            proc = subprocess.run(
                [
                    "cmake",
                    f"-DCMAKE_PROJECT_INCLUDE={probe}",
                    f"-DINCLUDE_AUDIT_TU={probe_tu}",
                    ".",
                ],
                check=False,
                cwd=build,
                env=self.env,
                capture_output=True,
                text=True,
                errors="replace",
            )
            if proc.returncode != 0:
                raise StageError(
                    self.stage,
                    f"CMake could not add the consumer probe to {package}",
                    tail(proc.stdout + proc.stderr),
                )
            after = load_db(db_path)
            real = [entry for entry in after if db_file(entry) != probe_tu]
            if sorted(db_key(entry) for entry in real) != before:
                raise StageError(
                    self.stage,
                    f"the consumer probe changed the compile commands of {package}",
                )
            for entry in real:
                own.setdefault(db_target(entry), []).append(entry)
            for entry in after:
                if db_file(entry) == probe_tu:
                    consumers[db_target(entry).removeprefix(CONSUMER_PREFIX)] = entry
            cache = os.path.join(build, "CMakeCache.txt")
            generator = cache_value(cache, "CMAKE_GENERATOR")
            build_type = cache_value(cache, "CMAKE_BUILD_TYPE") or "empty"
            self.facts.append(
                ("CMake", f"{package}: {generator}, CMAKE_BUILD_TYPE {build_type}")
            )
        if not own:
            raise StageError(
                self.stage,
                "the build produced no compile_commands.json",
                f"{COLCON_DEFAULTS} must pass -DCMAKE_EXPORT_COMPILE_COMMANDS=ON.",
            )
        for target, entry in sorted(consumers.items()):
            self.envs.append(
                Env(
                    f"consumer of {target}",
                    target,
                    True,
                    entry["directory"],
                    compile_flags(entry),
                )
            )
        for target, entries in sorted(own.items()):
            entry = min(entries, key=db_file)
            self.envs.append(
                Env(
                    f"target {target}",
                    target,
                    False,
                    entry["directory"],
                    compile_flags(entry),
                )
            )
        for future in [
            self.audit.compiler.pool.submit(self.search, env) for env in self.envs
        ]:
            future.result()
        for env in self.envs:
            for directory in env.quote_dirs + env.angle_dirs:
                if under(directory, self.checkout):
                    raise StageError(
                        self.stage,
                        f"{env.name} searches the developer checkout: {directory}",
                    )
        for target, entries in sorted(own.items()):
            for entry in sorted(entries, key=db_file):
                rel = self.audit.rel(db_file(entry))
                if rel and rel.endswith(SOURCE_SUFFIXES):
                    self.audit.checks.append(
                        Check(
                            rel,
                            rel,
                            entry["directory"],
                            compile_flags(entry),
                            db_file(entry),
                            f"target {target}",
                            target,
                        )
                    )
        compilers = sorted({env.flags[0] for env in self.envs})
        for compiler in compilers:
            version = subprocess.run(
                [compiler, "--version"], check=False, capture_output=True, text=True
            ).stdout
            real = os.path.realpath(compiler)
            name = compiler if real == compiler else f"{compiler} -> {real}"
            first = version.splitlines()[0] if version else "unknown version"
            self.facts.insert(0, ("Compiler", f"{name}\n{first}"))
        standards = sorted(
            {
                flag
                for env in self.envs
                for flag in env.flags
                if flag.startswith("-std=")
            }
        )
        self.facts.insert(
            len(compilers), ("Standard", ", ".join(standards) or "compiler default")
        )
        self.facts.append(
            (
                "Build",
                " ".join(BUILD_COMMAND) + f", COLCON_DEFAULTS_FILE {COLCON_DEFAULTS}",
            )
        )
        prefixes = [
            p for p in os.environ.get("COLCON_PREFIX_PATH", "").split(os.pathsep) if p
        ]
        self.facts.append(("Underlays", "\n".join(prefixes) or "none"))
        self.facts.append(("ROS_DISTRO", os.environ.get("ROS_DISTRO", "unset")))
        self.facts.append(("Packages", ", ".join(self.packages)))
        say(
            f"{len(self.envs)} compile environments, {len(self.audit.checks)} source checks"
        )

    def assign_headers(self) -> None:
        """Public headers get the narrowest consumer environment; private ones their target's."""
        audit = self.audit
        owners: dict[str, set[str]] = {}
        for index in audit.baseline:
            for rel in audit.deps.get(index, ()):
                owners.setdefault(rel, set()).add(audit.checks[index].target)
        public = sorted(
            (env for env in self.envs if env.public),
            key=lambda env: (len(env.quote_dirs) + len(env.angle_dirs), env.target),
        )
        private = {env.target: env for env in self.envs if not env.public}
        for rel in audit.files:
            if not rel.endswith(HEADER_SUFFIXES):
                continue
            path = os.path.join(self.workspace, rel)
            needed = [
                d.spelled
                for d in audit.directives[rel]
                if d.spelled and not d.conditions and not d.include_next
            ]
            options = [
                env
                for env in public
                if any(
                    under(path, d) and under(d, audit.src)
                    for d in env.quote_dirs + env.angle_dirs
                )
            ]
            options += [
                private[target]
                for target in sorted(owners.get(rel, ()))
                if target in private
            ]
            for env in options:
                if all(
                    resolve(path, name, env.quote_dirs, env.angle_dirs)
                    for name in needed
                ):
                    audit.checks.append(
                        Check(
                            rel,
                            f"standalone {rel}",
                            env.directory,
                            env.flags,
                            None,
                            env.name,
                            env.target,
                            env.public,
                        )
                    )
                    break

    def baseline_checks(self) -> None:
        audit = self.audit
        sources = list(range(len(audit.checks)))
        audit.record_baseline(audit.run(sources))
        self.assign_headers()
        headers = list(range(len(sources), len(audit.checks)))
        audit.record_baseline(audit.run(headers))
        for index, outcome in sorted(audit.baseline.items()):
            for path in outcome.trace.parent if outcome.trace else ():
                if path.startswith("<"):
                    continue
                label = audit.checks[index].label
                if under(path, self.checkout):
                    raise StageError(
                        self.stage, f"{label} read {path} from the developer checkout"
                    )
                real = os.path.realpath(path)
                if under(real, audit.src) and not under(path, audit.src):
                    raise StageError(
                        self.stage,
                        f"{label} reached {os.path.relpath(real, self.workspace)} through {path}",
                        "Trial edits only reach project headers found under the scratch src/.",
                    )
        failed = [
            index for index, outcome in sorted(audit.baseline.items()) if not outcome.ok
        ]
        if failed:
            detail = "\n\n".join(
                f"{audit.checks[i].label}\n{audit.baseline[i].output}" for i in failed
            )
            raise StageError(
                self.stage,
                f"{len(failed)} of {len(audit.checks)} checks fail on the untouched snapshot",
                detail,
            )
        say(f"{len(headers)} headers compile alone and {len(sources)} sources pass")

    def trials(self) -> None:
        audit = self.audit
        candidates = audit.classify()
        order = [rel for rel in audit.order() if rel in candidates]
        count = sum(len(group) for group in candidates.values())
        say(
            f"{count} candidates in {len(order)} files, {len(audit.not_tried)} directives not tried"
        )
        for position, rel in enumerate(order, 1):
            before = len(audit.removed)
            audit.audit_file(rel, candidates[rel])
            removed = len(audit.removed) - before
            say(
                f"[{position}/{len(order)}] {rel}: {removed} of {len(candidates[rel])} removable"
            )

    def final_checks(self) -> None:
        audit = self.audit
        audit.final = audit.run(range(len(audit.checks)))
        headers = [i for i, check in enumerate(audit.checks) if check.source is None]
        sources = [
            i for i, check in enumerate(audit.checks) if check.source is not None
        ]
        self.header_checks = (sum(audit.final[i].ok for i in headers), len(headers))
        self.source_checks = (sum(audit.final[i].ok for i in sources), len(sources))
        failed = [
            index for index, outcome in sorted(audit.final.items()) if not outcome.ok
        ]
        if failed:
            detail = "\n\n".join(
                f"{audit.checks[i].label}\n{audit.final[i].output}" for i in failed
            )
            raise StageError(
                self.stage,
                f"{len(failed)} checks fail with all removals in place",
                detail,
            )

    def clean_build(self) -> None:
        for name in ("build", "install", "log"):
            shutil.rmtree(os.path.join(self.workspace, name), ignore_errors=True)
        self.build_result = "failed"
        self.build("final")
        self.build_result = "passed"

    def check_snapshot(self) -> None:
        listed = self.git(
            "ls-files", "-z", "--cached", "--others", "--exclude-standard"
        )
        if listed is None:
            return
        current = sorted(path for path in listed.split("\0") if path)
        hashes = fingerprint(self.checkout, current)
        self.changed_during_run = sorted(
            rel
            for rel in set(hashes) | set(self.hashes)
            if hashes.get(rel) != self.hashes.get(rel)
        )

    def execute(self) -> None:
        stages = (
            ("environment", None, self.prepare),
            (
                "baseline build",
                "building the untouched snapshot",
                lambda: self.build("baseline"),
            ),
            (
                "compile environments",
                "deriving compile environments from the CMake targets",
                self.derive_envs,
            ),
            (
                "baseline checks",
                "compiling each header alone and each source, before any removal",
                self.baseline_checks,
            ),
            ("removal trials", "trying removals bottom-up", self.trials),
            (
                "final standalone checks",
                "compiling each header alone and each source, with all removals in place",
                self.final_checks,
            ),
            (
                "clean full build",
                "building the workspace from scratch with all removals in place",
                self.clean_build,
            ),
        )
        for stage, message, action in stages:
            self.stage = stage
            if message:
                step(message)
            action()
            self.completed.append(stage)
        self.verified = True

    def prepare(self) -> None:
        self.describe_snapshot()
        self.check_environment()

    def result(self) -> str:
        if self.verified:
            return "VERIFIED"
        return "INCOMPLETE" if self.interrupted else "FAILED"

    def build_summary(self) -> str:
        if self.build_result != "passed":
            return self.build_result
        packages = ", ".join(self.packages)
        return f"passed from empty build/, install/ and log/\n({packages})"

    def notes(self, directive: Directive) -> list[str]:
        notes = [self.audit.supply(directive)]
        if directive.conditions:
            notes.append(
                f"Inside {directive.conditions[-1]}. Verified for this configuration only."
            )
        return notes

    def finish(self) -> None:
        self.check_snapshot()
        text = Reporter(self).render()
        os.makedirs(os.path.dirname(self.report), exist_ok=True)
        write_text(self.report + ".tmp", text)
        os.replace(self.report + ".tmp", self.report)
        self.print_summary()

    def print_summary(self) -> None:
        color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
        green, red, reset = (
            ("\033[32m", "\033[31m", "\033[0m") if color else ("", "", "")
        )
        audit = self.audit
        examined = sum(len(group) for group in audit.directives.values())
        print()
        if self.verified:
            print(f"{green}[venimapping] include audit verified{reset}")
        else:
            state = "interrupted" if self.interrupted else "failed"
            print(
                f"{red}[venimapping] ERROR: include audit {state} at stage: {self.error.stage}{reset}"
            )
            print(f"[venimapping]   {self.error.message}")
        rows = [
            ("include directives examined", str(examined)),
            (
                "verified removable together",
                str(len(audit.removed)) if self.verified else "none (not verified)",
            ),
            (
                "standalone header checks",
                ratio(self.header_checks).replace(" with all removals in place", ""),
            ),
            ("clean full build", self.build_result),
            ("report", os.path.relpath(self.report, self.checkout)),
        ]
        for label, value in rows:
            print(f"[venimapping]   {label + ':':<29}{value}")


# --- Report -------------------------------------------------------------------

LEGEND = (
    "Each entry shows the original line number and directive. The note says what the trace "
    "of the file's own check showed with all removals in place."
)
CHECKS_INTRO = (
    "A standalone check compiles a generated translation unit whose only line includes the "
    "header. A public header gets the flags of a minimal consumer of the narrowest library "
    "target whose include directories reach it. Any other header gets the flags of a target "
    "that compiles it. A source check runs the compile command of the source with "
    "-fsyntax-only. Every check keeps the compiler, working directory, defines, standard and "
    "include order of its CMake command."
)
LIMITS = (
    (
        "The results apply to the compiler, flags and dependency versions above. "
        "Another compiler, standard library or ROS release can need an include that "
        "this one supplies through other headers."
    ),
    (
        "Removable means that this build does not need the directive. The file can "
        'still use declarations from the removed header. "Supplied by" and "Still '
        'included through" name the includes that bring it in. Keep a direct include '
        "for a header whose declarations the file uses itself if you do not want to "
        "depend on those includes."
    ),
    (
        "A check proves that the code compiles. It cannot show that a removal changes "
        "which overload or specialization a call selects."
    ),
    (
        'A removal from a file marked "public header" changes what code outside this '
        "workspace receives through that header. The checks cover consumers inside "
        "this workspace only."
    ),
    'Directives under "Not tried" are unverified.',
    (
        "Trials run in a fixed order: files from leaf headers to sources, directives "
        "from top to bottom. When two directives can replace each other, the earlier "
        "one in that order is removed. The set is valid as a whole. It is not "
        "necessarily the largest valid set."
    ),
)


def wrap(text: str, first: str, rest: str | None = None) -> list[str]:
    rest = first if rest is None else rest
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        lines += textwrap.wrap(
            paragraph,
            80,
            initial_indent=first,
            subsequent_indent=rest,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [first.rstrip()]
        first = rest
    return lines


def heading(title: str) -> list[str]:
    return [title, "-" * len(title)]


def table(rows: list[tuple[str, str]], width: int = 30) -> list[str]:
    lines = []
    for label, value in rows:
        parts = value.splitlines() or [""]
        lines.append(f"  {label:<{width}}{parts[0]}".rstrip())
        lines += [f"  {'':<{width}}{part}".rstrip() for part in parts[1:]]
    return lines


def findings(items: list[tuple[Directive, list[str]]], public: set[str]) -> list[str]:
    by_file: dict[str, list[tuple[Directive, list[str]]]] = {}
    for directive, notes in items:
        by_file.setdefault(directive.path, []).append((directive, notes))
    lines = []
    for path in sorted(by_file):
        lines.append(path + ("  (public header)" if path in public else ""))
        for directive, notes in sorted(by_file[path], key=lambda item: item[0].line):
            lines.append(f"  {directive.line:<4}{directive.text.strip()}")
            for note in notes:
                lines += wrap(note, " " * 6)
        lines.append("")
    return lines or ["None.", ""]


def ratio(counts: tuple[int, int] | None) -> str:
    if counts is None:
        return "not run"
    return f"{counts[0]} of {counts[1]} passed with all removals in place"


class Reporter:
    def __init__(self, run: Run):
        self.run = run

    def render(self) -> str:
        run, audit = self.run, self.run.audit
        by_key = {d.key: d for rel in audit.files for d in audit.directives[rel]}
        public = {check.subject for check in audit.checks if check.public}
        finished = datetime.datetime.now().astimezone()
        seconds = int((finished - run.begin).total_seconds())
        lines = ["VeniMapping include audit", "=" * 25, ""]
        lines += table(
            [
                ("Result", run.result()),
                ("Started", run.started),
                ("Finished", f"{finished:%Y-%m-%d %H:%M:%S %z} ({seconds} s)"),
            ]
            + (
                [("Failed stage", run.error.stage), ("Problem", run.error.message)]
                if run.error
                else []
            ),
            width=14,
        )
        lines.append("")
        if run.verified:
            intro = (
                'Every removal under "Removable together" was in place at the same time for the '
                "final standalone header checks, the source checks and a clean full build."
            )
        else:
            intro = (
                "Verification did not finish. No removal in this report is verified."
            )
        lines += wrap(intro, "") + [""]
        if run.changed_during_run:
            lines += wrap(
                "The working tree changed while the audit ran. The findings describe the "
                "snapshot taken at the start. Changed files: "
                + ", ".join(run.changed_during_run),
                "",
            ) + [""]

        tried = "removal trials" in run.completed
        lines += heading("Summary")
        lines += table(
            [
                ("Include directives examined", str(len(by_key))),
                (
                    "Verified removable together",
                    str(len(audit.removed)) if run.verified else "none",
                ),
                (
                    "Kept, removal failed a check",
                    str(len(audit.kept)) if tried else "not run",
                ),
                ("Not tried", str(len(audit.not_tried)) if tried else "not run"),
                ("Standalone header checks", ratio(run.header_checks)),
                ("Source checks", ratio(run.source_checks)),
                ("Clean full build", run.build_summary()),
            ]
        )
        lines.append("")
        if run.error and run.error.detail:
            lines += heading("Diagnostic")
            lines += ["  " + line for line in run.error.detail.splitlines()] + [""]

        lines += heading("Where the evidence applies")
        lines += table(
            [("Snapshot", "\n".join(run.snapshot) or "not described")] + run.facts,
            width=14,
        )
        lines.append("")

        if run.verified:
            lines += heading("Removable together (verified)")
            lines += wrap(LEGEND, "") + [""]
            lines += findings([(d, run.notes(d)) for d in audit.removed], public)
        elif audit.removed:
            lines += heading("Passed their trials, NOT verified")
            lines += findings([(d, []) for d in audit.removed], public)
        if tried:
            lines += heading("Kept: removal failed a check")
            lines += findings(
                [(by_key[key], [why]) for key, why in audit.kept.items()], public
            )
            lines += heading("Not tried")
            lines += findings(
                [(by_key[key], [why]) for key, why in audit.not_tried.items()], public
            )

        if audit.checks:
            lines += heading("Checks")
            lines += wrap(CHECKS_INTRO, "") + [""]
            for index, check in sorted(
                enumerate(audit.checks),
                key=lambda item: (item[1].source is not None, item[1].subject),
            ):
                kind = "standalone" if check.source is None else "source"
                status = [
                    f"{name} {('passed' if outcome.ok else 'failed') if outcome else 'not run'}"
                    for name, outcome in (
                        ("baseline", audit.baseline.get(index)),
                        ("final", audit.final.get(index)),
                    )
                ]
                lines.append(f"  {check.subject}")
                lines.append(f"      {kind}, {check.env}: {', '.join(status)}")
            unchecked = sorted(
                set(audit.files) - {check.subject for check in audit.checks}
            )
            if unchecked:
                lines += [""] + wrap(
                    "No check of its own: " + ", ".join(unchecked) + ".", "  "
                )
            lines.append("")
            lines += wrap(
                f"{audit.trials} removal trials ran {audit.compiler.count} compiler runs, "
                f"up to {audit.compiler.jobs} at a time.",
                "",
            ) + [""]

        lines += heading("Limits")
        for limit in LIMITS:
            lines += wrap(limit, "  - ", "    ")
        return "\n".join(lines) + "\n"


# --- Main ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Use scripts/audit-includes.sh to run the audit."
    )
    for option in ("--checkout", "--workspace", "--scratch", "--report", "--started"):
        parser.add_argument(option, required=True)
    session = Run(parser.parse_args(argv))
    code = 1
    try:
        session.execute()
        code = 0
    except StageError as error:
        session.error = error
    except KeyboardInterrupt:
        session.interrupted = True
        session.error = StageError(
            session.stage, "interrupted before the audit finished"
        )
        code = 130
    except Exception:  # noqa: BLE001
        session.error = StageError(
            session.stage, "internal error in audit_includes.py", traceback.format_exc()
        )
    finally:
        session.audit.compiler.pool.shutdown(wait=False, cancel_futures=True)
    session.finish()
    return code


if __name__ == "__main__":
    sys.exit(main())
