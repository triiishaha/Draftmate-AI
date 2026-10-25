"""Skills library, voice agent, models and prompt meter (the /api router)."""
import os, sys, types
os.environ.setdefault("GEMINI_API_KEY", "test-key")
if "google.genai" not in sys.modules:
    try:
        from google import genai  # noqa: F401
    except ImportError:
        g, gg = types.ModuleType("google"), types.ModuleType("google.genai")
        gg.Client = lambda **k: object(); g.genai = gg
        sys.modules["google"], sys.modules["google.genai"] = g, gg
from fastapi.testclient import TestClient
from main import app

c = TestClient(app)

def test_skills_library_has_many_skills():
    r = c.get("/api/skills").json()
    assert len(r["skills"]) >= 60 and "Drafting & Writing" in r["categories"]

def test_mention_routes_to_skill():
    assert c.post("/api/skills/route", json={"query": "@contract-review check this"}).json()["skill"]["id"] == "contract-review"

def test_voice_delete_needs_confirmation():
    r = c.post("/api/voice/command", json={"session_id": "t1", "transcript": "delete paragraph two"}).json()
    assert r["status"] == "awaiting_confirmation" and r["requires_confirmation"]
    assert c.post("/api/voice/confirm", json={"session_id": "t1", "accept": False}).json()["status"] == "cancelled"

def test_voice_replace_and_models():
    r = c.post("/api/voice/command", json={"session_id": "t2", "transcript": "replace foo with bar"}).json()
    assert r["intent"] == "replace_text" and r["params"] == {"find": "foo", "replace": "bar"}
    assert c.get("/api/models").json()
