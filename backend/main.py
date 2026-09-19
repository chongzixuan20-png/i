from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError:  # pragma: no cover
    firebase_admin = None
    credentials = None
    firestore = None

FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]

LABELS = {
    "shipper": "Shipper",
    "consignee": "Consignee",
    "notify_party": "Notify party",
    "port_of_loading": "Port of loading",
    "port_of_discharge": "Port of discharge",
    "container_count": "Container count",
    "gross_weight_kg": "Gross weight (kg)",
}

CATEGORIES = [
    "document-comparison request",
    "new SI request",
    "invoice query",
    "general message",
    "spam",
]

DEMO_EMAILS = [
    {
        "id": "IN-2401",
        "sender": "operations@northstar.example",
        "subject": "Please check SI and BL for NSRU 481920",
        "preview": "Please verify the draft BL against the attached SI before release.",
        "category": CATEGORIES[0],
        "attachments": ["shipping_instruction.txt", "bill_of_lading.txt"],
        "si": {
            "shipper": "Northstar Trading Ltd",
            "consignee": "Harbor Retail GmbH",
            "notify_party": "Harbor Retail GmbH",
            "port_of_loading": "Singapore",
            "port_of_discharge": "Hamburg",
            "container_count": 3,
            "gross_weight_kg": 21800,
        },
        "bl": {
            "shipper": "Northstar Trading Ltd",
            "consignee": "Harbor Retail GmbH",
            "notify_party": "Harbor Retail GmbH",
            "port_of_loading": "Singapore",
            "port_of_discharge": "Hamburg",
            "container_count": 4,
            "gross_weight_kg": 21800,
        },
    },
    {
        "id": "IN-2402",
        "sender": "billing@searoute.example",
        "subject": "Invoice 8931 question",
        "preview": "Could you confirm the detention charge on invoice 8931?",
        "category": CATEGORIES[2],
        "attachments": [],
    },
    {
        "id": "IN-2403",
        "sender": "customer@atlas.example",
        "subject": "New SI for voyage 18E",
        "preview": "Attached is the new shipping instruction for the upcoming booking.",
        "category": CATEGORIES[1],
        "attachments": ["new_si.txt"],
    },
    {
        "id": "IN-2404",
        "sender": "offers@unknown.example",
        "subject": "Exclusive offer — act now",
        "preview": "You have been selected for a limited-time offer.",
        "category": CATEGORIES[4],
        "attachments": [],
    },
]

app = FastAPI(title="InScout API", version="0.2.0")
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def secret(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    return None


def parse_json_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)


def normalise(value: Any, field: str) -> Any:
    if value is None or str(value).strip() == "":
        return None
    if field in {"container_count", "gross_weight_kg"}:
        match = re.search(r"[-+]?\d[\d,.]*", str(value))
        if not match:
            return None
        number = float(match.group().replace(",", ""))
        return int(number) if number.is_integer() else number
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def local_extract(text: str) -> dict[str, Any]:
    aliases = {
        "shipper": r"shipper|exporter",
        "consignee": r"consignee|receiver",
        "notify_party": r"notify\s*party|notify",
        "port_of_loading": r"port\s*of\s*loading|load\s*port|pol",
        "port_of_discharge": r"port\s*of\s*discharge|discharge\s*port|pod",
        "container_count": r"container\s*(?:count|quantity|number)|containers",
        "gross_weight_kg": r"gross\s*weight|weight\s*\(?(?:kg|kgs)\)?|weight",
    }

    result = {field: None for field in FIELDS}
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        for field, alias in aliases.items():
            match = re.match(rf"(?:{alias})\s*[:=-]\s*(.+)$", cleaned, re.I)
            if match:
                result[field] = match.group(1).strip()

    for field in ("container_count", "gross_weight_kg"):
        result[field] = normalise(result[field], field)

    return result


def gemini_extract(text: str) -> tuple[dict[str, Any] | None, float]:
    key = secret("GEMINI_API_KEY")
    if not key or genai is None:
        return None, 0.0

    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "Extract exactly these fields from this shipping document: "
            f"{FIELDS}. Recognize aliases such as Load Port, POL, POD, Exporter, Receiver, "
            "Containers and Weight KG. Return only JSON with a 'fields' object and 'confidence' number. "
            "Use null when absent.\n\n"
            f"DOCUMENT:\n{text}"
        )
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json", "temperature": 0},
        )
        data = parse_json_payload(response.text)
        return {field: data.get("fields", {}).get(field) for field in FIELDS}, float(data.get("confidence", 70))
    except Exception:
        return None, 0.0


def extract(text: str) -> tuple[dict[str, Any], float, str]:
    fields, confidence = gemini_extract(text)
    if fields is not None:
        return fields, confidence, "Gemini 1.5 Flash"

    fields = local_extract(text)
    missing = sum(fields.get(field) in (None, "") for field in FIELDS)
    return fields, max(45.0, 100.0 - missing * 8), "Local labelled-text fallback"


def compare(si: dict[str, Any], bl: dict[str, Any], confidence: float) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    reasons: list[str] = []

    for field in FIELDS:
        left = si.get(field)
        right = bl.get(field)
        left_norm = normalise(left, field)
        right_norm = normalise(right, field)
        missing = left_norm is None or right_norm is None
        match = not missing and left_norm == right_norm

        row = {
            "field": field,
            "label": LABELS[field],
            "si": left,
            "bl": right,
            "match": match,
            "confidence": round(confidence if not missing else 45.0, 1),
        }
        rows.append(row)
        if not match:
            mismatches.append(row)
        if missing:
            reasons.append(f"{LABELS[field]} is missing or ambiguous")

    needs_review = confidence < 80 or bool(reasons)
    return {
        "fields": rows,
        "mismatches": mismatches,
        "result": "Mismatch detected" if mismatches else "No mismatch detected",
        "confidence": round(confidence, 1),
        "needs_human_review": needs_review,
        "review_reason": "; ".join(reasons) or ("Confidence below 80%" if confidence < 80 else ""),
    }


def persist(report: dict[str, Any]) -> None:
    if not firebase_admin:
        return
    service_json = secret("FIREBASE_SERVICE_ACCOUNT_JSON")
    if not service_json:
        return
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(json.loads(service_json)))
        firestore.client().collection("verification_reports").document(report["email_id"]).set(report)
    except Exception:
        pass


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "gemini": bool(secret("GEMINI_API_KEY") and genai),
        "firestore": bool(firebase_admin and secret("FIREBASE_SERVICE_ACCOUNT_JSON")),
    }


@app.get("/api/inbox")
def inbox() -> list[dict[str, Any]]:
    return [{key: value for key, value in email.items() if key not in {"si", "bl"}} for email in DEMO_EMAILS]


@app.post("/api/verify/demo/{email_id}")
def verify_demo(email_id: str) -> dict[str, Any]:
    email = next((item for item in DEMO_EMAILS if item["id"] == email_id), None)
    if not email or email["category"] != CATEGORIES[0]:
        raise HTTPException(404, "Document-comparison request not found")

    result = compare(email["si"], email["bl"], 92.0)
    report = {
        "email_id": email_id,
        "category": email["category"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Demo shipment record",
        **result,
    }
    persist(report)
    return report


async def read_document(file: UploadFile) -> str:
    content = await file.read()
    filename = (file.filename or "").lower()
    if filename.endswith(".pdf"):
        if PdfReader is None:
            raise HTTPException(500, "Install pypdf to process PDF files")
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
    return content.decode("utf-8", errors="replace")


@app.post("/api/verify/upload")
async def verify_upload(si: UploadFile = File(...), bl: UploadFile = File(...)) -> dict[str, Any]:
    si_text = await read_document(si)
    bl_text = await read_document(bl)
    si_fields, si_conf, si_source = extract(si_text)
    bl_fields, bl_conf, bl_source = extract(bl_text)

    result = compare(si_fields, bl_fields, min(si_conf, bl_conf))
    report = {
        "email_id": "upload",
        "category": CATEGORIES[0],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"{si_source}; {bl_source}",
        **result,
    }
    persist(report)
    return report


@app.get("/api/reviews")
def reviews() -> list[dict[str, Any]]:
    return []


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=True)
