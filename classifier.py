"""
classifier.py

Email classification using Google Gemini.
Determines whether an email represents job application progress,
inbox noise, or content worth keeping.
"""

from google import genai
from secret_manager import get_secret

GEMINI_MODEL = "gemini-2.5-flash-lite"

# ── Classification Prompt ─────────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """
You are an email classifier for a software developer actively applying for jobs.
Classify the email below into EXACTLY one of three categories.

─────────────────────────────────────────────────────────────
CATEGORY 1 — JOB_PROGRESS
─────────────────────────────────────────────────────────────
Emails that represent real movement in a job application process.
This includes:
  - Interview invitations or scheduling requests
  - Recruiter follow-ups requesting availability or more info
  - Technical assessments or take-home assignments
  - Offer letters or compensation discussions
  - Rejection notices (a definitive final answer)
  - Referrals or warm introductions to a hiring team

─────────────────────────────────────────────────────────────
CATEGORY 2 — NOISE
─────────────────────────────────────────────────────────────
Low-value emails that require no action and contain no new information.
This includes:
  - Automated "we received your application" confirmations
  - Generic "thanks for applying, we'll be in touch" auto-replies
  - Promotional or marketing emails from brands or retailers
  - LinkedIn job recommendations, alerts, or digest emails
  - Glassdoor, Indeed, or job board alert emails
  - Receipt or order confirmation emails
  - Social media notifications (Facebook, Instagram, etc.)
  - App or service promotional announcements

─────────────────────────────────────────────────────────────
CATEGORY 3 — KEEP
─────────────────────────────────────────────────────────────
Emails that are worth keeping in the inbox even if not urgent.
Use this category when:
  - The email is a newsletter or digest the user clearly subscribed to
    (e.g. developer newsletters, AI/tech digests like TLDR, Morning Brew)
  - The email is from a known contact or service the user actively uses
  - The content is genuinely informative or time-sensitive
  - You are uncertain whether the email is important

When in doubt, use KEEP — it is safer to keep an email than to
archive something the user might need.

─────────────────────────────────────────────────────────────
Email Details:
From: {sender}
Subject: {subject}
Body (first 1000 chars): {body}
─────────────────────────────────────────────────────────────

Respond with ONLY the category word: JOB_PROGRESS, NOISE, or KEEP
""".strip()


# ── Gemini Client ─────────────────────────────────────────────────────────────

def get_gemini_client() -> genai.Client:
    """Initialises and returns a Gemini API client."""
    return genai.Client(api_key=get_secret("gemini-api-key"))


# ── Classification ────────────────────────────────────────────────────────────

def classify_email(client: genai.Client, subject: str, sender: str, body: str) -> str:
    """
    Classifies an email using Gemini.

    Returns one of: 'JOB_PROGRESS', 'NOISE', 'KEEP'
    Defaults to 'KEEP' on any API error to avoid incorrectly archiving email.
    """
    prompt = CLASSIFICATION_PROMPT.format(sender=sender, subject=subject, body=body)
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        result = response.text.strip().upper()
        return result if result in ("JOB_PROGRESS", "NOISE", "KEEP") else "KEEP"
    except Exception as e:
        print(f"[!] Gemini classification error: {e}")
        return "KEEP"  # Fail safe: never archive on API error.
