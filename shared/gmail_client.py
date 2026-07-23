"""
Gmail REST client — minimal, requests-only.

Talks to the Gmail API v1 using an OAuth refresh token. No Google SDK
dependency; `requests` (already in requirements.txt) is enough.

Required environment variables:
    GMAIL_CLIENT_ID       OAuth client ID from Google Cloud Console
    GMAIL_CLIENT_SECRET   OAuth client secret
    GMAIL_REFRESH_TOKEN   Long-lived refresh token for the HSO inbox
                          (mint with scripts/mint_gmail_token.py)

Scope required when minting the token: https://www.googleapis.com/auth/gmail.modify
(read + create drafts + manage labels; does NOT allow sending)
"""

from __future__ import annotations

import base64
import logging
import os
import time
from email.header import decode_header
from email.mime.text import MIMEText
from email.utils import parseaddr
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailError(Exception):
    pass


def _decode_mime_header(value: str) -> str:
    """Decode RFC 2047 encoded headers like =?UTF-8?B?...?="""
    if not value:
        return ""
    parts = []
    for chunk, enc in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _b64url_decode(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    import re
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class GmailClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @classmethod
    def from_env(cls) -> "GmailClient":
        cid = os.environ.get("GMAIL_CLIENT_ID", "")
        secret = os.environ.get("GMAIL_CLIENT_SECRET", "")
        rt = os.environ.get("GMAIL_REFRESH_TOKEN", "")
        missing = [n for n, v in [
            ("GMAIL_CLIENT_ID", cid),
            ("GMAIL_CLIENT_SECRET", secret),
            ("GMAIL_REFRESH_TOKEN", rt),
        ] if not v]
        if missing:
            raise GmailError(f"Missing environment variables: {', '.join(missing)}")
        return cls(cid, secret, rt)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        r = requests.post(TOKEN_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }, timeout=30)
        if r.status_code != 200:
            raise GmailError(f"Token refresh failed ({r.status_code}): {r.text[:300]}")
        data = r.json()
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._access_token

    def access_token(self) -> str:
        """Public accessor — the same token works for any API the refresh
        token's scopes cover (Gmail, and Sheets for the KB sync)."""
        return self._token()

    def _request(self, method: str, path: str, *, params: dict = None,
                 json_body: dict = None) -> dict:
        headers = {"Authorization": f"Bearer {self._token()}"}
        last_err = None
        for attempt in range(3):
            try:
                r = requests.request(
                    method, f"{API_BASE}{path}", headers=headers,
                    params=params, json=json_body, timeout=60,
                )
                if r.status_code == 401 and attempt == 0:
                    # Access token may have been revoked mid-flight; force refresh.
                    self._access_token = None
                    headers = {"Authorization": f"Bearer {self._token()}"}
                    continue
                if r.status_code >= 400:
                    raise GmailError(
                        f"Gmail API {method} {path} failed "
                        f"({r.status_code}): {r.text[:300]}"
                    )
                return r.json() if r.text else {}
            except requests.RequestException as e:
                last_err = e
                logger.warning("Gmail request failed attempt=%d: %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise GmailError(f"Gmail API {method} {path} failed after retries: {last_err}")

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def list_message_ids(self, query: str, max_results: int = 25) -> list[str]:
        data = self._request("GET", "/messages", params={
            "q": query, "maxResults": max_results,
        })
        return [m["id"] for m in data.get("messages", [])]

    def get_message(self, message_id: str) -> dict:
        return self._request("GET", f"/messages/{message_id}", params={"format": "full"})

    @staticmethod
    def _extract_body(payload: dict) -> str:
        """Walk MIME parts; prefer text/plain, fall back to stripped text/html."""
        plain, html = [], []

        def walk(part: dict) -> None:
            mime = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data")
            if body_data:
                if mime == "text/plain":
                    plain.append(_b64url_decode(body_data))
                elif mime == "text/html":
                    html.append(_b64url_decode(body_data))
            for sub in part.get("parts", []) or []:
                walk(sub)

        walk(payload)
        if plain:
            return "\n".join(plain).strip()
        if html:
            return _strip_html("\n".join(html))
        return ""

    @staticmethod
    def _count_attachments(payload: dict) -> int:
        count = 0

        def walk(part: dict) -> None:
            nonlocal count
            if part.get("filename"):
                count += 1
            for sub in part.get("parts", []) or []:
                walk(sub)

        walk(payload)
        return count

    def parse_message(self, msg: dict) -> dict:
        """Convert a Gmail API message into the agent payload dict, plus
        the extra fields the poller needs to build a threaded reply."""
        payload = msg.get("payload", {})
        headers = {
            h["name"].lower(): h["value"] for h in payload.get("headers", [])
        }
        sender_name, sender_email = parseaddr(
            _decode_mime_header(headers.get("from", ""))
        )
        subject = _decode_mime_header(headers.get("subject", ""))
        return {
            # Fields agent.process_email_from_dict expects:
            "message_id": msg["id"],
            "thread_id": msg.get("threadId", msg["id"]),
            "sender_email": sender_email or "",
            "sender_name": sender_name or "",
            "subject": subject,
            "body": self._extract_body(payload),
            "attachment_count": self._count_attachments(payload),
            # Extra fields for reply threading (not consumed by the agent):
            "rfc822_message_id": headers.get("message-id", ""),
            "references": headers.get("references", ""),
        }

    # ------------------------------------------------------------------
    # Threads
    # ------------------------------------------------------------------

    def get_thread(self, thread_id: str) -> dict:
        return self._request("GET", f"/threads/{thread_id}", params={"format": "full"})

    def get_thread_history(
        self,
        thread_id: str,
        exclude_message_id: str = "",
        max_messages: int = 10,
        max_chars_per_message: int = 1500,
    ) -> str:
        """Return earlier messages in a thread as a formatted string for the
        drafter (oldest first). Only messages BEFORE the one being processed
        are included — Gmail returns thread messages in chronological order,
        so we stop when we reach it."""
        thread = self.get_thread(thread_id)
        messages = thread.get("messages", [])
        parts = []
        for m in messages:
            if m.get("id") == exclude_message_id:
                break
            p = self.parse_message(m)
            body = p["body"][:max_chars_per_message]
            if len(p["body"]) > max_chars_per_message:
                body += "\n[... truncated ...]"
            sender = p["sender_name"] or p["sender_email"]
            parts.append(f"--- From: {sender} <{p['sender_email']}> ---\n{body}")
        if not parts:
            return ""
        return "\n\n".join(parts[-max_messages:])

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def ensure_labels(self, names: list[str]) -> dict[str, str]:
        """Return {label_name: label_id}, creating any that don't exist."""
        existing = {
            lbl["name"]: lbl["id"]
            for lbl in self._request("GET", "/labels").get("labels", [])
        }
        result = {}
        for name in names:
            if name in existing:
                result[name] = existing[name]
            else:
                created = self._request("POST", "/labels", json_body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                })
                result[name] = created["id"]
                logger.info("Created Gmail label: %s", name)
        return result

    def add_labels(self, message_id: str, label_ids: list[str]) -> None:
        if not label_ids:
            return
        self._request("POST", f"/messages/{message_id}/modify", json_body={
            "addLabelIds": label_ids,
        })

    # ------------------------------------------------------------------
    # Drafts
    # ------------------------------------------------------------------

    def create_reply_draft(
        self,
        thread_id: str,
        to_email: str,
        subject: str,
        body: str,
        in_reply_to: str = "",
        references: str = "",
    ) -> str:
        """Create a draft reply in the given thread. Returns the draft ID.
        The draft is NOT sent — a human reviews and sends it from Gmail."""
        mime = MIMEText(body, "plain", "utf-8")
        mime["To"] = to_email
        mime["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if in_reply_to:
            mime["In-Reply-To"] = in_reply_to
            mime["References"] = (
                f"{references} {in_reply_to}".strip() if references else in_reply_to
            )
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
        data = self._request("POST", "/drafts", json_body={
            "message": {"threadId": thread_id, "raw": raw},
        })
        return data.get("id", "")
