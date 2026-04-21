"""
classifier.py

Email classification using Google Gemini.
Determines whether an email represents job application progress,
inbox noise, or content worth keeping.

Includes a deterministic pre-filter for Job Scout alert emails so they
are never passed to Gemini — saving API quota and guaranteeing accuracy.
"""

from google import genai
from secret_manager import get_secret

GEMINI_MODEL = "gemini-2.5-flash-lite"

# ── Classification Prompt ─────────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """
You are an email classifier for a software developer actively applying for jobs.
Classify the email below into EXACTLY one of seven categories.

─────────────────────────────────────────────────────────────
CATEGORY 1 — JOB_APPLIED
─────────────────────────────────────────────────────────────
Auto-confirmations that an application was received.
- "We received your application"
- "Thanks for applying to..."
- "Your application is under review"
- Generic automated responses from ATS systems

─────────────────────────────────────────────────────────────
CATEGORY 2 — JOB_FORWARD
─────────────────────────────────────────────────────────────
Real progress in a job application process. ALWAYS keep these.
- ANY email asking you to take an assessment or complete a next step
- Interview invitations or scheduling requests
- Recruiter follow-ups requesting availability or more info
- Technical assessments or take-home assignments
- Offer letters, compensation, or negotiation
- IMPORTANT: Ignore "no-reply" senders or "Unsubscribe" links if the email asks you to take an assessment, schedule an interview, or complete next steps. It is JOB_FORWARD.

─────────────────────────────────────────────────────────────
CATEGORY 3 — JOB_REJECTED
─────────────────────────────────────────────────────────────
Rejection notices.
- "We have decided to move forward with other candidates"
- "While your background is impressive..."

─────────────────────────────────────────────────────────────
CATEGORY 4 — NEWSLETTER
─────────────────────────────────────────────────────────────
Newsletters, digests, or subscriptions the user wants to read.
- Developer newsletters
- AI/tech digests like TLDR, Morning Brew
- Substack publications or industry news

─────────────────────────────────────────────────────────────
CATEGORY 5 — RECEIPT
─────────────────────────────────────────────────────────────
Purchase confirmations or subscription billing.
- "Your receipt from..."
- "Your order has shipped"
- App store receipts

─────────────────────────────────────────────────────────────
CATEGORY 6 — JUNK
─────────────────────────────────────────────────────────────
Unsolicited marketing, social notifications, or job board spam.
- Promotional or marketing emails from brands/retailers
- LinkedIn job recommendations, alerts, or digest emails
- Glassdoor, Indeed, or specific company job alert emails
- Social media notifications (Facebook, Instagram, etc.)

─────────────────────────────────────────────────────────────
CATEGORY 7 — KEEP
─────────────────────────────────────────────────────────────
Anything ambiguous, important personal emails, or if uncertain.
- Emails from known contacts or colleagues
- Informative or time-sensitive content not fitting above
- When in doubt, use KEEP — never archive if unsure

─────────────────────────────────────────────────────────────
Email Details:
From: {sender}
Subject: {subject}
Body (first 1000 chars): {body}
─────────────────────────────────────────────────────────────

Respond with ONLY the category word: JOB_APPLIED, JOB_FORWARD, JOB_REJECTED, NEWSLETTER, RECEIPT, JUNK, or KEEP
""".strip()


# ── Gemini Client ─────────────────────────────────────────────────────────────

def get_gemini_client() -> genai.Client:
    """Initialises and returns a Gemini API client."""
    return genai.Client(api_key=get_secret("gemini-api-key"))


# ── Deterministic Pre-filters ──────────────────────────────────────────────────

def is_job_scout_alert(subject: str, sender: str, body: str) -> bool:
    """
    Returns True if the email was sent by the Job Scout pipeline.

    Job Scout always sends emails from the user's own Gmail address with:
      - Subject starting with '🚀 '
      - Footer containing 'Sent by Job Scout'

    Checking all three signals makes this practically impossible to false-positive.
    We short-circuit before calling Gemini to save API quota.
    """
    subject_match = subject.startswith("🚀 ")
    # sender is the user's own address (Job Scout sends from GMAIL_USER to GMAIL_USER)
    sender_match  = "job scout" in sender.lower() or "davidgsk.kim@gmail.com" in sender.lower()
    body_match    = "sent by job scout" in body.lower()
    return subject_match and (sender_match or body_match)


# ── Classification ────────────────────────────────────────────────────────────

def classify_email(client: genai.Client, subject: str, sender: str, body: str) -> tuple[str, bool]:
    """
    Classifies an email.

    First runs deterministic pre-filters (no API cost). If none match,
    falls back to Gemini. Returns a tuple: (category, api_called).
    """
    # Fast path: Job Scout pipeline emails — never send to Gemini.
    if is_job_scout_alert(subject, sender, body):
        print(f"[*] Pre-filter matched: JOB_SCOUT alert detected.")
        return "JOB_SCOUT", False

    prompt = CLASSIFICATION_PROMPT.format(sender=sender, subject=subject, body=body)
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        result = response.text.strip().upper()
        valid_categories = ("JOB_APPLIED", "JOB_FORWARD", "JOB_REJECTED", "NEWSLETTER", "RECEIPT", "JUNK", "KEEP")
        final_category = result if result in valid_categories else "KEEP"
        return final_category, True
    except Exception as e:
        print(f"[!] Gemini classification error: {e}")
        return "KEEP", False  # No successful API call.
