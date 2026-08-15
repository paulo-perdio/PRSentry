"""
One-off manual test: fetch a real PR's diff from your test-repo and print
the formatted result, to confirm app/github_client.py works end-to-end.

Run with: python -m scripts.test_fetch_diff

Requires the same env vars as scripts/test_auth.py, plus:
    GITHUB_OWNER=paulo-perdio
    GITHUB_REPO=test-repo
    GITHUB_PR_NUMBER=1        (or whichever PR number you want to fetch)
"""
import os

from app.github_auth import generate_jwt, get_installation_token
from app.github_client import fetch_pr_files, format_files_for_review

APP_ID = os.environ.get("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.environ.get("GITHUB_PRIVATE_KEY_PATH")
INSTALLATION_ID = os.environ.get("GITHUB_INSTALLATION_ID")
OWNER = os.environ.get("GITHUB_OWNER")
REPO = os.environ.get("GITHUB_REPO")
PR_NUMBER = os.environ.get("GITHUB_PR_NUMBER")


def main():
    required = {
        "GITHUB_APP_ID": APP_ID,
        "GITHUB_PRIVATE_KEY_PATH": PRIVATE_KEY_PATH,
        "GITHUB_INSTALLATION_ID": INSTALLATION_ID,
        "GITHUB_OWNER": OWNER,
        "GITHUB_REPO": REPO,
        "GITHUB_PR_NUMBER": PR_NUMBER,
    }
    missing = [name for name, val in required.items() if not val]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}")
        return

    with open(PRIVATE_KEY_PATH, "r") as f:
        private_key_pem = f.read()

    print("Authenticating...")
    app_jwt = generate_jwt(APP_ID, private_key_pem)
    token_data = get_installation_token(app_jwt, INSTALLATION_ID)
    installation_token = token_data["token"]
    print("Got installation token.\n")

    print(f"Fetching files for {OWNER}/{REPO} PR #{PR_NUMBER}...")
    files = fetch_pr_files(installation_token, OWNER, REPO, int(PR_NUMBER))
    print(f"Found {len(files)} changed file(s).\n")

    print("=" * 60)
    print(format_files_for_review(files))
    print("=" * 60)


if __name__ == "__main__":
    main()
