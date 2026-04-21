"""
setup_watch.py

Registers a Gmail push notification watch against a Google Cloud Pub/Sub topic.
Gmail will publish a notification to the topic whenever a new message arrives
in the watched inbox.

Gmail Watch subscriptions expire after 7 days. Re-run this script (or invoke
it via Cloud Scheduler) every 6 days to renew.

Usage:
    python setup_watch.py
"""

import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES       = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
]
TOKEN_FILE   = "token.json"
CREDS_FILE   = "credentials.json"
PUBSUB_TOPIC = "projects/gmail-sort-agent/topics/gmail-notifications"


def get_gmail_service():
    """Builds a Gmail API service client using local OAuth credentials."""
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    with open(CREDS_FILE) as f:
        creds_data = json.load(f)

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


def setup_gmail_watch():
    """Registers a Gmail Watch that pushes inbox notifications to Pub/Sub."""
    service = get_gmail_service()

    result = service.users().watch(
        userId="me",
        body={
            "topicName": PUBSUB_TOPIC,
            "labelIds": ["INBOX"],
        },
    ).execute()

    print(f"[OK] Gmail Watch registered successfully.")
    print(f"     historyId  : {result.get('historyId')}")
    print(f"     expiration : {result.get('expiration')}")
    print(f"\n[!]  This watch expires in ~7 days. Renew before expiry.")


if __name__ == "__main__":
    setup_gmail_watch()
