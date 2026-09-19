# InScout

InScout is now a small full-stack prototype for shipping inbox triage and SI/BL verification.

## Stack

- **AI:** Gemini 1.5 Flash, with a local labelled-text fallback
- **Backend:** Python FastAPI
- **Frontend:** React + Tailwind CSS + Vite
- **Database:** Firebase Firestore (optional persistence)
- **Deployment:** Google Cloud Run
- **IDE:** Trae
- **Source:** GitHub

The organizer ZIP files are intentionally not committed. Keep `sdoc-hackathon-bundle.zip` and `sdoc-hackathon-docker.zip` outside this repository, then adapt the `DEMO_EMAILS` provider in `backend/main.py` to the supplied `loader.py` contract.

## Run locally

### Backend

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
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

Open `http://localhost:5173`. The frontend calls `http://localhost:8080` by default. Set `VITE_API_URL` when the API is hosted elsewhere.

The demo works without Gemini or Firestore. The demo inbox and one intentional container-count mismatch are built in so the complete flow can be shown immediately.

## Secrets

The previously exposed Gemini key must be revoked and replaced. Never commit API keys or Firebase service-account JSON. Set secrets through the shell locally or Cloud Run Secret Manager:

```powershell
$env:GEMINI_API_KEY="your-new-key"
$env:FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account", ...}'
```

Cloud Run should receive both values from Secret Manager. `CORS_ORIGINS` should contain the deployed frontend origin.

## Cloud Run

The included `backend/Dockerfile` deploys the FastAPI API:

```bash
gcloud run deploy inscout-api --source . --region asia-southeast1 --allow-unauthenticated
```

For a production setup, build and host the React `frontend/dist` separately or serve it through Firebase Hosting, and set `VITE_API_URL` to the Cloud Run URL. Keep the API secret-free in GitHub.

## Competition integration plan

1. Extract both organizer ZIPs outside the repo.
2. Read the provided `loader.py` and return inbox records from `/api/inbox`.
3. Preserve the seven-field report shape expected by `sample_submission.json`.
4. Run the organizer `score_cli.py` against exported reports.
5. Add a Firestore collection for persistent review decisions.

PDF text extraction is supported; scanned PDFs still need OCR.
