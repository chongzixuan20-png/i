# InScout

A small, practical Streamlit prototype for shipping inbox triage and SI/BL verification.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The application starts in **local demo mode** and does not require an API key. It includes a representative inbox and a verification request so the complete UI can be demonstrated before the competition ZIP files are available.

## Enable Gemini

1. Revoke the API key that was posted in chat and create a replacement.
2. Set it only in your local environment or deployment secret:

```bash
export GEMINI_API_KEY="your-new-key"
streamlit run app.py
```

For Streamlit Cloud, add `GEMINI_API_KEY` under App settings → Secrets. Never commit `.env`, keys, or service-account JSON files.

Gemini is used for inbox classification and seven-field extraction. If it is unavailable, the app deliberately falls back to a transparent local label extractor so the demo remains usable.

## Add the organizer dataset

Do not commit the ZIP archives or extracted competition data if they contain restricted material. Extract them outside the repository, inspect their `README` and loader contract, then adapt the `DEMO_EMAILS` provider in `app.py` to call the provided `loader.py`. Keep the current demo records as a fallback.

The expected adapter should return records shaped like:

```python
{"id": "...", "sender": "...", "subject": "...", "preview": "...", "attachments": [...]}
```

For a competition submission, connect the organizer's `score_cli.py` separately and write the generated report JSON to the exact path/shape required by their sample submission. The UI's download button already produces a structured report containing `fields`, `mismatches`, confidence, and review metadata.

## Deployment

For a quick Cloud Run deployment, containerize the Streamlit app with a non-root user and inject `GEMINI_API_KEY` using Secret Manager. Firebase persistence is intentionally not hard-coded into the prototype: add it after the organizer's data contract is confirmed, using Firestore server credentials from Secret Manager rather than a downloaded key in Git.

## Prototype limitations

- The demo dataset is embedded because the ZIP files were not available in the repository.
- The fallback extractor handles labelled plain text; Gemini improves varied wording and aliases.
- Streamlit session state is temporary. Add Firestore for shared operator queues.
- PDF support extracts text but does not OCR scanned images.
