import io, os, sys, types
os.environ.setdefault("GEMINI_API_KEY", "test-key")
try:
    from google import genai  # noqa: F401
except ImportError:
    g, gg = types.ModuleType("google"), types.ModuleType("google.genai")
    gg.Client = lambda **k: object(); g.genai = gg
    sys.modules["google"], sys.modules["google.genai"] = g, gg
from docx import Document
from fastapi.testclient import TestClient
from main import app

c = TestClient(app)
TEXT = "LEGAL NOTICE\n\nTo,\nMr. Rao\n\n1. DEMAND\n\nYou are required to return the deposit within 15 days."

def test_docx_is_valid_word_file():
    r = c.post("/export/docx", json={"text": TEXT, "title": "Legal Notice"})
    assert r.status_code == 200 and r.content[:2] == b"PK"
    assert "attachment" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith('.docx"')
    paras = [p.text for p in Document(io.BytesIO(r.content)).paragraphs]
    assert "LEGAL NOTICE" in paras and any("return the deposit" in p for p in paras)
    heading = [p for p in Document(io.BytesIO(r.content)).paragraphs if p.text == "LEGAL NOTICE"][0]
    assert heading.runs[0].bold

def test_empty_rejected():
    assert c.post("/export/docx", json={"text": "  "}).status_code == 422
