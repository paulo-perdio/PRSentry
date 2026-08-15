"""
Tests for app.github_comment.format_review_comment. post_issue_comment
itself is not tested here — real network call to GitHub.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.github_comment import format_review_comment
from app.review_schema import Finding, ReviewResult


class TestFormatReviewComment(unittest.TestCase):

    def test_no_findings_says_no_issues(self):
        review = ReviewResult(summary="Looks good.", findings=[])
        result = format_review_comment(review)
        self.assertIn("No issues found.", result)
        self.assertIn("Looks good.", result)

    def test_findings_include_severity_and_file(self):
        review = ReviewResult(
            summary="Two issues found.",
            findings=[
                Finding(file="inventory.py", severity="high",
                        description="Off-by-one bug", line_hint="find_item_index"),
                Finding(file="inventory.py", severity="medium",
                        description="Missing validation"),
            ],
        )
        result = format_review_comment(review)
        self.assertIn("HIGH", result)
        self.assertIn("MEDIUM", result)
        self.assertIn("inventory.py", result)
        self.assertIn("Off-by-one bug", result)
        self.assertIn("find_item_index", result)

    def test_missing_line_hint_is_omitted_cleanly(self):
        review = ReviewResult(
            summary="x",
            findings=[Finding(file="a.py", severity="low", description="minor thing")],
        )
        result = format_review_comment(review)
        self.assertNotIn("**Location:**", result)  # no line_hint given, shouldn't appear

    def test_includes_disclaimer_footer(self):
        review = ReviewResult(summary="x", findings=[])
        result = format_review_comment(review)
        self.assertIn("verify findings before acting on them", result)


if __name__ == "__main__":
    unittest.main()
