import sys
import os
import time

from gmail_client import get_gmail_service, fetch_unread_messages, fetch_full_message, get_email_body, apply_label, archive_message, get_or_create_label
from classifier import classify_email, get_gemini_client

def sweep():
    service = get_gmail_service()
    gemini = get_gemini_client()
    
    label_map = {
        "JOB_APPLIED": get_or_create_label(service, "[Job] Applied"),
        "JOB_FORWARD": get_or_create_label(service, "[Job] Forward"),
        "JOB_REJECTED": get_or_create_label(service, "[Job] Rejected"),
        "JOB_SCOUT": get_or_create_label(service, "[Job] Scout"),
        "NEWSLETTER": get_or_create_label(service, "[Newsletter]"),
        "RECEIPT": get_or_create_label(service, "[Receipt]"),
        "JUNK": get_or_create_label(service, "[Junk]")
    }

    messages = fetch_unread_messages(service, max_results=150)
    print(f"[*] Found {len(messages)} unread messages to sweep.")
    
    count = 0
    for msg_ref in messages:
        msg_id = msg_ref["id"]
        msg = fetch_full_message(service, msg_id)
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("Subject", "(No Subject)")
        sender = headers.get("From", "(Unknown Sender)")
        body = get_email_body(msg["payload"])
        
        category, api_called = classify_email(gemini, subject, sender, body)
        print(f"[{category}] {subject[:60]}")
        
        if category in label_map:
            apply_label(service, msg_id, label_map[category])
            archive_message(service, msg_id)
            count += 1
            
        if api_called:
            time.sleep(3)

    print(f"Sweep complete. Processed and archived {count} emails.")

if __name__ == "__main__":
    sweep()
