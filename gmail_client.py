"""
gmail_client.py

Gmail API client and inbox management utilities.
Handles authentication, message fetching, label management, and archiving.
"""

import base64
import json
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from secret_manager import get_secret

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
]


# ── Authentication ─────────────────────────────────────────────────────────────

def get_gmail_service():
    """
    Builds an authenticated Gmail API client using OAuth credentials
    stored in Secret Manager. Automatically refreshes expired tokens.
    """
    token_data = json.loads(get_secret("gmail-oauth-token"))
    creds_data = json.loads(get_secret("gmail-credentials"))

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=creds_data["installed"]["client_id"],
        client_secret=creds_data["installed"]["client_secret"],
        scopes=SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)


# ── Message Fetching ───────────────────────────────────────────────────────────

def fetch_unread_messages(service, max_results: int = 10) -> list:
    """Returns a list of unread Inbox message references (id + threadId only)."""
    result = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
        maxResults=max_results,
    ).execute()
    return result.get("messages", [])


def fetch_full_message(service, msg_id: str) -> dict:
    """Fetches the full payload of a message by ID."""
    return service.users().messages().get(
        userId="me",
        id=msg_id,
        format="full",
    ).execute()


def fetch_messages_from_history(service, start_history_id: str) -> list | None:
    """
    Returns message refs newly added to the Inbox since start_history_id.

    Uses the Gmail History API to fetch only the delta — messages that
    arrived after the last recorded historyId. This prevents re-processing
    emails that have already been classified.

    Returns None if the historyId is too old (> ~30 days), signalling the
    caller to fall back to a standard unread scan.
    """
    try:
        result = service.users().history().list(
            userId="me",
            startHistoryId=start_history_id,
            historyTypes=["messageAdded"],
            labelId="INBOX",
        ).execute()

        seen_ids = set()
        messages = []
        for record in result.get("history", []):
            for msg_added in record.get("messagesAdded", []):
                msg    = msg_added.get("message", {})
                msg_id = msg.get("id")
                if msg_id and msg_id not in seen_ids:
                    seen_ids.add(msg_id)
                    messages.append({"id": msg_id})
        return messages

    except Exception as e:
        if "404" in str(e):
            print("[!] History ID too old — falling back to unread scan.")
            return None
        raise


def get_email_body(payload, max_chars: int = 1000) -> str:
    """Extracts and returns plain text from an email payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
                break
    elif "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(
            payload["body"]["data"] + "=="
        ).decode("utf-8", errors="ignore")

    return re.sub(r"\s+", " ", body).strip()[:max_chars]


# ── Label Management ───────────────────────────────────────────────────────────

def get_or_create_label(service, name: str) -> str:
    """Returns the ID of a Gmail label, creating it if it does not exist."""
    existing = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in existing:
        if label["name"] == name:
            return label["id"]

    created = service.users().labels().create(
        userId="me",
        body={
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    ).execute()
    print(f"[+] Created Gmail label: '{name}'")
    return created["id"]


def apply_label(service, msg_id: str, label_id: str) -> None:
    """Adds a label to a Gmail message."""
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"addLabelIds": [label_id]},
    ).execute()


def archive_message(service, msg_id: str) -> None:
    """Removes a message from the Inbox without deleting it."""
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"removeLabelIds": ["INBOX"]},
    ).execute()
