# ------------------------------------------------------------------------------
#  Filename: test_audit_includes.py
#
#  Purpose:  Regression tests for the include audit that a passing project build cannot catch.
#
#  Usage:    python3 -m unittest discover -s scripts/support -p 'test_*.py'
#
#  Copyright (C) 2026 Logan Kaising.  All rights reserved.
# ------------------------------------------------------------------------------

import argparse
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import audit_includes as ai

# --- Directive scanning -------------------------------------------------------


class ScanTest(unittest.TestCase):
    def scan(self, text):
        return ai.scan_directives("src/x.hpp", text)

    def test_ignores_commented_and_raw_string_includes(self):
        text = (
            "// #include <a>\n"
            "/* start\n"
            "#include <b>\n"
            "*/\n"
            'auto s = R"(\n'
            "#include <c>\n"
            ')";\n'
            "#include <d> // kept comment\n"
        )
        found = self.scan(text)
        self.assertEqual([(d.line, d.spelled) for d in found], [(8, "<d>")])
        self.assertEqual(found[0].text, "#include <d> // kept comment")

    def test_continuation_keeps_first_line_and_span(self):
        found = self.scan("#include \\\n  <vector>\nint x;\n")
        self.assertEqual(
            (found[0].line, found[0].last, found[0].spelled), (1, 2, "<vector>")
        )

    def test_include_guard_is_not_a_condition(self):
        text = "#ifndef G\n#define G\n#include <a>\n#ifdef FOO\n#  include <b>\n#endif\n#endif\n"
        found = self.scan(text)
        self.assertEqual(found[0].conditions, ())
        self.assertEqual(found[1].conditions, ("#ifdef FOO (line 4)",))

    def test_iwyu_pragmas(self):
        text = (
            "#include <a>  // IWYU pragma: keep\n"
            "// IWYU pragma: begin_exports\n"
            "#include <b>\n"
            "// IWYU pragma: end_exports\n"
            "#include <c>\n"
        )
        self.assertEqual([d.pragma for d in self.scan(text)], ["keep", "export", None])

    def test_block_comment_after_directive_is_not_editable(self):
        found = self.scan("#include <a> /* spans\nlines */\n")
        self.assertFalse(found[0].editable)

    def test_blank_keeps_line_numbers(self):
        lines = ["#include <a>", "#include \\", "  <b>", "int x;"]
        directives = self.scan("\n".join(lines))
        self.assertEqual(ai.blank(lines, directives), ["", "", "", "int x;"])


# --- Synthetic project --------------------------------------------------------

FILES = {
    "src/inc/types.hpp": "#pragma once\nusing u8 = unsigned char;\n",
    "src/inc/raw.hpp": '#pragma once\n#include "types.hpp"\nstruct Raw { u8 value; };\n',
    "src/inc/common.hpp": "#pragma once\nstruct Common {};\n",
    "src/inc/a.hpp": '#pragma once\n#include "common.hpp"\nstruct A {};\n',
    "src/inc/b.hpp": '#pragma once\n#include "common.hpp"\nstruct B {};\n',
    "src/inc/wrap.hpp": '#pragma once\n#include "common.hpp"\nstruct Wrap { Common c; };\n',
    "src/use.cpp": (
        '#include "types.hpp"\n'
        '#include "raw.hpp"\n'
        '#include "a.hpp"  // IWYU pragma: keep\n'
        '#include "b.hpp"\n'
        "#if defined(NEVER_DEFINED)\n"
        '#include "missing.hpp"\n'
        "#endif\n"
        "Raw r; Common c; u8 x = 0;\n"
    ),
    "src/pair.cpp": '#include "common.hpp"\n#include "wrap.hpp"\nCommon p;\n',
}


def make_workspace(parent):
    workspace = os.path.join(parent, f"ws{len(os.listdir(parent))}")
    for rel, text in FILES.items():
        os.makedirs(os.path.dirname(os.path.join(workspace, rel)), exist_ok=True)
        ai.write_text(os.path.join(workspace, rel), text)
    return workspace


def trial_run(audit, standalone=True):
    """Drive the trial stages the way Run does, with plain g++ checks."""
    workspace = audit.workspace
    flags = ["g++", "-std=c++23", "-I" + os.path.join(workspace, "src", "inc")]
    for rel in audit.files:
        path = os.path.join(workspace, rel)
        if rel.endswith(".cpp"):
            audit.checks.append(ai.Check(rel, rel, workspace, flags, path, "test"))
        elif standalone:
            label = f"standalone {rel}"
            audit.checks.append(ai.Check(rel, label, workspace, flags, None, "test"))
    audit.record_baseline(audit.run(range(len(audit.checks))))
    candidates = audit.classify()
    for rel in audit.order():
        if rel in candidates:
            audit.audit_file(rel, candidates[rel])
    audit.final = audit.run(range(len(audit.checks)))
    return audit


def make_run(tmp, checkout, workspace):
    args = argparse.Namespace(
        checkout=checkout,
        workspace=workspace,
        scratch=tmp,
        report=os.path.join(tmp, "report.txt"),
        started="now",
    )
    return ai.Run(args)


@unittest.skipUnless(shutil.which("g++"), "g++ is required")
class TrialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def audit(self, standalone=True):
        workspace = make_workspace(self.tmp)
        audit = ai.Audit(workspace, os.path.join(workspace, "audit"), jobs=4)
        return trial_run(audit, standalone)

    def removed(self, audit):
        return sorted(d.key for d in audit.removed)

    def test_standalone_check_rejects_what_the_source_build_accepts(self):
        with_standalone = self.audit()
        key = ("src/inc/raw.hpp", 2)
        self.assertNotIn(key, self.removed(with_standalone))
        self.assertIn("its standalone check", with_standalone.kept[key])
        self.assertIn(key, self.removed(self.audit(standalone=False)))

    def test_jointly_valid_set(self):
        audit = self.audit()
        self.assertEqual(
            self.removed(audit),
            [("src/inc/a.hpp", 2), ("src/pair.cpp", 1), ("src/use.cpp", 1)],
        )
        self.assertTrue(all(outcome.ok for outcome in audit.final.values()))

    def test_competing_providers_resolve_in_a_fixed_order(self):
        audit = self.audit()
        self.assertIn(("src/inc/b.hpp", 2), audit.kept)
        self.assertIn("Passed alone", audit.kept[("src/pair.cpp", 2)])
        self.assertEqual(self.removed(audit), self.removed(self.audit()))

    def test_unexercised_and_marked_directives_are_not_tried(self):
        audit = self.audit()
        inactive = audit.not_tried[("src/use.cpp", 6)]
        self.assertIn("#if defined(NEVER_DEFINED) (line 5)", inactive)
        self.assertIn("Unverified", inactive)
        self.assertIn("IWYU pragma: keep", audit.not_tried[("src/use.cpp", 3)])

    def test_removals_keep_original_line_numbers(self):
        audit = self.audit()
        path = os.path.join(audit.workspace, "src", "use.cpp")
        lines = ai.read_text(path).split("\n")
        self.assertEqual(lines[0], "")
        self.assertEqual(lines[1], '#include "raw.hpp"')
        self.assertEqual(len(lines), len(FILES["src/use.cpp"].split("\n")))

    def test_provider_notes_follow_the_final_trace(self):
        audit = self.audit()
        notes = {d.key: audit.supply(d) for d in audit.removed}
        self.assertEqual(notes[("src/use.cpp", 1)], 'Supplied by "raw.hpp".')
        self.assertEqual(notes[("src/pair.cpp", 1)], 'Supplied by "wrap.hpp".')
        self.assertIn("No longer included", notes[("src/inc/a.hpp", 2)])


# --- Run and report -----------------------------------------------------------


@unittest.skipUnless(shutil.which("g++"), "g++ is required")
class TraceTest(unittest.TestCase):
    def test_skipped_includes_keep_their_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in {
                "common.hpp": "#pragma once\n",
                "a.hpp": '#pragma once\n#include "common.hpp"\nstruct A {};\n',
                "b.hpp": '#pragma once\n#include "common.hpp"\nstruct B {};\n',
                "t.cpp": '#include "a.hpp"\n#include "b.hpp"\n',
            }.items():
                ai.write_text(os.path.join(tmp, name), text)
            source = os.path.join(tmp, "t.cpp")
            check = ai.Check("t.cpp", "t.cpp", tmp, ["g++"], source, "test")
            outcome = ai.Compiler(tmp, 1)._run(check, ai.Tree(tmp, tmp), "trace")
            common = os.path.join(tmp, "common.hpp")
            edges = {
                (os.path.basename(f), line, target)
                for f, line, _, target in outcome.trace.directives
            }
            self.assertIn(("a.hpp", 2, common), edges)
            self.assertIn(("b.hpp", 2, common), edges)
            self.assertEqual(outcome.trace.parent[common], os.path.join(tmp, "a.hpp"))
            self.assertIn(source, outcome.trace.parent)


@unittest.skipUnless(shutil.which("g++"), "g++ is required")
class ReportTest(unittest.TestCase):
    def test_verified_only_after_the_final_stages_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp, os.path.join(tmp, "checkout"), make_workspace(tmp))
            trial_run(run.audit)
            run.completed = ["removal trials"]
            run.error = ai.StageError("clean full build", "colcon build exited with 2")
            failed = ai.Reporter(run).render()
            self.assertIn("FAILED", failed)
            self.assertIn("Passed their trials, NOT verified", failed)
            self.assertNotIn("Removable together (verified)", failed)

            run.error, run.verified = None, True
            verified = ai.Reporter(run).render()
            self.assertIn("Removable together (verified)", verified)
            self.assertIn('  1   #include "types.hpp"', verified)
            self.assertIn('Supplied by "raw.hpp".', verified)


class EnvironmentTest(unittest.TestCase):
    def test_rejects_variables_that_point_into_the_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout, workspace = os.path.join(tmp, "checkout"), os.path.join(tmp, "ws")
            os.makedirs(os.path.join(workspace, ".devcontainer"))
            ai.write_text(os.path.join(workspace, ai.COLCON_DEFAULTS), "")
            run = make_run(tmp, checkout, workspace)
            overlay = f"/opt/ros:{os.path.join(checkout, 'install')}"
            with (
                mock.patch.dict(os.environ, {"AMENT_PREFIX_PATH": overlay}),
                self.assertRaises(ai.StageError) as raised,
            ):
                run.check_environment()
            self.assertIn("AMENT_PREFIX_PATH", raised.exception.message)


class SnapshotTest(unittest.TestCase):
    def test_lists_changed_and_untracked_paths_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkout = os.path.join(tmp, "checkout")
            os.makedirs(os.path.join(checkout, "src"))
            ai.write_text(os.path.join(checkout, "src", "a.hpp"), "#pragma once\n")
            git = ["git", "-C", checkout, "-c", "user.name=t", "-c", "user.email=t@t"]
            subprocess.run([*git, "init", "-q"], check=True)
            subprocess.run([*git, "add", "."], check=True)
            subprocess.run([*git, "commit", "-q", "-m", "init"], check=True)
            ai.write_text(
                os.path.join(checkout, "src", "a.hpp"), "#pragma once\nint a;\n"
            )
            ai.write_text(os.path.join(checkout, "src", "b.hpp"), "#pragma once\n")
            workspace = os.path.join(tmp, "ws")
            os.makedirs(workspace)
            run = make_run(tmp, checkout, workspace)
            run.describe_snapshot()
            self.assertIn("1 changed and 1 untracked", run.snapshot[1])
            self.assertEqual(run.snapshot[2:], ["  src/a.hpp", "  src/b.hpp"])


if __name__ == "__main__":
    unittest.main()
