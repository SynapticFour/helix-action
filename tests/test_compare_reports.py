# SPDX-License-Identifier: Apache-2.0
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_reports.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(ROOT / "scripts"))
import compare_reports  # noqa: E402


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class CompareReportsTest(unittest.TestCase):
    def test_score_ignores_skips(self):
        report = load("all_pass.json")
        self.assertEqual(compare_reports.score(report), (5, 5))

    def test_wes_skip_is_not_pass(self):
        report = load("all_pass.json")
        self.assertEqual(compare_reports.service_verdict(report, "Drs"), "PASS")
        self.assertEqual(compare_reports.service_verdict(report, "Wes"), "SKIP")
        line = compare_reports.comment_line(None, report)
        self.assertIn("DRS: PASS", line)
        self.assertIn("WES: SKIP", line)
        self.assertNotIn("WES: PASS", line)

    def test_known_fail_is_not_regression(self):
        prev = load("known_fail.json")
        cur = load("known_fail.json")
        self.assertEqual(compare_reports.regressions(prev, cur), [])
        self.assertEqual(compare_reports.score(cur), (4, 5))

    def test_pass_to_fail_is_regression(self):
        prev = load("all_pass.json")
        cur = load("known_fail.json")
        regs = compare_reports.regressions(prev, cur)
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["name"], "DRS checksum correctness")

    def test_fail_to_pass_is_not_regression(self):
        prev = load("known_fail.json")
        cur = load("all_pass.json")
        self.assertEqual(compare_reports.regressions(prev, cur), [])

    def test_skip_to_fail_is_not_regression(self):
        prev = {
            "services": [
                {
                    "service": "Drs",
                    "tests": [
                        {
                            "name": "DRS checksum correctness",
                            "status": "skip",
                            "passed": False,
                        }
                    ],
                }
            ]
        }
        cur = {
            "services": [
                {
                    "service": "Drs",
                    "tests": [
                        {
                            "name": "DRS checksum correctness",
                            "status": "fail",
                            "passed": False,
                        }
                    ],
                }
            ]
        }
        self.assertEqual(compare_reports.regressions(prev, cur), [])

    def test_no_previous_is_not_regression(self):
        cur = load("known_fail.json")
        self.assertEqual(compare_reports.regressions(None, cur), [])
        line = compare_reports.comment_line(None, cur)
        self.assertTrue(line.startswith("Helix Verification — Previous: n/a | Current: 4/5"))

    def test_cli_exit_codes(self):
        pass_f = FIXTURES / "all_pass.json"
        fail_f = FIXTURES / "known_fail.json"
        r0 = subprocess.run(
            [sys.executable, str(SCRIPT), "--previous", str(fail_f), "--current", str(fail_f)],
            check=False,
        )
        self.assertEqual(r0.returncode, 0)
        r1 = subprocess.run(
            [sys.executable, str(SCRIPT), "--previous", str(pass_f), "--current", str(fail_f)],
            check=False,
        )
        self.assertEqual(r1.returncode, 1)
        r2 = subprocess.run(
            [sys.executable, str(SCRIPT), "--current", str(fail_f)],
            check=False,
        )
        self.assertEqual(r2.returncode, 0)

    def test_bench_warning_appends_comment_and_keeps_exit_zero(self):
        pass_f = FIXTURES / "all_pass.json"
        bench_f = FIXTURES / "bench_warn.json"
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--current",
                str(pass_f),
                "--bench-json",
                str(bench_f),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0)
        report = load("all_pass.json")
        bench = json.loads(bench_f.read_text(encoding="utf-8"))
        comment = compare_reports.render_comment(None, report, bench)
        self.assertIn("Helix bench (warn only — does not fail this job)", comment)
        self.assertIn("wall_ms +20.0% exceeds 10% threshold", comment)
        self.assertIn("WARN", comment)

    def test_bench_warning_does_not_clear_regression_exit(self):
        pass_f = FIXTURES / "all_pass.json"
        fail_f = FIXTURES / "known_fail.json"
        bench_f = FIXTURES / "bench_warn.json"
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--previous",
                str(pass_f),
                "--current",
                str(fail_f),
                "--bench-json",
                str(bench_f),
            ],
            check=False,
        )
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
