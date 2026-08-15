"""
End-to-end pipeline: given a PR's identifying info, authenticate, fetch
the diff, generate a review, and post it back as a comment.

Designed to run as a FastAPI background task (see app/main.py) — the
webhook handler returns its response immediately, while this runs after,
since GitHub expects a webhook response within ~10 seconds and the LLM
call alone can easily take longer than that.

Deliberately swallows and logs all exceptions rather than raising: this
runs with nothing awaiting its result, so an unhandled exception here
would otherwise just vanish silently instead of being visible anywhere.
"""
import logging
import os

from app.github_auth import generate_jwt, get_installation_token
from app.github_client import exclude_files, fetch_pr_files, format_files_for_review
from app.github_comment import format_review_comment, post_issue_comment
from app.llm_review import generate_review
from app.review_schema import ReviewParseError

logger = logging.getLogger("prsentry")

# Files that should never reach an LLM prompt, even if present in a diff.
EXCLUDED_FILES = {"GROUND_TRUTH.md"}


def run_review_pipeline(installation_id: int, owner: str, repo: str, pr_number: int) -> None:
    try:
        app_id = os.environ["GITHUB_APP_ID"]
        private_key_path = os.environ["GITHUB_PRIVATE_KEY_PATH"]
    except KeyError as exc:
        logger.error("Pipeline cannot run — missing required env var: %s", exc)
        return

    try:
        with open(private_key_path, "r") as f:
            private_key_pem = f.read()

        app_jwt = generate_jwt(app_id, private_key_pem)
        token_data = get_installation_token(app_jwt, str(installation_id))
        installation_token = token_data["token"]

        files = fetch_pr_files(installation_token, owner, repo, pr_number)
        files = exclude_files(files, EXCLUDED_FILES)

        if not files:
            logger.info(
                "No reviewable files for %s/%s PR #%s after exclusions",
                owner, repo, pr_number,
            )
            return

        diff_text = format_files_for_review(files)
        review = generate_review(diff_text)

        comment_body = format_review_comment(review)
        post_issue_comment(installation_token, owner, repo, pr_number, comment_body)

        logger.info(
            "Posted review for %s/%s PR #%s: %d finding(s)",
            owner, repo, pr_number, len(review.findings),
        )

    except ReviewParseError as exc:
        logger.error(
            "Review parsing failed for %s/%s PR #%s: %s", owner, repo, pr_number, exc
        )
    except Exception:
        # Broad on purpose — this is the top of a background task, and an
        # unhandled exception here has nowhere else to surface.
        logger.exception("Pipeline failed for %s/%s PR #%s", owner, repo, pr_number)
