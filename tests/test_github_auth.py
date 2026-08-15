"""
Tests for app.github_auth.generate_jwt.

Uses a throwaway RSA keypair generated at test time — never touches your
real GitHub App private key. This verifies the JWT-signing logic is
correct; it can't test get_installation_token, since that requires a real
network call to GitHub's API.

Run with: python3 -m unittest tests.test_github_auth -v
"""
import sys
import time
import unittest
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.github_auth import generate_jwt


def make_test_keypair():
    """Generate a throwaway RSA keypair, PEM-encoded, for test use only."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


class TestGenerateJWT(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.private_pem, cls.public_pem = make_test_keypair()

    def test_jwt_verifies_against_matching_public_key(self):
        token = generate_jwt("123456", self.private_pem)
        # If this doesn't raise, the signature is valid for this keypair —
        # the core thing we actually need to be true.
        decoded = jwt.decode(token, self.public_pem, algorithms=["RS256"])
        self.assertEqual(decoded["iss"], "123456")

    def test_jwt_rejects_wrong_public_key(self):
        token = generate_jwt("123456", self.private_pem)
        _, wrong_public_pem = make_test_keypair()  # a different, unrelated keypair
        with self.assertRaises(jwt.InvalidSignatureError):
            jwt.decode(token, wrong_public_pem, algorithms=["RS256"])

    def test_expiry_is_within_githubs_ten_minute_limit(self):
        token = generate_jwt("123456", self.private_pem)
        decoded = jwt.decode(token, self.public_pem, algorithms=["RS256"])
        lifetime_seconds = decoded["exp"] - decoded["iat"]
        self.assertLessEqual(lifetime_seconds, 10 * 60)

    def test_iat_is_backdated_for_clock_drift_tolerance(self):
        before = int(time.time())
        token = generate_jwt("123456", self.private_pem)
        decoded = jwt.decode(token, self.public_pem, algorithms=["RS256"])
        # iat should be slightly in the past relative to when we called it
        self.assertLess(decoded["iat"], before)


if __name__ == "__main__":
    unittest.main()
