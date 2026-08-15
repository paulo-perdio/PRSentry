"""
Eval scoring for PRSentry: binary per-PR classification only.

Scope, stated plainly: this measures whether a review correctly predicts
"this PR has at least one real issue" vs "this PR is clean" — NOT whether
individual findings match the exact expected bug. Matching specific
findings to specific expected bugs reliably would need either manual
labeling per finding or a second judge model, neither of which this does.
For a small fixture set, eyeball the findings themselves for correctness;
this module only automates the coarser "flagged vs not" question.
"""
from dataclasses import dataclass


@dataclass
class PRScore:
    branch: str
    expected_has_bug: bool
    predicted_has_bug: bool
    finding_count: int

    @property
    def correct(self) -> bool:
        return self.expected_has_bug == self.predicted_has_bug

    @property
    def outcome(self) -> str:
        """One of: true_positive, true_negative, false_positive, false_negative."""
        if self.expected_has_bug and self.predicted_has_bug:
            return "true_positive"
        if not self.expected_has_bug and not self.predicted_has_bug:
            return "true_negative"
        if not self.expected_has_bug and self.predicted_has_bug:
            return "false_positive"
        return "false_negative"


def score_pr(branch: str, expected_has_bug: bool, finding_count: int) -> PRScore:
    return PRScore(
        branch=branch,
        expected_has_bug=expected_has_bug,
        predicted_has_bug=finding_count > 0,
        finding_count=finding_count,
    )


def compute_metrics(scores: list[PRScore]) -> dict:
    """
    Standard binary classification metrics over a list of PRScores.
    Returns 0.0 for precision/recall/f1 when the denominator is 0, rather
    than raising — an empty or degenerate eval set shouldn't crash this.
    """
    tp = sum(1 for s in scores if s.outcome == "true_positive")
    tn = sum(1 for s in scores if s.outcome == "true_negative")
    fp = sum(1 for s in scores if s.outcome == "false_positive")
    fn = sum(1 for s in scores if s.outcome == "false_negative")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(scores) if scores else 0.0

    return {
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "accuracy": round(accuracy, 3),
        "total": len(scores),
    }
