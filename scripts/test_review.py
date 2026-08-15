"""
One-off manual test: fetch a real PR's diff and run it through Gemini,
printing the parsed findings. This is the first real end-to-end test of
app/llm_review.py — nothing about the Gemini call has been verified
before you run this.

Run with: python -m scripts.test_review

Requires everything scripts/test_fetch_diff.py needs, plus:
    GEMINI_API_KEY=<your key from https://aistudio.google.com/apikey>
"""
import os

from app.config import load_env, require_env
from app.github_auth import generate_jwt, get_installation_token
from app.github_client import fetch_pr_files, exclude_files, format_files_for_review
from app.llm_review import generate_review
from app.review_schema import ReviewParseError

load_env()  # reads GITHUB_APP_ID, GITHUB_PRIVATE_KEY_PATH, etc. from .env automatically

# Files that should never reach an LLM prompt, even if they end up in a diff.
EXCLUDED_FILES = {"GROUND_TRUTH.md"}


def main():
    try:
        required = require_env(
            "GITHUB_APP_ID", "GITHUB_PRIVATE_KEY_PATH", "GITHUB_INSTALLATION_ID",
            "GITHUB_OWNER", "GITHUB_REPO", "GEMINI_API_KEY",
        )
    except RuntimeError as exc:
        print(exc)
        return

    # GITHUB_PR_NUMBER is deliberately NOT in .env — it changes every time
    # you run this against a different PR, so it stays a per-run $env: value.
    pr_number = os.environ.get("GITHUB_PR_NUMBER")
    if not pr_number:
        print("Missing required env var: GITHUB_PR_NUMBER (set this per-run, e.g. $env:GITHUB_PR_NUMBER = \"1\")")
        return

    APP_ID = required["GITHUB_APP_ID"]
    PRIVATE_KEY_PATH = required["GITHUB_PRIVATE_KEY_PATH"]
    INSTALLATION_ID = required["GITHUB_INSTALLATION_ID"]
    OWNER = required["GITHUB_OWNER"]
    REPO = required["GITHUB_REPO"]

    with open(PRIVATE_KEY_PATH, "r") as f:
        private_key_pem = f.read()

    print("Authenticating...")
    app_jwt = generate_jwt(APP_ID, private_key_pem)
    token_data = get_installation_token(app_jwt, INSTALLATION_ID)
    installation_token = token_data["token"]

    print(f"Fetching files for {OWNER}/{REPO} PR #{pr_number}...")
    files = fetch_pr_files(installation_token, OWNER, REPO, int(pr_number))
    files = exclude_files(files, EXCLUDED_FILES)
    print(f"Reviewing {len(files)} file(s) after exclusions.\n")

    diff_text = format_files_for_review(files)

    print("Sending to Gemini for review...")
    try:
        result = generate_review(diff_text)
    except ReviewParseError as exc:
        print(f"Gemini's response didn't match the expected schema: {exc}")
        return
    except Exception as exc:
        print(f"Review generation failed: {type(exc).__name__}: {exc}")
        return

    print("\n" + "=" * 60)
    print(f"SUMMARY: {result.summary}")
    print("=" * 60)
    if not result.findings:
        print("No findings reported.")
    for i, finding in enumerate(result.findings, 1):
        print(f"\n[{i}] {finding.file} — {finding.severity.upper()}")
        if finding.line_hint:
            print(f"    Location: {finding.line_hint}")
        print(f"    {finding.description}")
    print("=" * 60)


if __name__ == "__main__":
    main()