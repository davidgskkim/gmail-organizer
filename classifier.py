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
        valid_categories = ("JOB_APPLIED", "JOB_FORWARD", "JOB_REJECTED", "NEWSLETTER", "RECEIPT", "JUNK", "KEEP")
        return result if result in valid_categories else "KEEP"
    except Exception as e:
        print(f"[!] Gemini classification error: {e}")
        return "KEEP"  # Fail safe: never archive on API error.
