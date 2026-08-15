# PRSentry Test Fixtures

A small, deliberately toy codebase used only to generate real pull requests
for testing PRSentry's review quality against. Not real production code.

Branches:
- `main` — base state
- `feature/clean-addition` — a well-written addition, should NOT be flagged
- `feature/buggy-changes` — contains planted bugs, SHOULD be flagged

See `GROUND_TRUTH.md` for exactly what's planted where — that file is the
answer key for scoring PRSentry's precision/recall once it's running.
Don't let PRSentry "see" `GROUND_TRUTH.md` when testing — it would be
cheating off the answer key.
