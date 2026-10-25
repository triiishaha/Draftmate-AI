import io
import sys

import pytest
from fastapi.testclient import TestClient

import main
import routes_draft
import doc_store
from drafting_engine.models import DraftResult

docx = pytest.importorskip("docx")
client = TestClient(main.app)

LONG = "\n\n".join(
    [f"{i}. {t}\n\nTerms about {t.lower()}. " + "Standard filler wording applies here. " * 90
     for i, t in enumerate(["Payment", "Termination", "Confidentiality", "Governing Law", "Liability", "Notices"], 1)]
)


def docx_bytes():
    d = docx.Document()
    d.add_heading("SERVICE AGREEMENT", 1)
    d.add_heading("1. Payment Terms", 2)
    d.add_paragraph("The client must pay within 30 days.")
    d.add_heading("1.1 Late Fees", 3)
    d.add_paragraph("Late payments may incur additional fees.")
    b = io.BytesIO(); d.save(b)
    return b.getvalue()


def test_every_module_is_mounted():
    paths = set(client.get("/openapi.json").json()["paths"])
    for p in ["/verify", "/research", "/contract/redline", "/contract/compare", "/contract/deadlines", "/contract/risk",
              "/contract/impact", "/contract/laws", "/store/templates", "/store/documents", "/doc/convert",
              "/context/optimize", "/document/process", "/voice/parse", "/draft/skills", "/draft/run", "/status"]:
        assert p in paths, p


def test_status_never_shows_secret_values(monkeypatch):
    monkeypatch.setenv("INDIANKANOON_API_TOKEN", "super-secret-token-123")
    monkeypatch.setenv("GEMINI_API_KEY", "another-secret-456")
    r = client.get("/status")
    body = r.text
    assert r.status_code == 200 and "super-secret-token-123" not in body and "another-secret-456" not in body
    assert r.json()["keys_set"]["INDIANKANOON_API_TOKEN"] is True


def test_cors_allows_the_react_app():
    r = client.options("/draft/run", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options("/draft/run", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_draft_skills_listed():
    ids = {s["id"] for s in client.get("/draft/skills").json()["skills"]}
    assert {"legal_notice", "agreement_drafting", "contract_review", "revise_draft", "summarise_document"} <= ids


def test_draft_dry_run_and_missing_inputs():
    ok = client.post("/draft/run", json={"skill_id": "legal_notice", "instruction": "Notice for unpaid rent", "dry_run": True,
                                         "inputs": {"sender": "A", "recipient": "B", "facts": "Rent unpaid", "relief_sought": "Pay"}}).json()
    assert "DRY RUN" in ok["draft_md"] and ok["missing_inputs"] == []
    miss = client.post("/draft/run", json={"skill_id": "legal_notice", "instruction": "x", "dry_run": True, "inputs": {"sender": "A"}}).json()
    assert set(miss["missing_inputs"]) == {"recipient", "facts", "relief_sought"}
    assert client.post("/draft/run", json={"skill_id": "nope", "instruction": "x"}).status_code == 404


def test_long_source_is_cut_to_the_budget_before_drafting():
    r = client.post("/draft/run", json={"skill_id": "summarise_document", "instruction": "What happens on termination?",
                                        "source_text": LONG, "max_context_tokens": 800, "dry_run": True}).json()
    c = r["context"]
    assert c["applied"] and c["final_tokens"] <= 800 and c["saved_pct"] > 40
    user = r["draft_md"].split("--- USER ---")[1]
    assert "Terms about termination" in user and "Terms about notices" not in user       # kept vs left out
    assert "[Omitted" in user                                                             # and the model is told something was left out


def test_revise_draft_keeps_the_whole_text():
    r = client.post("/draft/run", json={"skill_id": "revise_draft", "instruction": "Change 30 to 15", "source_text": LONG,
                                        "inputs": {"change_request": "Change 30 days to 15 days"}, "max_context_tokens": 500, "dry_run": True}).json()
    assert r["context"]["applied"] is False and "all of it was sent" in r["context"]["note"]
    assert "Notices" in r["draft_md"]


def test_verify_runs_on_a_real_draft_only(monkeypatch):
    fake = lambda **k: DraftResult(skill_id="legal_notice", draft_md="As held in Maneka Gandhi v. Union of India, AIR 1978 SC 597.")
    monkeypatch.setattr(routes_draft, "run_skill", lambda req, dry_run=None: fake())
    calls = []
    monkeypatch.setattr(routes_draft, "verify_draft", lambda text, completer=None: calls.append(text) or {"summary": {"verified": 1, "partially_verified": 0, "unverified": 0}, "items": []})
    body = {"skill_id": "legal_notice", "instruction": "x", "verify": True, "inputs": {"sender": "A", "recipient": "B", "facts": "f", "relief_sought": "r"}}
    r = client.post("/draft/run", json=body).json()
    assert r["verification"]["summary"]["verified"] == 1 and "Maneka Gandhi" in calls[0]
    # a dry run is not a real draft: nothing is verified
    monkeypatch.undo()
    r2 = client.post("/draft/run", json={**body, "dry_run": True}).json()
    assert r2["verification"] is None and "Nothing to verify" in r2["verification_note"]


def test_model_failure_is_a_clean_502_without_details(monkeypatch):
    def boom(req, dry_run=None):
        raise RuntimeError("401 invalid key sk-SECRET")
    monkeypatch.setattr(routes_draft, "run_skill", boom)
    r = client.post("/draft/run", json={"skill_id": "summarise_document", "instruction": "x", "source_text": "abc"})
    assert r.status_code == 502 and "SECRET" not in r.text and "RuntimeError" in r.text


def test_document_process_without_ai():
    r = client.post("/document/process", files={"file": ("a.docx", docx_bytes())}, data={"command": "Explain clause 1.1", "ai": "false"}).json()
    assert r["action"] == "explain_clause" and r["context"]["found"] and "additional fees" in r["context"]["text"]
    assert r["optimization"]["strategy"] == "clause" and r["conversion"]["engine"] in {"built-in", "MarkItDown"}
    assert r["ai_response"] is None and r["ai_error"] is None


def test_document_process_ai_failure_keeps_the_result(monkeypatch):
    fake = type(sys)("ai_service")
    def boom(**k): raise ValueError("GEMINI_API_KEY not found")
    fake.generate_document_response = boom
    monkeypatch.setitem(sys.modules, "ai_service", fake)
    r = client.post("/document/process", files={"file": ("a.docx", docx_bytes())}, data={"command": "Summarise this agreement", "ai": "true"})
    j = r.json()
    assert r.status_code == 200 and j["ai_response"] is None and "unavailable" in j["ai_error"] and j["context"]["found"]


def test_document_process_validation():
    f = {"file": ("a.docx", docx_bytes())}
    assert client.post("/document/process", files=f, data={"command": "  "}).status_code == 422
    assert client.post("/document/process", files={"file": ("a.exe", b"MZ")}, data={"command": "Summarise"}).status_code == 422
    assert client.post("/document/process", files={"file": ("a.docx", b"")}, data={"command": "Summarise"}).status_code == 422


def test_voice_parse():
    assert client.post("/voice/parse", json={"transcript": "Rewrite clause two point one"}).json()["action"] in {"rewrite_clause", "general_instruction"}
    r = client.post("/voice/parse", json={"transcript": "Explain clause four"}).json()
    assert r["action"] == "explain_clause" and r["target_clause"] == "4"


def test_old_routes_still_work(tmp_path):
    doc_store.set_store(doc_store.Store(str(tmp_path / "i.db")))
    try:
        assert client.post("/contract/risk", json={"text": "1. Termination. The Company may terminate at any time without notice."}).status_code == 200
        assert client.post("/store/templates", json={"name": "NDA", "text": "text"}).status_code == 200
        assert client.post("/context/optimize", json={"text": LONG, "query": "termination", "max_tokens": 600}).json()["final_tokens"] <= 600
        assert client.post("/doc/convert", files={"file": ("a.docx", docx_bytes())}).json()["markdown"]
    finally:
        doc_store.set_store(None)
