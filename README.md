# Email Sort Agent

An autonomous email classifier that runs on Google Cloud and keeps your inbox clean. New emails are classified in real-time using Gemini and automatically organised into Gmail labels.

## How It Works

```
New email arrives in Gmail
  → Gmail Watch fires a notification to Google Cloud Pub/Sub
  → Pub/Sub triggers the Cloud Function
  → Function classifies the email using Gemini 2.0 Flash
  → Gmail label applied, noise archived
  → Function exits (no idle cost)
```

## Classification Logic

| Label | Meaning | Action |
|---|---|---|
| `[Job] Progress` | Interview invites, recruiter replies, assessments, offers | Kept in Inbox |
| `[Filtered] Noise` | Promotional email, job board alerts, auto-confirmations | Archived |
| *(none)* | Intentional subscriptions, ambiguous mail | Kept in Inbox |

When in doubt, the classifier keeps email in your Inbox. It only archives mail it is confident is low-value.

## Project Structure

```
email_sort/
├── main.py           # Cloud Function — classifies emails and applies labels
├── setup_watch.py    # One-time script to register Gmail push notifications
├── requirements.txt  # Python dependencies for the Cloud Function
└── .gitignore        # Excludes credentials and tokens from version control
```

## Setup

### Prerequisites
- Google Cloud project with billing enabled
- `gcloud` CLI installed and authenticated
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Enable GCP APIs
```bash
gcloud services enable pubsub cloudfunctions cloudbuild secretmanager cloudscheduler run
```

### 2. Create Pub/Sub Topic and Grant Gmail Permission
```bash
gcloud pubsub topics create gmail-notifications

gcloud pubsub topics add-iam-policy-binding gmail-notifications \
  --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

### 3. Store Secrets
```bash
gcloud secrets create gmail-oauth-token    --data-file="token.json"
gcloud secrets create gmail-credentials   --data-file="credentials.json"
gcloud secrets create gemini-api-key      --data-file="-"   # paste key, then Ctrl+D
```

Grant the Cloud Function's service account read access to each secret:
```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in gmail-oauth-token gmail-credentials gemini-api-key; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor"
done
```

### 4. Deploy the Cloud Function
```bash
gcloud functions deploy email-classifier \
  --gen2 \
  --runtime=python312 \
  --region=us-central1 \
  --source=. \
  --entry-point=classify_email_handler \
  --trigger-http \
  --allow-unauthenticated \
  --max-instances=5 \
  --memory=256Mi \
  --timeout=120s
```

### 5. Create Pub/Sub Push Subscription
```bash
gcloud pubsub subscriptions create gmail-push-sub \
  --topic=gmail-notifications \
  --push-endpoint="https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/email-classifier" \
  --ack-deadline=60
```

### 6. Register Gmail Watch
```bash
python setup_watch.py
```

### 7. Schedule Watch Renewal (Gmail Watch expires after 7 days)
```bash
gcloud scheduler jobs create http renew-gmail-watch \
  --location=us-central1 \
  --schedule="0 9 */6 * *" \
  --uri="https://us-central1-YOUR_PROJECT_ID.cloudfunctions.net/email-classifier" \
  --message-body='{"renew": true}' \
  --http-method=POST
```

## Redeploying After Code Changes

```bash
gcloud functions deploy email-classifier \
  --gen2 --runtime=python312 --region=us-central1 \
  --source=. --entry-point=classify_email_handler \
  --trigger-http --allow-unauthenticated \
  --max-instances=5 --memory=256Mi --timeout=120s
```

## Viewing Logs

```bash
gcloud functions logs read email-classifier --region=us-central1
```

## Cost

Designed to run within Google Cloud's free tier for personal use. Typical cost for a personal inbox: **< $0.10/month**.

Set up a budget alert at [console.cloud.google.com/billing](https://console.cloud.google.com/billing) to notify you if spend ever approaches a threshold.
