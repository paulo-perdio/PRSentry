"""
Run the full eval suite: for every entry in eval/ground_truth.json, find
its PR on GitHub, run a review, score it, and print a results table with
aggregate precision/recall/F1.

Run with: python -m scripts.run_eval

Requires the same env vars as scripts/test_review.py (GITHUB_APP_ID,
GITHUB_PRIVATE_KEY_PATH, GITHUB_INSTALLATION_ID, GITHUB_OWNER,
GITHUB_REPO, GEMINI_API_KEY) — GITHUB_PR_NUMBER is NOT needed here, since
this script finds each PR's number itself via the GitHub API.
"""
import json
import time
from pathlib import Path

import requests

from app.config import load_env, require_env
from app.eval_scoring import compute_metrics, score_pr
from app.github_auth import generate_jwt, get_installation_token
from app.github_client import exclude_files, fetch_pr_files, format_files_for_review
from app.llm_review import generate_review
from app.review_schema import ReviewParseError

load_env()  # reads .env automatically — no more manual $env: setup needed

GROUND_TRUTH_PATH = Path(__file__).resolve().parent.parent / "eval" / "ground_truth.json"
EXCLUDED_FILES = {"GROUND_TRUTH.md"}

GITHUB_API_BASE = "https://api.github.com"


def find_pr_number_for_branch(installation_token: str, owner: str, repo: str, branch: str) -> int | None:
    """Look up the open PR number for a given head branch, or None if not found."""
    headers = {
        "Authorization": f"Bearer {installation_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"
    response = requests.get(
        url, headers=headers,
        params={"head": f"{owner}:{branch}", "state": "open"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()
    return results[0]["number"] if results else None


def main():
    try:
        required = require_env(
            "GITHUB_APP_ID", "GITHUB_PRIVATE_KEY_PATH", "GITHUB_INSTALLATION_ID",
            "GITHUB_OWNER", "GITHUB_REPO", "GEMINI_API_KEY",
        )
    except RuntimeError as exc:
        print(exc)
        return

    with open(GROUND_TRUTH_PATH, "r") as f:
        manifest = json.load(f)

    with open(required["GITHUB_PRIVATE_KEY_PATH"], "r") as f:
        private_key_pem = f.read()

    app_jwt = generate_jwt(required["GITHUB_APP_ID"], private_key_pem)
    token_data = get_installation_token(app_jwt, required["GITHUB_INSTALLATION_ID"])
    installation_token = token_data["token"]

    owner = required["GITHUB_OWNER"]
    repo = required["GITHUB_REPO"]

    scores = []
    print(f"{'BRANCH':<40} {'EXPECTED':<10} {'RESULT':<20} {'FINDINGS'}")
    print("-" * 90)

    for entry in manifest["entries"]:
        branch = entry["branch"]
        expected_has_bug = entry["expected_has_bug"]

        pr_number = find_pr_number_for_branch(installation_token, owner, repo, branch)
        if pr_number is None:
            print(f"{branch:<40} {'—':<10} {'NO OPEN PR FOUND':<20} skipping")
            continue

        try:
            files = fetch_pr_files(installation_token, owner, repo, pr_number)
            files = exclude_files(files, EXCLUDED_FILES)
            diff_text = format_files_for_review(files)
            review = generate_review(diff_text)
            finding_count = len(review.findings)
        except ReviewParseError as exc:
            print(f"{branch:<40} {'—':<10} {'REVIEW PARSE ERROR':<20} {exc}")
            continue
        except Exception as exc:
            error_text = str(exc)
            if "RESOURCE_EXHAUSTED" in error_text or "GenerateRequestsPerDayPerProjectPerModel" in error_text:
                print(f"{branch:<40} {'—':<10} {'DAILY QUOTA EXHAUSTED':<20}")
                print(
                    "\nStopping the run — this is a per-day cap on the free tier, "
                    "not a short cooldown. Retrying immediately will just repeat this "
                    "for every remaining entry. Wait for the daily reset (roughly "
                    "midnight Pacific time) and re-run, or switch MODEL_NAME in "
                    "app/llm_review.py to a model with a higher free-tier daily quota."
                )
                break
            print(f"{branch:<40} {'—':<10} {'ERROR':<20} {type(exc).__name__}: {exc}")
            continue

        score = score_pr(branch, expected_has_bug, finding_count)
        scores.append(score)

        result_label = "CORRECT" if score.correct else f"WRONG ({score.outcome})"
        print(f"{branch:<40} {str(expected_has_bug):<10} {result_label:<20} {finding_count}")

        # Small delay to stay comfortably under free-tier rate limits across
        # several sequential calls in one run.
        time.sleep(2)

    print("-" * 90)
    metrics = compute_metrics(scores)
    print(f"\nScored {metrics['total']} / {len(manifest['entries'])} entries "
          f"(entries with no open PR were skipped, not counted as failures)\n")
    print(f"Precision: {metrics['precision']}")
    print(f"Recall:    {metrics['recall']}")
    print(f"F1:        {metrics['f1']}")
    print(f"Accuracy:  {metrics['accuracy']}")
    print(f"TP={metrics['true_positives']} TN={metrics['true_negatives']} "
          f"FP={metrics['false_positives']} FN={metrics['false_negatives']}")


if __name__ == "__main__":
    main()