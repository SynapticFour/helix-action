# SPDX-License-Identifier: Apache-2.0
"""Compare VerificationRun JSON at stable Helix id. Not a score."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_reports.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(ROOT / "scripts"))
import compare_reports  # noqa: E402


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


class ShapeTest(unittest.TestCase):
    def test_load_report_accepts_verification_run(self):
        data = compare_reports.load_report(FIXTURES / "all_pass.json")
        self.assertEqual(data["schema_version"], "helix-verification-v1")
        self.assertIsInstance(data["executed"], list)
        self.assertIsInstance(data["skipped"], list)

    def test_load_report_rejects_overall_report(self):
        with self.assertRaises(ValueError) as ctx:
            compare_reports.load_report(FIXTURES / "overall_report.json")
        msg = str(ctx.exception)
        self.assertIn("OverallReport", msg)
        self.assertIn("VerificationRun", msg)
        self.assertIn("services[]", msg)
        self.assertIn("helix security", msg)

    def test_load_report_rejects_unknown_shape(self):
        with self.assertRaises(ValueError) as ctx:
            compare_reports.load_report(FIXTURES / "unknown.json")
        msg = str(ctx.exception)
        self.assertIn("not a Helix VerificationRun", msg)
        self.assertIn("executed[]", msg)

    def test_missing_schema_version_with_executed_skipped_is_v1(self):
        data = {
            "executed": [
                {
                    "id": "drs.object.reachable",
                    "code": "HLX-DRS-001",
                    "status": "pass",
                }
            ],
            "skipped": [],
        }
        self.assertTrue(compare_reports.is_verification_run(data))
        self.assertFalse(compare_reports.is_overall_report(data))

    def test_wrong_schema_version_is_rejected(self):
        data = {
            "schema_version": "helix-verification-v2",
            "executed": [],
            "skipped": [],
        }
        self.assertFalse(compare_reports.is_verification_run(data))
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".json", delete=False
        ) as fh:
            json.dump(data, fh)
            path = Path(fh.name)
        try:
            with self.assertRaises(ValueError) as ctx:
                compare_reports.load_report(path)
            self.assertIn("helix-verification-v2", str(ctx.exception))
            self.assertIn("helix-verification-v1", str(ctx.exception))
        finally:
            path.unlink(missing_ok=True)


class ClassifyTest(unittest.TestCase):
    def test_pass_to_fail_is_new_fail(self):
        self.assertEqual(compare_reports.classify("pass", "fail"), "NEW_FAIL")
        self.assertEqual(compare_reports.classify("pass", "error"), "NEW_FAIL")

    def test_fail_to_fail_is_unchanged(self):
        self.assertEqual(compare_reports.classify("fail", "fail"), "UNCHANGED_FAIL")
        self.assertEqual(compare_reports.classify("fail", "error"), "UNCHANGED_FAIL")

    def test_fail_to_pass_is_fixed(self):
        self.assertEqual(compare_reports.classify("fail", "pass"), "FIXED")

    def test_skip_to_pass_is_fixed_skip_not_unchanged_pass(self):
        self.assertEqual(compare_reports.classify("skip", "pass"), "FIXED_SKIP")
        self.assertNotEqual(compare_reports.classify("skip", "pass"), "UNCHANGED_PASS")

    def test_skip_to_fail_is_not_new_fail(self):
        self.assertEqual(compare_reports.classify("skip", "fail"), "FIXED_SKIP")

    def test_pass_to_skip_is_new_skip(self):
        self.assertEqual(compare_reports.classify("pass", "skip"), "NEW_SKIP")

    def test_added_fail_is_not_new_fail(self):
        self.assertEqual(compare_reports.classify(None, "fail"), "ADDED")


class CompareRunsTest(unittest.TestCase):
    def test_known_fail_is_not_regression(self):
        report = compare_reports.compare_runs(load("known_fail.json"), load("known_fail.json"))
        self.assertFalse(report["has_regression"])
        self.assertEqual(report["summary"]["new_fail"], 0)
        self.assertEqual(report["summary"]["unchanged_fail"], 1)
        self.assertEqual(compare_reports.executed_score(load("known_fail.json")), (4, 5))

    def test_pass_to_fail_is_regression_at_id(self):
        report = compare_reports.compare_runs(load("all_pass.json"), load("known_fail.json"))
        self.assertTrue(report["has_regression"])
        self.assertEqual(report["summary"]["new_fail"], 1)
        row = next(r for r in report["rows"] if r["kind"] == "NEW_FAIL")
        self.assertEqual(row["id"], "drs.object.checksum")
        self.assertEqual(row["code"], "HLX-DRS-003")

    def test_fail_to_pass_is_fixed_not_regression(self):
        report = compare_reports.compare_runs(load("known_fail.json"), load("all_pass.json"))
        self.assertFalse(report["has_regression"])
        self.assertEqual(report["summary"]["fixed"], 1)

    def test_score_drop_from_skip_is_not_regression(self):
        report = compare_reports.compare_runs(load("all_pass.json"), load("score_drop_skip.json"))
        self.assertFalse(report["has_regression"])
        self.assertEqual(report["summary"]["new_skip"], 1)
        row = next(r for r in report["rows"] if r["id"] == "drs.object.checksum")
        self.assertEqual(row["kind"], "NEW_SKIP")

    def test_skip_became_pass_is_fixed_skip(self):
        report = compare_reports.compare_runs(
            load("skip_only_scatter.json"), load("skip_became_pass.json")
        )
        self.assertFalse(report["has_regression"])
        row = next(r for r in report["rows"] if r["id"] == "wes.run.scatter_gather")
        self.assertEqual(row["kind"], "FIXED_SKIP")
        self.assertTrue(row["skip_became_pass"])
        self.assertEqual(report["summary"]["skip_became_pass"], 1)

    def test_skip_to_fail_is_not_regression(self):
        prev = {
            "schema_version": "helix-verification-v1",
            "executed": [],
            "skipped": [
                {
                    "id": "drs.object.checksum",
                    "code": "HLX-DRS-003",
                    "status": "skip",
                }
            ],
        }
        cur = {
            "schema_version": "helix-verification-v1",
            "executed": [
                {
                    "id": "drs.object.checksum",
                    "code": "HLX-DRS-003",
                    "status": "fail",
                }
            ],
            "skipped": [],
        }
        report = compare_reports.compare_runs(prev, cur)
        self.assertFalse(report["has_regression"])
        self.assertEqual(report["summary"]["fixed_skip"], 1)

    def test_no_previous_is_not_regression(self):
        report = compare_reports.compare_runs(None, load("known_fail.json"))
        self.assertFalse(report["has_regression"])
        self.assertTrue(all(r["kind"] == "ADDED" for r in report["rows"]))

    def test_mixed_kinds(self):
        report = compare_reports.compare_runs(
            load("mixed_previous.json"), load("mixed_current.json")
        )
        by_id = {r["id"]: r["kind"] for r in report["rows"]}
        self.assertEqual(by_id["drs.object.checksum"], "NEW_FAIL")
        self.assertEqual(by_id["drs.object.range"], "FIXED")
        self.assertEqual(by_id["drs.object.not_found"], "UNCHANGED_FAIL")
        self.assertTrue(report["has_regression"])

    def test_pass_to_error_is_new_fail(self):
        report = compare_reports.compare_runs(
            load("all_pass.json"), load("unreachable.json")
        )
        self.assertTrue(report["has_regression"])
        self.assertGreaterEqual(report["summary"]["new_fail"], 1)


class CommentTest(unittest.TestCase):
    def test_comment_order_and_not_score_headline(self):
        report = compare_reports.compare_runs(
            load("mixed_previous.json"), load("mixed_current.json")
        )
        comment = compare_reports.render_comment(report)
        self.assertIn("<!-- helix-verification -->", comment)
        self.assertIn("# Helix verification", comment)
        lead = comment.split("## Helix bench")[0]
        self.assertNotRegex(lead, r"Previous:\s*\d+/\d+")
        self.assertNotRegex(comment.split("##")[0], r"\d+/\d+")
        self.assertIn("**New regressions:** 1", comment)
        self.assertIn("**Fixed failures:** 1", comment)
        self.assertIn("**Existing failures:** 1", comment)
        new_i = comment.index("## New regressions")
        fixed_i = comment.index("## Fixed failures")
        exist_i = comment.index("## Existing failures")
        self.assertLess(new_i, fixed_i)
        self.assertLess(fixed_i, exist_i)
        self.assertIn("`drs.object.checksum` (`HLX-DRS-003`) pass → fail", comment)
        self.assertIn("`drs.object.range` (`HLX-DRS-004`) fail → pass", comment)
        self.assertIn("`drs.object.not_found` (`HLX-DRS-005`) fail → fail", comment)
        self.assertIn("Not HELIOS", comment)
        self.assertIn("Not GA4GH certification", comment)

    def test_headline_is_not_xy_score(self):
        report = compare_reports.compare_runs(load("all_pass.json"), load("known_fail.json"))
        line = compare_reports.headline(report)
        self.assertIn("new regressions: 1", line)
        self.assertNotRegex(line, r"\d+/\d+")

    def test_skip_became_pass_section(self):
        report = compare_reports.compare_runs(
            load("skip_only_scatter.json"), load("skip_became_pass.json")
        )
        comment = compare_reports.render_comment(report)
        self.assertIn("## SKIP became PASS", comment)
        self.assertIn("FIXED_SKIP", comment)


class CliExitTest(unittest.TestCase):
    def test_known_fail_exit_zero(self):
        fail_f = FIXTURES / "known_fail.json"
        r = run_script("--previous", str(fail_f), "--current", str(fail_f))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_new_fail_exit_one(self):
        r = run_script(
            "--previous",
            str(FIXTURES / "all_pass.json"),
            "--current",
            str(FIXTURES / "known_fail.json"),
        )
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_no_previous_exit_zero(self):
        r = run_script("--current", str(FIXTURES / "known_fail.json"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_score_drop_skip_exit_zero(self):
        r = run_script(
            "--previous",
            str(FIXTURES / "all_pass.json"),
            "--current",
            str(FIXTURES / "score_drop_skip.json"),
        )
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_skip_became_pass_exit_zero(self):
        r = run_script(
            "--previous",
            str(FIXTURES / "skip_only_scatter.json"),
            "--current",
            str(FIXTURES / "skip_became_pass.json"),
        )
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_overall_report_previous_is_not_compared(self):
        r = run_script(
            "--previous",
            str(FIXTURES / "overall_report.json"),
            "--current",
            str(FIXTURES / "known_fail.json"),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as fh:
            out = Path(fh.name)
        try:
            r2 = run_script(
                "--previous",
                str(FIXTURES / "overall_report.json"),
                "--current",
                str(FIXTURES / "known_fail.json"),
                "--comment-out",
                str(out),
            )
            self.assertEqual(r2.returncode, 0, r2.stderr)
            body = out.read_text(encoding="utf-8")
            self.assertIn("OverallReport", body)
            self.assertIn("_No new regressions", body)
        finally:
            out.unlink(missing_ok=True)

    def test_overall_report_current_is_runtime_exit_two(self):
        r = run_script("--current", str(FIXTURES / "overall_report.json"))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("OverallReport", r.stderr)
        self.assertIn("VerificationRun", r.stderr)

    def test_unknown_current_is_runtime_exit_two(self):
        r = run_script("--current", str(FIXTURES / "unknown.json"))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("not a Helix VerificationRun", r.stderr)

    def test_pass_to_error_exits_one(self):
        r = run_script(
            "--previous",
            str(FIXTURES / "all_pass.json"),
            "--current",
            str(FIXTURES / "unreachable.json"),
        )
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_bench_warning_keeps_exit_zero(self):
        r = run_script(
            "--current",
            str(FIXTURES / "all_pass.json"),
            "--bench-json",
            str(FIXTURES / "bench_warn.json"),
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as fh:
            out = Path(fh.name)
        try:
            r2 = run_script(
                "--current",
                str(FIXTURES / "all_pass.json"),
                "--bench-json",
                str(FIXTURES / "bench_warn.json"),
                "--comment-out",
                str(out),
            )
            self.assertEqual(r2.returncode, 0, r2.stderr)
            body = out.read_text(encoding="utf-8")
            self.assertIn("Helix bench (warn only — does not fail this job)", body)
            self.assertIn("wall_ms +20.0% exceeds 10% threshold", body)
        finally:
            out.unlink(missing_ok=True)

    def test_bench_warning_does_not_clear_regression_exit(self):
        r = run_script(
            "--previous",
            str(FIXTURES / "all_pass.json"),
            "--current",
            str(FIXTURES / "known_fail.json"),
            "--bench-json",
            str(FIXTURES / "bench_warn.json"),
        )
        self.assertEqual(r.returncode, 1, r.stderr)

    def test_github_output_keeps_scores_and_adds_kinds(self):
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as fh:
            out = Path(fh.name)
        try:
            r = run_script(
                "--previous",
                str(FIXTURES / "all_pass.json"),
                "--current",
                str(FIXTURES / "known_fail.json"),
                "--github-output",
                str(out),
            )
            self.assertEqual(r.returncode, 1, r.stderr)
            text = out.read_text(encoding="utf-8")
            self.assertIn("regression=true", text)
            self.assertIn("new_fail=1", text)
            self.assertIn("fixed=0", text)
            self.assertIn("current_score=4/5", text)
            self.assertIn("previous_score=5/5", text)
        finally:
            out.unlink(missing_ok=True)


class ActionContractTest(unittest.TestCase):
    def test_checkouts_do_not_persist_credentials(self):
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("persist-credentials: false"), 2)

    def test_build_requires_verification_schema_file(self):
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("schemas/helix-verification-v1.json", text)
        self.assertIn('default: "1304d92daa80f6c9b8b164a543c2210bab391863"', text)

    def test_ci_is_contents_read_only(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertIn('run: "false"', text)


if __name__ == "__main__":
    unittest.main()
