"""
PRSentry webhook receiver.

Run locally with:
    uvicorn app.main:app --reload --port 8000

Requires GITHUB_WEBHOOK_SECRET to be set in the environment first — this
must match the webhook secret you entered in the GitHub App settings.
"""
import logging
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from app.config import load_env
from app.pipeline import run_review_pipeline
from app.security import SignatureVerificationError, verify_signature

load_env()  # reads .env automatically — no more manual $env: setup needed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prsentry")

app = FastAPI()

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")

# Only these actions warrant a review. "closed" (without reopening),
# "labeled", "assigned", etc. all also arrive as pull_request events but
# don't represent new/changed code worth reviewing.
REVIEWABLE_ACTIONS = {"opened", "reopened", "synchronize"}


@app.get("/")
def health_check():
    """Simple liveness check — hit this in a browser to confirm the server is up."""
    return {"status": "ok", "service": "prsentry"}


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    if not WEBHOOK_SECRET:
        # Fail loudly at request time rather than silently accepting
        # unverifiable webhooks if the env var was never set.
        raise HTTPException(
            status_code=500,
            detail="GITHUB_WEBHOOK_SECRET is not configured on this server",
        )

    # Read the raw bytes BEFORE any JSON parsing — verify_signature needs
    # the exact bytes GitHub signed, not a re-serialized version of them.
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    try:
        verify_signature(raw_body, signature_header, WEBHOOK_SECRET)
    except SignatureVerificationError as exc:
        logger.warning("Rejected webhook with invalid signature: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid signature") from exc

    event_type = request.headers.get("X-GitHub-Event", "unknown")
    payload = await request.json()  # safe: Starlette caches the body we already read
    action = payload.get("action", "unknown")
    pr_number = payload.get("pull_request", {}).get("number")

    logger.info(
        "Verified webhook received: event=%s action=%s pr=%s",
        event_type, action, pr_number,
    )

    if event_type == "pull_request" and action in REVIEWABLE_ACTIONS:
        installation_id = payload.get("installation", {}).get("id")
        owner = payload.get("repository", {}).get("owner", {}).get("login")
        repo = payload.get("repository", {}).get("name")

        if not all([installation_id, owner, repo, pr_number]):
            logger.warning(
                "Skipping review — payload missing expected fields "
                "(installation_id=%s owner=%s repo=%s pr_number=%s)",
                installation_id, owner, repo, pr_number,
            )
        else:
            # Runs AFTER this response is sent — keeps the webhook response
            # fast regardless of how long the LLM call takes.
            background_tasks.add_task(
                run_review_pipeline, installation_id, owner, repo, pr_number
            )
            logger.info("Queued review pipeline for %s/%s PR #%s", owner, repo, pr_number)

    return {"status": "received", "event": event_type, "action": action}
