"""
GitHub App authentication: sign a JWT with the App's private key, then
exchange it for a short-lived installation access token.

Two-hop auth, required by GitHub Apps:
  1. JWT ("I am this App"), signed with the private key, max 10 min lifetime
  2. Installation access token ("I am this App, acting on this specific
     installation"), obtained by POSTing the JWT to GitHub, valid ~1 hour

Reference:
https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app
"""
import time

import jwt
import requests

GITHUB_API_BASE = "https://api.github.com"


def generate_jwt(app_id: str, private_key_pem: str) -> str:
    """
    Sign a JWT proving identity as the GitHub App itself (not yet scoped
    to any specific installation/repo).

    Args:
        app_id: the App ID from the GitHub App's General settings page
        private_key_pem: the full contents of the downloaded .pem file, as a string
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,        # backdated 60s to tolerate clock drift with GitHub's servers
        "exp": now + (9 * 60),  # GitHub allows max 10 minutes; stay comfortably under
        "iss": app_id,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def get_installation_token(app_jwt: str, installation_id: str) -> dict:
    """
    Exchange an App-level JWT for an installation access token — the token
    actually used to call the API on behalf of a specific installed repo.

    Returns the full JSON response (contains 'token' and 'expires_at').
    Raises requests.HTTPError if the request fails (e.g. wrong
    installation_id, or the JWT expired before this call ran).
    """
    url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    response = requests.post(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()
