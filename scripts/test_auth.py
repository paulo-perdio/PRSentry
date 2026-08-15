"""
One-off manual test: confirm we can actually get a real installation
token from GitHub. Not part of the app itself — just a way to verify
app/github_auth.py works end-to-end before wiring it into main.py.

Run with: python -m scripts.test_auth

Requires in your .env (or set as environment variables first):
    GITHUB_APP_ID=4555875
    GITHUB_PRIVATE_KEY_PATH=./paulo-prsentry-dev.2026-08-11.private-key.pem
    GITHUB_INSTALLATION_ID=<see instructions below to find this>
"""
import os

from app.github_auth import generate_jwt, get_installation_token

APP_ID = os.environ.get("GITHUB_APP_ID")
PRIVATE_KEY_PATH = os.environ.get("GITHUB_PRIVATE_KEY_PATH")
INSTALLATION_ID = os.environ.get("GITHUB_INSTALLATION_ID")


def main():
    missing = [
        name for name, val in [
            ("GITHUB_APP_ID", APP_ID),
            ("GITHUB_PRIVATE_KEY_PATH", PRIVATE_KEY_PATH),
            ("GITHUB_INSTALLATION_ID", INSTALLATION_ID),
        ] if not val
    ]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}")
        return

    with open(PRIVATE_KEY_PATH, "r") as f:
        private_key_pem = f.read()

    print("Generating App JWT...")
    app_jwt = generate_jwt(APP_ID, private_key_pem)
    print(f"JWT generated ({len(app_jwt)} chars) — not printing full value.")

    print("Exchanging JWT for installation access token...")
    result = get_installation_token(app_jwt, INSTALLATION_ID)

    # Deliberately NOT printing result['token'] — it's a real, usable
    # credential (short-lived, but still). Only confirm it worked.
    print("Success. Installation token obtained.")
    print(f"Expires at: {result.get('expires_at')}")
    print(f"Token prefix (safe to show): {result['token'][:8]}...")


if __name__ == "__main__":
    main()
