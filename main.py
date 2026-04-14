"""
main.py

Cloud Function entry point. Receives Gmail push notifications via
Google Cloud Pub/Sub and orchestrates email classification.

Each invocation processes up to 10 unread inbox messages, applies
Gmail labels, and archives low-value email automatically.
"""

import base64
import json
import time

import functions_framework

from classifier import classify_email, get_gemini_client
from gmail_client import (
    apply_label,
    archive_message,
    fetch_full_message,
    fetch_unread_messages,
    get_email_body,
    get_gmail_service,
    get_or_create_label,
)

LABEL_JOB_APPLIED  = "[Job] Applied"
LABEL_JOB_FORWARD  = "[Job] Forward"
LABEL_JOB_REJECTED = "[Job] Rejected"
LABEL_NEWSLETTER   = "[Newsletter]"
LABEL_RECEIPT      = "[Receipt]"
LABEL_JUNK         = "[Junk]"


@functions_framework.http
def classify_email_handler(request):
    """
    HTTP handler triggered by a Pub/Sub push subscription.

    Gmail publishes a notification to Pub/Sub when new mail arrives.
    Pub/Sub forwards it here as an HTTP POST. Returning HTTP 200
    acknowledges the message; HTTP 500 signals Pub/Sub to retry.
    """
    try:
        # Decode the Pub/Sub envelope.
        # Gmail sends a base64-encoded JSON payload with the recipient
        # address and a historyId — a cursor, not the email itself.
        envelope = request.get_json(silent=True)
        if not envelope or "message" not in envelope:
            print("[!] Invalid Pub/Sub message received.")
            return "Bad Request", 400

        pubsub_message = envelope["message"]
        if "data" not in pubsub_message:
            return "OK", 200  # Empty notification — nothing to process.

        data = json.loads(base64.b64decode(pubsub_message["data"]).decode("utf-8"))
        print(f"[*] Notification for {data.get('emailAddress')} | historyId: {data.get('historyId')}")

        # Initialise clients.
        service       = get_gmail_service()
        gemini_client = get_gemini_client()

        job_applied_label_id  = get_or_create_label(service, LABEL_JOB_APPLIED)
        job_forward_label_id  = get_or_create_label(service, LABEL_JOB_FORWARD)
        job_rejected_label_id = get_or_create_label(service, LABEL_JOB_REJECTED)
        newsletter_label_id   = get_or_create_label(service, LABEL_NEWSLETTER)
        receipt_label_id      = get_or_create_label(service, LABEL_RECEIPT)
        junk_label_id         = get_or_create_label(service, LABEL_JUNK)

        # Fetch unread inbox messages.
        messages = fetch_unread_messages(service, max_results=10)
        if not messages:
            print("[*] No unread messages to process.")
            return "OK", 200

        print(f"[*] Processing {len(messages)} message(s)...")

        for msg_ref in messages:
            msg_id  = msg_ref["id"]
            msg     = fetch_full_message(service, msg_id)
            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

            subject = headers.get("Subject", "(No Subject)")
            sender  = headers.get("From", "(Unknown Sender)")
            body    = get_email_body(msg["payload"])

            category = classify_email(gemini_client, subject, sender, body)
            print(f"[{category}] {subject[:60]}")

            if category == "JOB_APPLIED":
                apply_label(service, msg_id, job_applied_label_id)
                archive_message(service, msg_id)
            elif category == "JOB_FORWARD":
                apply_label(service, msg_id, job_forward_label_id)
            elif category == "JOB_REJECTED":
                apply_label(service, msg_id, job_rejected_label_id)
                archive_message(service, msg_id)
            elif category == "NEWSLETTER":
                apply_label(service, msg_id, newsletter_label_id)
            elif category == "RECEIPT":
                apply_label(service, msg_id, receipt_label_id)
                archive_message(service, msg_id)
            elif category == "JUNK":
                apply_label(service, msg_id, junk_label_id)
                archive_message(service, msg_id)

            # KEEP: no action — message remains in Inbox as-is.

            time.sleep(4)  # Respect Gemini API rate limits.

        return "OK", 200

    except Exception as e:
        print(f"[!] Unhandled error: {e}")
        return f"Internal Server Error: {e}", 500
