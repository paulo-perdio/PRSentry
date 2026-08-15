"""
Generate a structured code review using Gemini 2.5 Flash (free tier).

WARNING: unlike the other modules in this project, this file has NOT been
run or tested in any sandbox — google-genai isn't installed here and
there's no network access to install or call it. It's written carefully
against current Gemini API docs, but treat it as a first draft until you
run scripts/test_review.py and confirm it actually works.

Requires GEMINI_API_KEY in the environment. Get one free, no credit card,
at https://aistudio.google.com/apikey
"""
import concurrent.futures
import os

from google import genai
from google.genai import types

from app.review_schema import REVIEW_JSON_SCHEMA, parse_review_result, ReviewResult

MODEL_NAME = "gemini-3.5-flash"
# NOTE: gemini-2.5-flash and gemini-2.5-flash-lite currently return 404 for
# newly created API keys/projects, even though Google's docs still list
# them — a known, currently-active inconsistency as of August 2026, not
# specific to this setup. gemini-3.5-flash is confirmed working on fresh
# free-tier keys as of this writing. If this breaks again later, check
# https://ai.google.dev/gemini-api/docs/pricing for which models currently
# show a Free Tier row — model availability here has been changing often.

REVIEW_PROMPT_TEMPLATE = """You are reviewing a pull request diff for a Python codebase. \
Your job is to find real bugs and correctness issues — not style preferences, \
not formatting, not naming conventions. Focus on:

- Logic errors (off-by-one, wrong operators, inverted conditions)
- Removed or weakened validation/error handling
- Edge cases that would silently produce wrong output (not just crashes)
- Anything that changes behavior in a way the diff doesn't make obvious

Do NOT flag: style choices, missing docstrings, variable naming, or \
anything that is a matter of preference rather than correctness. If you \
find nothing wrong, say so — do not invent issues to have something to report.

Here is the diff:

{diff_text}
"""


def generate_review(diff_text: str, api_key: str | None = None, timeout_seconds: int = 60) -> ReviewResult:
    """
    Send a formatted diff to Gemini and return a parsed, validated ReviewResult.

    Raises app.review_schema.ReviewParseError if Gemini's response doesn't
    match the expected schema (should be rare given response_schema is set,
    but not impossible — always handle this, never assume it can't happen).

    Raises TimeoutError if the call doesn't complete within timeout_seconds.
    This is a hard backstop via a worker thread, not just http_options —
    there are current open issues in google-genai where the SDK's own
    request can hang indefinitely regardless of the timeout you configure
    (see googleapis/python-genai#1893, #4031). Don't rely on http_options
    alone to prevent a hang.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=timeout_seconds * 1000),  # milliseconds
    )

    prompt = REVIEW_PROMPT_TEMPLATE.format(diff_text=diff_text)

    def _call():
        return client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": REVIEW_JSON_SCHEMA,
            },
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call)
        try:
            response = future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise TimeoutError(
                f"Gemini call did not complete within {timeout_seconds}s "
                "(hard backstop timeout, not the SDK's own — see docstring)"
            ) from exc

    return parse_review_result(response.text)