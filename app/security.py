"""
GitHub webhook signature verification.

GitHub signs every webhook payload with HMAC-SHA256 using a secret you
configure when you register the GitHub App. Every request to our webhook
endpoint must be verified against this signature before we trust it —
otherwise anyone who finds our endpoint URL can send fake PR events.

Reference: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
"""
import hmac
import hashlib


class SignatureVerificationError(Exception):
    """Raised when a webhook payload's signature doesn't match."""


def verify_signature(payload_body: bytes, signature_header: str | None, secret: str) -> None:
    """
    Verify a GitHub webhook payload against its X-Hub-Signature-256 header.

    Args:
        payload_body: the raw request body, as bytes (NOT re-serialized JSON —
            it must be the exact bytes GitHub sent, or the HMAC won't match)
        signature_header: the value of the 'X-Hub-Signature-256' request header
        secret: the webhook secret configured in the GitHub App settings

    Raises:
        SignatureVerificationError: if the header is missing, malformed, or
            the computed signature doesn't match.
    """
    if not signature_header:
        raise SignatureVerificationError("Missing X-Hub-Signature-256 header")

    if not signature_header.startswith("sha256="):
        raise SignatureVerificationError(
            f"Unexpected signature format: {signature_header!r}"
        )

    expected_signature = signature_header.removeprefix("sha256=")

    computed_hmac = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    computed_signature = computed_hmac.hexdigest()

    # hmac.compare_digest prevents timing-attack side channels — a plain
    # `==` comparison leaks information about how many leading characters
    # matched via response-time differences. Never use `==` here.
    if not hmac.compare_digest(computed_signature, expected_signature):
        raise SignatureVerificationError("Signature does not match payload")
