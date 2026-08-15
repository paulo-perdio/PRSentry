# PRSentry

An AI-powered GitHub PR reviewer that automatically reviews pull requests when they're opened or updated, and posts findings back as a comment — no manual invocation required.

## What it does

PRSentry is a GitHub App. Once installed on a repository, it:

1. Listens for `pull_request` webhook events (`opened`, `reopened`, `synchronize`)
2. Verifies each webhook's HMAC-SHA256 signature before trusting it
3. Authenticates to GitHub's API as the App (JWT → installation access token)
4. Fetches the PR's changed files via GitHub's structured files endpoint
5. Sends the diff to an LLM (Gemini) with a review-focused prompt, constrained to a structured JSON output schema
6. Posts the findings back as a comment on the PR — automatically, as a background task, so the original webhook response stays fast

## Why

Most "AI PR reviewer" side projects are demos: point them at one PR, watch it print something plausible-looking, done. PRSentry is built around a different question — **is the review actually any good, and how would you know?** That's the part this project treats as the actual engineering problem, not an afterthought.

## Eval results

Scored against an 11-entry labeled test set (`eval/ground_truth.json`), covering both canonical bug patterns and deliberately harder cases — a cross-file semantic bug, a subtle non-idiom-based rounding error, and a "looks suspicious but is actually correct" trap designed to test false-positive resistance rather than just recall.

| Metric | Value |
|---|---|
| Precision | 1.0 |
| Recall | 0.857 |
| F1 | 0.923 |
| Accuracy | 0.909 |
| TP / TN / FP / FN | 6 / 4 / 0 / 1 |

**The one miss is diagnosed, not a mystery.** The missed case (`feature/multi-file-tax-bug`) involves a function called with the wrong argument semantics (a 0–1 fraction passed where a 0–100 percent was expected) — but the function whose contract is being violated lives in a *different, unchanged file*, outside the PR's diff. PRSentry currently reviews diffs in isolation, with no visibility into the implementation of functions called from elsewhere in the codebase. That's a real, specific architectural limitation, not a model failure — the model was never shown the information it would have needed to catch it.

**A separate, informal observation:** a re-run of one previously-clean case (`feature/clean-addition`) produced a false positive in a later pass on the same unchanged branch — a reminder that LLM output is non-deterministic, and a single pass through an eval set is a snapshot, not a guaranteed stable rate. Run-to-run consistency wasn't formally measured here and is a natural next step.

**Model:** Gemini 3.5 Flash (free tier). Free-tier daily quotas (20 requests/day at time of testing) constrained how often the full eval could be re-run — worth knowing if you're extending this yourself.

## Architecture

```
GitHub PR event
      │
      ▼
Webhook (FastAPI) ── signature verified (HMAC-SHA256)
      │
      ▼
GitHub App auth ── JWT (RS256, private key) → installation access token
      │
      ▼
Fetch PR files ── GitHub structured files API, paginated
      │
      ▼
Exclude sensitive files (e.g. answer-key files in test fixtures)
      │
      ▼
Format diff for review
      │
      ▼
LLM review ── Gemini, structured JSON output, schema-validated
      │
      ▼
Post comment ── GitHub issue-comment API
```

Runs as a background task after the webhook responds, so review latency (which includes an LLM call) never blocks GitHub's expected fast webhook response.

## Tech stack

Python · FastAPI · uvicorn · PyJWT + `cryptography` (GitHub App auth) · `google-genai` (Gemini) · `requests` · `python-dotenv`

## Known limitations

- **Diff-only context** — no visibility into unchanged files' contents, even when called functions live there (see eval results above)
- **Single summary comment**, not inline diff comments — inline comments require calculating exact diff-line positions from patch hunks, a deliberate scope cut, not an oversight
- **Small eval set (n=11)** — enough to catch real, specific failure modes, not enough for a statistically rigorous precision/recall claim at scale
- **No handling yet** for very large diffs approaching context limits, or rapid successive pushes to the same PR in quick succession
- **Free-tier LLM rate limits** cap how frequently this can be run in bursts

## Setup

1. Create a GitHub App (Settings → Developer settings → GitHub Apps) with:
   - Webhook active, subscribed to the `Pull request` event
   - Repository permissions: `Pull requests: Read & write`, `Contents: Read-only`
   - A generated private key (`.pem`)
2. Install the App on the repository you want reviewed
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in: `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY_PATH`, `GITHUB_INSTALLATION_ID`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_OWNER`, `GITHUB_REPO`, `GEMINI_API_KEY`
5. For local development, expose your local server with a tunnel (e.g. `ngrok http 8000`) and set that URL as the GitHub App's webhook URL
6. `python -m uvicorn app.main:app --reload --port 8000`

## Testing

```
python -m unittest discover tests -v
```

Manual end-to-end scripts (`scripts/`) exist for testing each stage independently — auth, diff fetching, single-PR review, and the full eval suite (`scripts/run_eval.py`).