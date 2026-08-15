"""
Tests for app.security.verify_signature.

Run with: python3 -m unittest tests.test_security -v
(from the prsentry/ root — no pip install required, stdlib only)
"""
import hashlib
import hmac
import sys
import unittest
from pathlib import Path

# Allow running this file directly without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security import verify_signature, SignatureVerificationError


SECRET = "test-webhook-secret-do-not-use-in-prod"
PAYLOAD = b'{"action": "opened", "pull_request": {"number": 42}}'


def make_signature(payload: bytes, secret: str) -> str:
    """Helper: compute a valid GitHub-style signature header for a payload."""
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class TestVerifySignature(unittest.TestCase):

    def test_valid_signature_passes(self):
        sig = make_signature(PAYLOAD, SECRET)
        # Should not raise
        verify_signature(PAYLOAD, sig, SECRET)

    def test_tampered_payload_is_rejected(self):
        sig = make_signature(PAYLOAD, SECRET)
        tampered_payload = b'{"action": "opened", "pull_request": {"number": 99999}}'
        with self.assertRaises(SignatureVerificationError):
            verify_signature(tampered_payload, sig, SECRET)

    def test_wrong_secret_is_rejected(self):
        sig = make_signature(PAYLOAD, "a-different-secret")
        with self.assertRaises(SignatureVerificationError):
            verify_signature(PAYLOAD, sig, SECRET)

    def test_missing_header_is_rejected(self):
        with self.assertRaises(SignatureVerificationError):
            verify_signature(PAYLOAD, None, SECRET)

    def test_empty_header_is_rejected(self):
        with self.assertRaises(SignatureVerificationError):
            verify_signature(PAYLOAD, "", SECRET)

    def test_malformed_header_missing_prefix_is_rejected(self):
        # Real signature but without the required "sha256=" prefix
        digest = hmac.new(SECRET.encode("utf-8"), PAYLOAD, hashlib.sha256).hexdigest()
        with self.assertRaises(SignatureVerificationError):
            verify_signature(PAYLOAD, digest, SECRET)  # no "sha256=" prefix

    def test_sha1_header_is_rejected(self):
        # GitHub also sends a legacy X-Hub-Signature (sha1) header we should
        # never accept — sha1 is weaker and we only wired up sha256 support.
        digest = hmac.new(SECRET.encode("utf-8"), PAYLOAD, hashlib.sha1).hexdigest()
        with self.assertRaises(SignatureVerificationError):
            verify_signature(PAYLOAD, f"sha1={digest}", SECRET)


if __name__ == "__main__":
    unittest.main()
