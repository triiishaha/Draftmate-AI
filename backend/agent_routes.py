"""FastAPI router: skills library, document conversion, context optimisation, prompt meter, voice.
In main.py:   from agent_routes import router as agent_router;  app.include_router(agent_router)
Needs: fastapi, python-multipart. Recommended: markitdown[all], tiktoken, anthropic."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import skills_registry as registry
import file_to_markdown as converter
import token_optimizer as tokens
import voice_agent as voice
import llm_client as llm

router = APIRouter(prefix="/api", tags=["agent"])

class Doc(BaseModel):
    name: str = "document"
    markdown: str
class RouteIn(BaseModel):
    query: str
class RunIn(BaseModel):
    skill_id: str
    instruction: str
    documents: List[Doc] = []
    tier: str = "gemini"
    budget_tokens: int = 3000
class ContextIn(BaseModel):
    documents: List[Doc]
    query: str
    budget_tokens: int = 3000
class PromptIn(BaseModel):
    prompt: str
class CustomIn(BaseModel):
    name: str
    description: str
    instruction: str
    needs_document: bool = False
class VoiceIn(BaseModel):
    session_id: str
    transcript: str
class ConfirmIn(BaseModel):
    session_id: str
    accept: bool

@router.get("/skills")
def skills(q: Optional[str] = None, category: Optional[str] = None, audience: Optional[str] = None):
    return {"skills": registry.list_skills(q, category, audience), "categories": registry.categories()}
@router.post("/skills/route")
def skills_route(body: RouteIn): return registry.route(body.query)
@router.post("/skills/custom")
def skills_custom(body: CustomIn): return registry.save_custom(body.name, body.description, body.instruction, body.needs_document)
@router.get("/skills/{skill_id}")
def skill_detail(skill_id: str):
    s = registry.get(skill_id)
    if not s: raise HTTPException(404, "Skill not found")
    return s

@router.post("/skills/run")
def skills_run(body: RunIn):
    s = registry.get(body.skill_id)
    if not s: raise HTTPException(404, "Skill not found")
    if s["needs_document"] and not body.documents:
        raise HTTPException(422, f"{s['name']} needs a document. Upload or select one first.")
    ctx = tokens.build_context([d.dict() for d in body.documents], body.instruction, body.budget_tokens)
    user = body.instruction + (f"\n\n--- REFERENCE MATERIAL ---\n{ctx['context']}" if ctx["context"] else "")
    out = llm.complete(registry.system_prompt(s), user, body.tier)
    return {"skill": registry.public(s), "result": out, "context_stats": ctx["stats"]}

@router.get("/models")
def models(): return llm.list_models()

@router.post("/convert")
async def convert(file: UploadFile = File(...)):
    try: return converter.convert_bytes(await file.read(), file.filename or "")
    except ValueError as e: raise HTTPException(422, str(e))
    except ImportError as e: raise HTTPException(400, f"Missing parser: {e.name}")

@router.post("/context/build")
def context_build(body: ContextIn): return tokens.build_context([d.dict() for d in body.documents], body.query, body.budget_tokens)
@router.post("/prompt/score")
def prompt_score(body: PromptIn): return tokens.prompt_score(body.prompt)

@router.post("/voice/command")
def voice_command(body: VoiceIn): return voice.parse(body.session_id, body.transcript)
@router.post("/voice/confirm")
def voice_confirm(body: ConfirmIn): return voice.confirm(body.session_id, body.accept)
