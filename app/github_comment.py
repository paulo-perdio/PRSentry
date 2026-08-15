"""
Post review results back to a PR as a comment.

Uses the general issue-comment endpoint (PRs are 'issues' in GitHub's API
for commenting purposes) rather than inline diff comments. Inline comments
require calculating exact diff-line positions from the patch hunks, which
is meaningfully more complex and error-prone — a deliberate scope cut for
now, not an oversight. A single summary comment is a reasonable v1.
"""
import requests

from app.review_schema import ReviewResult

GITHUB_API_BASE = "https://api.github.com"

SEVERITY_EMOJI = {"high": "\U0001F534", "medium": "\U0001F7E1", "low": "\U0001F535"}


def format_review_comment(review: ReviewResult) -> str:
    """Format a ReviewResult as a GitHub-flavored markdown comment."""
    lines = ["## PRSentry Review", "", review.summary, ""]

    if not review.findings:
        lines.append("No issues found.")
    else:
        for finding in review.findings:
            emoji = SEVERITY_EMOJI.get(finding.severity, "\u26AA")
            lines.append(f"### {emoji} {finding.severity.upper()} \u2014 `{finding.file}`")
            if finding.line_hint:
                lines.append(f"**Location:** {finding.line_hint}")
            lines.append(finding.description)
            lines.append("")

    lines.append("---")
    lines.append("*Automated review \u2014 verify findings before acting on them.*")
    return "\n".join(lines)


def post_issue_comment(
    installation_token: str, owner: str, repo: str, pr_number: int, body: str
) -> dict:
    """Post `body` as a new comment on the PR's conversation tab."""
    headers = {
        "Authorization": f"Bearer {installation_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    response = requests.post(url, headers=headers, json={"body": body}, timeout=10)
    response.raise_for_status()
    return response.json()
