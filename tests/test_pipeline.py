"""
Tests for app.pipeline.run_review_pipeline.

Only the fail-safe behavior is tested offline — the rest of the pipeline
is a real network/auth/LLM chain already covered individually by
test_security, test_github_auth, test_github_client, test_review_schema,
and test_github_comment. This test exists to prove the pipeline doesn't
raise and crash the background task when misconfigured, since a raised
exception in a FastAPI background task has nowhere visible to go.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline import run_review_pipeline


class TestRunReviewPipelineFailsSafe(unittest.TestCase):

    def test_missing_env_vars_does_not_raise(self):
        with patch.dict("os.environ", {}, clear=True):
            try:
                run_review_pipeline(installation_id=1, owner="x", repo="y", pr_number=1)
            except Exception as exc:  # noqa: BLE001 — the point is nothing should escape
                self.fail(f"run_review_pipeline raised unexpectedly: {exc}")

    def test_missing_private_key_path_does_not_raise(self):
        with patch.dict("os.environ", {"GITHUB_APP_ID": "123"}, clear=True):
            try:
                run_review_pipeline(installation_id=1, owner="x", repo="y", pr_number=1)
            except Exception as exc:  # noqa: BLE001
                self.fail(f"run_review_pipeline raised unexpectedly: {exc}")


if __name__ == "__main__":
    unittest.main()
