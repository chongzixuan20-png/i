# InScout

InScout is a practical full-stack prototype for shipping inbox triage and SI/BL verification.

## Stack

- AI: Gemini 1.5 Flash with a local labelled-text fallback
- Backend: Python FastAPI
- Frontend: React + Tailwind CSS + Vite
- Database: Firebase Firestore (optional persistence)
- Deployment: Google Cloud Run
- IDE: Trae
- Source control: GitHub

The organizer ZIP files are intentionally not committed. Keep `sdoc-hackathon-bundle.zip` and `sdoc-hackathon-docker.zip` outside this repository, then adapt the demo provider in `backend/main.py` to the supplied `loader.py` contract.

## Run locally

### Backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8080
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and ensure the frontend is pointed at the backend host. By default the frontend calls `http://localhost:8080`.

## Secrets

The Gemini key posted in chat must be revoked and replaced with a new key. Do not commit any API keys or Firebase credentials.

Set keys in your local shell or deployment environment:

```bash
export GEMINI_API_KEY="your-new-key"
export FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account", ...}'
export CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```

For Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="your-new-key"
$env:FireBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account", ...}'
$env:CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```

## Cloud Run deployment

The included Dockerfile packages the FastAPI service for Cloud Run:

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/inscout-api .
gcloud run deploy inscout-api --image gcr.io/PROJECT_ID/inscout-api --platform managed --region asia-southeast1 --allow-unauthenticated
```

Then point the frontend to the deployed Cloud Run URL through `VITE_API_URL`.

## Competition integration plan

1. Extract both organizer ZIPs outside the repo.
2. Read the provided `loader.py` and convert its records into the same shape as `DEMO_EMAILS`.
3. Preserve the seven-field report shape expected by `sample_submission.json`.
4. Run the organizer `score_cli.py` against exported report JSON files.
5. Add a Firestore collection for persistent review decisions.

## Notes

- PDF text extraction is supported.
- Scanned PDFs still require OCR.
- The demo flow works even without Gemini or Firestore configured.
