"""
Tests for app.eval_scoring — fully offline, no dependencies.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.eval_scoring import score_pr, compute_metrics


class TestScorePR(unittest.TestCase):

    def test_true_positive(self):
        s = score_pr("buggy-branch", expected_has_bug=True, finding_count=2)
        self.assertEqual(s.outcome, "true_positive")
        self.assertTrue(s.correct)

    def test_true_negative(self):
        s = score_pr("clean-branch", expected_has_bug=False, finding_count=0)
        self.assertEqual(s.outcome, "true_negative")
        self.assertTrue(s.correct)

    def test_false_positive(self):
        s = score_pr("clean-branch", expected_has_bug=False, finding_count=1)
        self.assertEqual(s.outcome, "false_positive")
        self.assertFalse(s.correct)

    def test_false_negative(self):
        s = score_pr("buggy-branch", expected_has_bug=True, finding_count=0)
        self.assertEqual(s.outcome, "false_negative")
        self.assertFalse(s.correct)


class TestComputeMetrics(unittest.TestCase):

    def test_perfect_score(self):
        scores = [
            score_pr("a", True, 2),
            score_pr("b", False, 0),
            score_pr("c", True, 1),
        ]
        metrics = compute_metrics(scores)
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["f1"], 1.0)
        self.assertEqual(metrics["accuracy"], 1.0)

    def test_one_false_positive_hurts_precision_not_recall(self):
        scores = [
            score_pr("a", True, 2),    # TP
            score_pr("b", False, 1),   # FP — clean branch, but findings reported
        ]
        metrics = compute_metrics(scores)
        self.assertEqual(metrics["precision"], 0.5)  # 1 TP / (1 TP + 1 FP)
        self.assertEqual(metrics["recall"], 1.0)       # no false negatives

    def test_one_false_negative_hurts_recall_not_precision(self):
        scores = [
            score_pr("a", True, 0),    # FN — buggy branch, missed
            score_pr("b", False, 0),   # TN
        ]
        metrics = compute_metrics(scores)
        self.assertEqual(metrics["recall"], 0.0)
        self.assertEqual(metrics["precision"], 0.0)  # no TPs and no FPs -> defined as 0.0

    def test_empty_list_does_not_crash(self):
        metrics = compute_metrics([])
        self.assertEqual(metrics["total"], 0)
        self.assertEqual(metrics["accuracy"], 0.0)

    def test_counts_are_correct(self):
        scores = [
            score_pr("a", True, 1),   # TP
            score_pr("b", True, 0),   # FN
            score_pr("c", False, 0),  # TN
            score_pr("d", False, 2),  # FP
        ]
        metrics = compute_metrics(scores)
        self.assertEqual(metrics["true_positives"], 1)
        self.assertEqual(metrics["false_negatives"], 1)
        self.assertEqual(metrics["true_negatives"], 1)
        self.assertEqual(metrics["false_positives"], 1)
        self.assertEqual(metrics["total"], 4)


if __name__ == "__main__":
    unittest.main()
