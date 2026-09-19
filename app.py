import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

try:
    import google.generativeai as genai
except ImportError:  # Optional dependency during local UI-only runs.
    genai = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]
FIELD_LABELS = {
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
        "category": "document-comparison request",
        "status": "Needs review",
        "attachments": ["shipping_instruction.txt", "bill_of_lading.txt"],
        "preview": "Please verify the draft BL against the attached SI before release.",
        "si": {"shipper": "Northstar Trading Ltd", "consignee": "Harbor Retail GmbH", "notify_party": "Harbor Retail GmbH", "port_of_loading": "Singapore", "port_of_discharge": "Hamburg", "container_count": 3, "gross_weight_kg": 21800},
        "bl": {"shipper": "Northstar Trading Ltd", "consignee": "Harbor Retail GmbH", "notify_party": "Harbor Retail GmbH", "port_of_loading": "Singapore", "port_of_discharge": "Hamburg", "container_count": 4, "gross_weight_kg": 21800},
    },
    {"id": "IN-2402", "sender": "billing@searoute.example", "subject": "Invoice 8931 question", "category": "invoice query", "status": "Classified", "attachments": [], "preview": "Could you confirm the detention charge on invoice 8931?"},
    {"id": "IN-2403", "sender": "customer@atlas.example", "subject": "New SI for voyage 18E", "category": "new SI request", "status": "Classified", "attachments": ["new_si.txt"], "preview": "Attached is the new shipping instruction for the upcoming booking."},
    {"id": "IN-2404", "sender": "offers@unknown.example", "subject": "Exclusive offer — act now", "category": "spam", "status": "Classified", "attachments": [], "preview": "You have been selected for a limited-time offer."},
]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    return re.sub(r"\s+", " ", value)


def normalise(value: Any, field: str) -> Any:
    if value is None or value == "":
        return None
    if field in {"container_count", "gross_weight_kg"}:
        match = re.search(r"[-+]?\d[\d,.]*", str(value))
        if not match:
            return None
        try:
            number = float(match.group().replace(",", ""))
            return int(number) if number.is_integer() else number
        except ValueError:
            return None
    return re.sub(r"[^a-z0-9]", "", clean_text(value).lower())


def extract_from_text(text: str) -> Dict[str, Any]:
    """Small local extractor used when Gemini is unavailable or for a quick demo."""
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
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        for field, alias in aliases.items():
            match = re.match(rf"(?:{alias})\s*[:=-]\s*(.+)$", line, re.I)
            if match:
                result[field] = clean_text(match.group(1))
    for field in ("container_count", "gross_weight_kg"):
        result[field] = normalise(result[field], field)
    return result


def gemini_json(prompt: str) -> Optional[Dict[str, Any]]:
    key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)
    if not key or genai is None:
        return None
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json", "temperature": 0})
        return json.loads(response.text)
    except Exception:
        return None


def classify(email: Dict[str, Any]) -> Tuple[str, float, str]:
    prompt = f'''Classify this shipping inbox email into exactly one of {CATEGORIES}. Return JSON with category and confidence (0-100).\nSubject: {email.get("subject", "")}\nBody: {email.get("preview", "")}'''
    answer = gemini_json(prompt)
    if answer and answer.get("category") in CATEGORIES:
        return answer["category"], float(answer.get("confidence", 80)), "Gemini classification"
    return email.get("category", "general message"), 96.0, "Local demo classifier"


def extract_document(text: str) -> Tuple[Dict[str, Any], float, str]:
    prompt = f'''Extract exactly these fields from the shipping document: {FIELDS}. Recognize aliases such as Load Port, POL, Discharge Port, POD, Exporter, Receiver, Containers, and Weight (KG). Return JSON with keys fields (object), confidence (0-100), missing_fields (array). Use null when absent.\nDOCUMENT:\n{text}'''
    answer = gemini_json(prompt)
    if answer and isinstance(answer.get("fields"), dict):
        fields = {key: answer["fields"].get(key) for key in FIELDS}
        return fields, float(answer.get("confidence", 70)), "Gemini extraction"
    fields = extract_from_text(text)
    missing = [FIELD_LABELS[f] for f in FIELDS if fields.get(f) in (None, "")]
    return fields, max(45.0, 100.0 - len(missing) * 8), "Local label extractor"


def compare(si: Dict[str, Any], bl: Dict[str, Any], confidence: float) -> Dict[str, Any]:
    rows, mismatches, reasons = [], [], []
    for field in FIELDS:
        left, right = si.get(field), bl.get(field)
        left_n, right_n = normalise(left, field), normalise(right, field)
        missing = left_n is None or right_n is None
        match = not missing and left_n == right_n
        row = {"field": field, "label": FIELD_LABELS[field], "si": left, "bl": right, "match": match, "confidence": round(confidence if not missing else 45.0, 1)}
        rows.append(row)
        if not match:
            mismatches.append(row)
        if missing:
            reasons.append(f"{FIELD_LABELS[field]} is missing or ambiguous")
    needs_review = confidence < 80 or bool(reasons)
    return {"mismatches": mismatches, "rows": rows, "needs_review": needs_review, "review_reason": "; ".join(reasons) or ("AI confidence below 80%" if confidence < 80 else ""), "result": "Mismatch detected" if mismatches else "No mismatch detected"}


def file_text(uploaded_file) -> str:
    raw = uploaded_file.read()
    if uploaded_file.name.lower().endswith(".pdf"):
        if PdfReader is None:
            return "PDF support needs pypdf installed."
        try:
            return "\n".join(page.extract_text() or "" for page in PdfReader(raw).pages)
        except Exception as exc:
            return f"PDF extraction failed: {exc}"
    return raw.decode("utf-8", errors="replace")


def make_report(email: Dict[str, Any], si: Dict[str, Any], bl: Dict[str, Any], confidence: float, source: str) -> Dict[str, Any]:
    comparison = compare(si, bl, confidence)
    return {"email_id": email.get("id", "upload"), "category": "document-comparison request", "generated_at": datetime.utcnow().isoformat() + "Z", "extraction_source": source, "confidence": round(confidence, 1), "needs_human_review": comparison["needs_review"], "review_reason": comparison["review_reason"], "result": comparison["result"], "mismatches": comparison["mismatches"], "fields": comparison["rows"]}


st.set_page_config(page_title="InScout | Shipment desk", page_icon="◈", layout="wide")
st.markdown("""<style> .block-container{padding-top:2rem;max-width:1200px}.hero{padding:1.4rem 1.6rem;border:1px solid #dce5e6;border-radius:16px;background:linear-gradient(115deg,#f4faf8,#fff)}.eyebrow{color:#157f72;font-size:.75rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}.muted{color:#667477}.pill{display:inline-block;padding:.2rem .55rem;border-radius:99px;background:#e8f4f0;color:#176e63;font-size:.8rem;font-weight:600}</style>""", unsafe_allow_html=True)

if "reports" not in st.session_state:
    st.session_state.reports = {}

st.markdown('<div class="hero"><div class="eyebrow">InScout · shipment desk</div><h1>Clearer documents. Fewer surprises.</h1><p class="muted">A practical review queue for sorting inbox traffic and checking SI drafts against BL drafts.</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Workspace")
    page = st.radio("Go to", ["Inbox", "Compare documents", "Review queue"], label_visibility="collapsed")
    st.divider()
    gemini_on = bool(os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None))
    st.caption(f"AI connection: {'ready' if gemini_on else 'local demo mode'}")
    st.caption("Review threshold: 80%")

if page == "Inbox":
    emails = DEMO_EMAILS
    st.subheader("Inbox triage")
    a, b, c, d = st.columns(4)
    a.metric("Inbox today", len(emails))
    b.metric("Checks found", sum(x["category"] == CATEGORIES[0] for x in emails))
    c.metric("Needs review", len(st.session_state.reports))
    d.metric("Automation", "Ready" if gemini_on else "Demo")
    st.write("")
    for email in emails:
        category, confidence, method = classify(email)
        with st.container(border=True):
            left, middle, right = st.columns([2.5, 3, 1])
            left.markdown(f"**{email['subject']}**\n\n<span class='muted'>{email['sender']} · {email['id']}</span>", unsafe_allow_html=True)
            middle.write(email["preview"])
            middle.caption(f"{category} · {confidence:.0f}% · {method}")
            if right.button("Open", key=f"open-{email['id']}"):
                st.session_state.selected_email = email["id"]
                st.session_state.page_hint = "Compare documents"
            right.caption(" · ".join(email["attachments"]) if email["attachments"] else "No attachments")
    st.info("Demo records are included so the interface works before the organizer ZIP is added. Replace DEMO_EMAILS with loader.py output when available.")

elif page == "Compare documents":
    st.subheader("Compare SI and BL")
    st.caption("Upload plain-text files for the fastest path. PDF text extraction is also supported when pypdf is installed.")
    selected = st.selectbox("Or choose a demo verification request", [e["id"] for e in DEMO_EMAILS if e["category"] == CATEGORIES[0]])
    selected_email = next(e for e in DEMO_EMAILS if e["id"] == selected)
    si_file = st.file_uploader("Shipping Instruction (SI)", type=["txt", "pdf"], key="si")
    bl_file = st.file_uploader("Bill of Lading (BL)", type=["txt", "pdf"], key="bl")
    if st.button("Run verification", type="primary"):
        if si_file and bl_file:
            si, si_conf, si_source = extract_document(file_text(si_file)); bl, bl_conf, bl_source = extract_document(file_text(bl_file))
            confidence, source = min(si_conf, bl_conf), f"{si_source}; {bl_source}"
        else:
            si, bl, confidence, source = selected_email["si"], selected_email["bl"], 92.0, "Demo shipment record"
        report = make_report(selected_email, si, bl, confidence, source)
        st.session_state.reports[report["email_id"]] = report
    if st.session_state.reports.get(selected_email):
        report = st.session_state.reports[selected_email]
        st.success(report["result"])
        x, y, z = st.columns(3); x.metric("Confidence", f"{report['confidence']:.0f}%"); y.metric("Mismatches", len(report["mismatches"])); z.metric("Decision", "Human review" if report["needs_human_review"] else "Auto-pass")
        if report["needs_human_review"]: st.warning(report["review_reason"] or "This comparison needs a human check.")
        st.dataframe(report["fields"], column_config={"match": st.column_config.CheckboxColumn("Match")}, hide_index=True, use_container_width=True)
        st.download_button("Download JSON report", json.dumps(report, indent=2), file_name=f"{report['email_id']}-report.json", mime="application/json")

else:
    st.subheader("Human review queue")
    reports = list(st.session_state.reports.values())
    if not reports:
        st.success("Nothing is waiting for review.")
    for report in reports:
        if report["needs_human_review"]:
            with st.container(border=True):
                st.markdown(f"**{report['email_id']}** · {report['result']} · {report['confidence']:.0f}%")
                st.caption(report["review_reason"] or "Mismatch requires operator confirmation.")
                st.dataframe(report["mismatches"], hide_index=True, use_container_width=True)
                if st.button("Mark reviewed", key=f"review-{report['email_id']}"):
                    report["needs_human_review"] = False
                    st.rerun()
