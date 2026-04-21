"""
refresh_token.py

Re-runs the Gmail OAuth flow locally to generate a fresh token.json,
then uploads it to Secret Manager to replace the expired one.

Run once whenever you see: 'invalid_grant: Token has been expired or revoked.'
"""

import json
import subprocess
from google_auth_oauthlib.flow import InstalledAppFlow
from google.cloud import secretmanager

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
]
PROJECT_ID = "gmail-sort-agent"


def main():
    # Step 1: Run OAuth flow using local credentials.json
    print("[*] Opening browser for Gmail OAuth...")
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = json.loads(creds.to_json())
    token_json = json.dumps(token_data)

    # Step 2: Save locally as backup
    with open("token.json", "w") as f:
        f.write(token_json)
    print("[✓] Saved fresh token.json locally.")

    # Step 3: Upload to Secret Manager
    print("[*] Uploading to Secret Manager...")
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{PROJECT_ID}/secrets/gmail-oauth-token"
    client.add_secret_version(
        request={
            "parent": secret_name,
            "payload": {"data": token_json.encode("utf-8")},
        }
    )
    print("[✓] Secret Manager updated with fresh token.")
    print("[✓] Email sort agent will resume automatically — no redeploy needed.")


if __name__ == "__main__":
    main()
