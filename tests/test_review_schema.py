"""
Tests for app.review_schema.parse_review_result — fully offline, stdlib only.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.review_schema import parse_review_result, ReviewParseError


class TestParseReviewResult(unittest.TestCase):

    def test_valid_response_with_findings(self):
        raw = json.dumps({
            "summary": "Found two issues.",
            "findings": [
                {"file": "inventory.py", "severity": "high",
                 "description": "Removed input validation", "line_hint": "apply_discount"},
                {"file": "inventory.py", "severity": "medium",
                 "description": "Off-by-one loop bound", "line_hint": "find_item_index"},
            ],
        })
        result = parse_review_result(raw)
        self.assertEqual(result.summary, "Found two issues.")
        self.assertEqual(len(result.findings), 2)
        self.assertEqual(result.findings[0].severity, "high")

    def test_valid_response_with_no_findings(self):
        # A clean PR should be able to produce this without erroring
        raw = json.dumps({"summary": "No issues found.", "findings": []})
        result = parse_review_result(raw)
        self.assertEqual(result.findings, [])

    def test_missing_summary_raises(self):
        raw = json.dumps({"findings": []})
        with self.assertRaises(ReviewParseError):
            parse_review_result(raw)

    def test_missing_findings_raises(self):
        raw = json.dumps({"summary": "ok"})
        with self.assertRaises(ReviewParseError):
            parse_review_result(raw)

    def test_invalid_severity_raises(self):
        raw = json.dumps({
            "summary": "x",
            "findings": [{"file": "a.py", "severity": "critical", "description": "y"}],
        })
        with self.assertRaises(ReviewParseError):
            parse_review_result(raw)

    def test_finding_missing_required_field_raises(self):
        raw = json.dumps({
            "summary": "x",
            "findings": [{"file": "a.py", "severity": "high"}],  # no description
        })
        with self.assertRaises(ReviewParseError):
            parse_review_result(raw)

    def test_malformed_json_raises(self):
        with self.assertRaises(ReviewParseError):
            parse_review_result("{not valid json")

    def test_findings_not_a_list_raises(self):
        raw = json.dumps({"summary": "x", "findings": "should be a list"})
        with self.assertRaises(ReviewParseError):
            parse_review_result(raw)

    def test_line_hint_defaults_to_empty_string(self):
        raw = json.dumps({
            "summary": "x",
            "findings": [{"file": "a.py", "severity": "low", "description": "y"}],
        })
        result = parse_review_result(raw)
        self.assertEqual(result.findings[0].line_hint, "")


if __name__ == "__main__":
    unittest.main()
