"""
secrets.py

Thin wrapper around Google Cloud Secret Manager.
All runtime credentials are stored here rather than in environment
variables, ensuring secrets are never exposed in logs or source code.
"""

from google.cloud import secretmanager

PROJECT_ID = "gmail-sort-agent"


def get_secret(secret_id: str) -> str:
    """Retrieves the latest version of a secret from GCP Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8").strip()
