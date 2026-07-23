"""
One-time helper: mint a Gmail refresh token for the HSO inbox.

Prerequisites (Google Cloud Console):
    1. A project with the Gmail API enabled
    2. OAuth consent screen configured (External) and PUBLISHED to
       "In production" — otherwise the refresh token expires in 7 days
    3. An OAuth client. Either:
       - type "Desktop app"  (recommended — loopback redirect just works), or
       - type "Web application" with http://localhost:8765 added as an
         authorized redirect URI

Usage:
    export GMAIL_CLIENT_ID=...
    export GMAIL_CLIENT_SECRET=...
    python scripts/mint_gmail_token.py

Then open the printed URL in a browser where the HSO Gmail account
(Hope.spot.org@gmail.com) is signed in, approve the gmail.modify scope,
and the script prints the refresh token. Set it as GMAIL_REFRESH_TOKEN
in Render. Run this ONCE; the refresh token does not expire as long as
the consent screen stays in production status and access isn't revoked.

The token also carries the spreadsheets.readonly scope so the same
credentials power the Google Sheets -> KB sync (shared/kb_sync.py).
"""

from __future__ import annotations

import http.server
import os
import sys
import threading
import urllib.parse

import requests

SCOPE = (
    "https://www.googleapis.com/auth/gmail.modify "
    "https://www.googleapis.com/auth/spreadsheets.readonly"
)
REDIRECT_URI = "http://localhost:8765"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

_code_holder: dict = {}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            _code_holder["code"] = params["code"][0]
            body = b"Authorization received. You can close this tab."
        else:
            body = b"No authorization code in request."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence request logging
        pass


def main() -> None:
    client_id = os.environ.get("GMAIL_CLIENT_ID", "")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        sys.exit("Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET first.")

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",   # required to receive a refresh token
        "prompt": "consent",        # force refresh token even if previously granted
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n1. Open this URL in a browser signed into the HSO Gmail account:\n")
    print(url)
    print("\n2. Approve access. Waiting for the redirect on localhost:8765 ...\n")

    server = http.server.HTTPServer(("localhost", 8765), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        while "code" not in _code_holder:
            thread.join(0.2)
    except KeyboardInterrupt:
        sys.exit("\nAborted.")
    finally:
        server.shutdown()

    r = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": _code_holder["code"],
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Token exchange failed ({r.status_code}): {r.text}")

    data = r.json()
    refresh = data.get("refresh_token")
    if not refresh:
        sys.exit(
            "No refresh_token in response. Remove the app's prior grant at "
            "https://myaccount.google.com/permissions and run again."
        )

    print("Success. Set this in Render (do NOT commit it anywhere):\n")
    print(f"GMAIL_REFRESH_TOKEN={refresh}\n")


if __name__ == "__main__":
    main()
