"""
Tests for app.github_client.format_files_for_review.

fetch_pr_files() itself is NOT tested here — it's a real network call to
GitHub's API, so it gets verified on your machine via scripts/test_fetch_diff.py
instead. This file only covers the formatting logic, using fake payloads
shaped like GitHub's real response.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.github_client import format_files_for_review, exclude_files


class TestExcludeFiles(unittest.TestCase):

    def test_excluded_file_is_removed(self):
        files = [
            {"filename": "GROUND_TRUTH.md"},
            {"filename": "inventory.py"},
        ]
        result = exclude_files(files, {"GROUND_TRUTH.md"})
        filenames = [f["filename"] for f in result]
        self.assertNotIn("GROUND_TRUTH.md", filenames)
        self.assertIn("inventory.py", filenames)

    def test_no_matches_leaves_list_unchanged(self):
        files = [{"filename": "inventory.py"}]
        result = exclude_files(files, {"GROUND_TRUTH.md"})
        self.assertEqual(result, files)

    def test_empty_exclusion_set_leaves_everything(self):
        files = [{"filename": "a.py"}, {"filename": "b.py"}]
        result = exclude_files(files, set())
        self.assertEqual(len(result), 2)

    def test_excludes_multiple_matches(self):
        files = [
            {"filename": "GROUND_TRUTH.md"},
            {"filename": "SECRETS.md"},
            {"filename": "inventory.py"},
        ]
        result = exclude_files(files, {"GROUND_TRUTH.md", "SECRETS.md"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["filename"], "inventory.py")


class TestFormatFilesForReview(unittest.TestCase):

    def test_empty_list_returns_no_files_message(self):
        result = format_files_for_review([])
        self.assertEqual(result, "No files changed.")

    def test_modified_file_with_patch(self):
        files = [{
            "filename": "inventory.py",
            "status": "modified",
            "additions": 3,
            "deletions": 1,
            "patch": "@@ -10,3 +10,5 @@\n def apply_discount(price, percent):\n-    raise ValueError\n+    return price",
        }]
        result = format_files_for_review(files)
        self.assertIn("inventory.py (modified, +3/-1)", result)
        self.assertIn("```diff", result)
        self.assertIn("apply_discount", result)

    def test_binary_file_with_no_patch(self):
        files = [{
            "filename": "logo.png",
            "status": "modified",
            "additions": 0,
            "deletions": 0,
            # no 'patch' key at all — this is what GitHub actually omits for binaries
        }]
        result = format_files_for_review(files)
        self.assertIn("logo.png", result)
        self.assertIn("no diff available", result)
        self.assertNotIn("```diff", result)  # shouldn't render an empty diff block

    def test_renamed_file_shows_previous_name(self):
        files = [{
            "filename": "new_name.py",
            "status": "renamed",
            "previous_filename": "old_name.py",
            "additions": 0,
            "deletions": 0,
            "patch": "@@ -1 +1 @@\n-old\n+new",
        }]
        result = format_files_for_review(files)
        self.assertIn("renamed from old_name.py", result)

    def test_multiple_files_are_all_included(self):
        files = [
            {"filename": "a.py", "status": "modified", "additions": 1, "deletions": 0, "patch": "diff a"},
            {"filename": "b.py", "status": "added", "additions": 5, "deletions": 0, "patch": "diff b"},
        ]
        result = format_files_for_review(files)
        self.assertIn("a.py", result)
        self.assertIn("b.py", result)

    def test_missing_optional_fields_do_not_crash(self):
        # Defensive: a minimal/malformed-ish entry shouldn't blow up formatting
        files = [{"filename": "mystery.py"}]
        result = format_files_for_review(files)
        self.assertIn("mystery.py", result)


if __name__ == "__main__":
    unittest.main()
