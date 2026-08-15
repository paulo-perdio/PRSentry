"""
Fetch a pull request's changed files via GitHub's structured files endpoint,
and format them into review-ready text.

Reference: https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files
"""
import requests

GITHUB_API_BASE = "https://api.github.com"

# GitHub caps this endpoint at 100 results per page and 3000 files total per PR.
PER_PAGE = 100


def fetch_pr_files(installation_token: str, owner: str, repo: str, pr_number: int) -> list[dict]:
    """
    Fetch every changed file for a PR, handling pagination.

    Each returned dict includes (per GitHub's API): 'filename', 'status'
    ('added'/'modified'/'removed'/'renamed'), 'additions', 'deletions',
    and 'patch' (the unified diff text for that file — absent for binary
    files or files GitHub considers too large to diff).
    """
    headers = {
        "Authorization": f"Bearer {installation_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"

    all_files = []
    page = 1
    while True:
        response = requests.get(
            url, headers=headers,
            params={"per_page": PER_PAGE, "page": page},
            timeout=10,
        )
        response.raise_for_status()
        batch = response.json()
        all_files.extend(batch)
        if len(batch) < PER_PAGE:
            break  # last page reached
        page += 1

    return all_files


def exclude_files(files: list[dict], excluded_filenames: set[str]) -> list[dict]:
    """
    Drop any file whose name matches excluded_filenames before it ever
    reaches formatting or an LLM prompt.

    Exists specifically so files like GROUND_TRUTH.md (or, in a real repo,
    things like secrets/answer keys/internal notes) can never leak into a
    review even if they accidentally end up inside a PR diff — belt and
    suspenders on top of keeping them out of the repo in the first place.
    """
    return [f for f in files if f.get("filename") not in excluded_filenames]


def format_files_for_review(files: list[dict]) -> str:
    """
    Turn GitHub's structured file list into readable text suitable for
    feeding to an LLM review prompt (that's the next step, not this one).

    Files with no 'patch' field (binary files, or files GitHub deemed too
    large) are noted but not expanded, since there's no diff text to show.
    """
    if not files:
        return "No files changed."

    sections = []
    for f in files:
        filename = f.get("filename", "<unknown file>")
        status = f.get("status", "unknown")
        additions = f.get("additions", 0)
        deletions = f.get("deletions", 0)

        header = f"### {filename} ({status}, +{additions}/-{deletions})"

        if status == "renamed" and f.get("previous_filename"):
            header += f"\n(renamed from {f['previous_filename']})"

        patch = f.get("patch")
        if patch:
            sections.append(f"{header}\n```diff\n{patch}\n```")
        else:
            sections.append(f"{header}\n(no diff available — binary or too large to display)")

    return "\n\n".join(sections)
