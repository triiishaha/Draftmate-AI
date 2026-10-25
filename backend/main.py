"""
DraftMate AI: one backend for every Python module.

Run from this folder:   python3 -m uvicorn main:app --reload
Open:                   http://localhost:8000/docs   (all routes)     http://localhost:8000/status   (what is switched on)
"""
import importlib.util
import os
import sys

try:                                    # read .env (INDIANKANOON_API_TOKEN, GEMINI_API_KEY, LLM_* ...) if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from citation_verifier import router as verify_router        # POST /verify
from research import router as research_router               # GET /research, /research/doc/{id}, /research/answer; POST /research/summarize
from contract_intel import router as contract_router         # POST /contract/redline, /compare, /deadlines
from risk_radar import router as risk_router                 # POST /contract/risk
from impact_map import router as impact_router               # GET /contract/laws; POST /contract/impact
from doc_store import router as store_router                 # /store/templates, /store/documents ...
from doc_convert import router as convert_router             # POST /doc/convert
from context_opt import router as context_router             # POST /context/optimize
from routes_document import router as document_router       # POST /document/process, /voice/parse
from routes_draft import router as draft_router              # GET /draft/skills; POST /draft/run
from agent_routes import router as agent_router               # /api/skills, /api/models, /api/voice/*, /api/convert ...
from style_profile import router as style_router               # POST /style/profile (file), /style/analyze (text)
from testpage import router as test_router                   # /test, /demo

DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
ORIGINS = [o.strip() for o in os.getenv("DRAFTMATE_CORS", DEFAULT_ORIGINS).split(",") if o.strip()]

app = FastAPI(title="DraftMate AI backend", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])

for r in (verify_router, research_router, contract_router, risk_router, impact_router, store_router,
          convert_router, context_router, document_router, draft_router, agent_router, style_router, test_router):
    app.include_router(r)


@app.get("/status", tags=["status"])
def status():
    """What is switched on. Shows whether keys are set, never their values."""
    has = lambda name: importlib.util.find_spec(name) is not None
    return {
        "service": "DraftMate AI backend",
        "python": sys.version.split()[0],
        "cors_origins": ORIGINS,
        "keys_set": {
            "INDIANKANOON_API_TOKEN": bool(os.getenv("INDIANKANOON_API_TOKEN")),
            "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
            "LLM_MODEL (drafting engine)": bool(os.getenv("LLM_MODEL")),
        },
        "drafting_mode": "live" if os.getenv("LLM_MODEL") else "dry run (no model called)",
        "optional_packages": {
            "markitdown": has("markitdown"),
            "python-multipart (file upload)": has("multipart") or has("python_multipart"),
            "tiktoken": has("tiktoken"),
        },
        "tips": [t for t in (
            None if os.getenv("INDIANKANOON_API_TOKEN") else "Set INDIANKANOON_API_TOKEN for live case search and verification.",
            None if os.getenv("LLM_MODEL") else "Set LLM_PROVIDER, LLM_MODEL and the provider key to get real drafts (otherwise /draft/run is a dry run).",
            None if os.getenv("GEMINI_API_KEY") else "Set GEMINI_API_KEY for AI answers in /document/process.",
        ) if t],
    }
