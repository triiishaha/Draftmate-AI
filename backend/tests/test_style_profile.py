import io
from style_profile import analyze

FORMAL = """RENTAL AGREEMENT

This Agreement is made at Pune between Mr. A Sharma (the "Landlord") and Ms. B Rao (the "Tenant").

WHEREAS the Landlord is the lawful owner of the premises and hereby agrees to let the same.

1. TERM
1.1 The Tenant shall pay the rent on or before the fifth day of each month, notwithstanding any dispute.
1.2 The Landlord shall not enter the premises without prior notice, pursuant to this Agreement.
(a) The Tenant shall maintain the premises.
(b) The Tenant shall not sublet the premises.

2. TERMINATION
2.1 Either party may terminate herein by thirty days notice. IN WITNESS WHEREOF the parties have signed.
"""
PLAIN = ("Hi, I'm writing to ask about the deposit. We moved out last month and I'd like it back. "
         "I think we left the flat clean and we don't owe anything. Can you please send it to my account? "
         "I'll wait for your reply and we can sort it out. Thanks so much for your help with this matter.")

def test_formal_reference_detected():
    p = analyze(FORMAL)
    assert p["ok"] and "formal" in p["tone"] and p["obligation_verb"] == "shall"
    assert "Landlord" in p["defined_terms"] and "decimal" in p["numbering"]
    assert not any("shall maintain" in h for h in p["headings"])
    assert "style only" in p["guide"]

def test_plain_reference_detected():
    assert "plain" in analyze(PLAIN)["tone"]

def test_too_short_rejected():
    assert analyze("Too short.")["ok"] is False

def test_endpoint_text_and_file():
    from fastapi.testclient import TestClient
    import os, sys, types
    os.environ.setdefault("GEMINI_API_KEY", "test-key")
    try:
        from google import genai  # noqa: F401
    except ImportError:
        g, gg = types.ModuleType("google"), types.ModuleType("google.genai")
        gg.Client = lambda **k: object(); g.genai = gg
        sys.modules["google"], sys.modules["google.genai"] = g, gg
    from main import app
    c = TestClient(app)
    assert c.post("/style/analyze", json={"text": FORMAL}).status_code == 200
    r = c.post("/style/profile", files={"file": ("ref.txt", io.BytesIO(FORMAL.encode()), "text/plain")})
    assert r.status_code == 200 and r.json()["filename"] == "ref.txt"
    assert c.post("/style/analyze", json={"text": "short"}).status_code == 422
