"""
Drafting engine over HTTP, joined to the context and verification modules.

  GET  /draft/skills   the skills the engine knows (from drafting_engine/skills/*.yaml)
  POST /draft/run      run a skill. Optional extras:
                         max_context_tokens  long source_text is cut to the sections that matter (context_opt)
                         verify              citations in the draft are checked (citation_verifier)
                         dry_run             true/false. Leave out to follow the engine rule (no LLM_MODEL = dry run)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import Field

from drafting_engine.engine import run_skill
from drafting_engine.models import DraftRequest
from drafting_engine.skill_loader import load_skills

from citation_verifier import verify_draft, anthropic_completer
from context_opt import est_tokens, optimize

router = APIRouter(prefix="/draft")

# revise_draft returns the whole edited document, so cutting its input would lose text
NEEDS_FULL_TEXT = {"revise_draft"}
MAX_TEXT = 400_000


class RunRequest(DraftRequest):
    verify: bool = False
    max_context_tokens: int = Field(6000, ge=500, le=200_000)
    dry_run: Optional[bool] = None


def _dump(model) -> dict:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@router.get("/skills")
def skills():
    out = []
    for sid, s in load_skills().items():
        inputs = s.get("inputs", {})
        out.append({
            "id": sid,
            "name": s.get("name", sid),
            "category": s.get("category", ""),
            "description": s.get("description", ""),
            "triggers": s.get("triggers", []),
            "required": inputs.get("required", []),
            "optional": inputs.get("optional", []),
            "requires_source_text": bool(s.get("requires_source_text")),
            "uses_reference_style": bool(s.get("use_reference_style")),
        })
    return {"skills": out}


def _fit_source(req: RunRequest) -> dict:
    """Cut a long source_text to the budget. Returns a report the UI can show."""
    text = req.source_text or ""
    report = {"applied": False, "budget": req.max_context_tokens, "source_tokens": est_tokens(text)}
    if not text.strip() or report["source_tokens"] <= req.max_context_tokens:
        return report
    if req.skill_id in NEEDS_FULL_TEXT:
        report["note"] = "The document is longer than the budget, but this skill edits the whole text, so all of it was sent."
        return report
    opt = optimize(text, req.instruction, req.max_context_tokens)
    req.source_text = opt["text"]
    report.update({
        "applied": True,
        "final_tokens": opt["final_tokens"],
        "saved_pct": opt["saved_pct"],
        "sections": opt["sections"],
        "citations": opt["citations"],
        "note": "The document was longer than the budget. Sections that best match the instruction were kept, in their original wording.",
    })
    return report


@router.post("/run")
def run(req: RunRequest):
    if req.source_text and len(req.source_text) > MAX_TEXT:
        raise HTTPException(422, f"source_text is too long (max {MAX_TEXT} characters).")
    if req.skill_id not in load_skills():
        raise HTTPException(404, f"Unknown skill '{req.skill_id}'. Use GET /draft/skills.")

    context = _fit_source(req)
    engine_req = DraftRequest(
        skill_id=req.skill_id, instruction=req.instruction, inputs=req.inputs, source_text=req.source_text,
        reference_text=req.reference_text, context_chunks=req.context_chunks, model=req.model,
    )
    try:
        result = run_skill(engine_req, dry_run=req.dry_run)
    except Exception as e:                         # model/key/package problems: say what, never leak secrets
        raise HTTPException(502, f"The drafting model call failed ({type(e).__name__}). Check LLM_PROVIDER, LLM_MODEL and the API key in .env.")

    out = _dump(result)
    out["context"] = context
    is_dry = out["draft_md"].startswith("[DRY RUN")
    out["verify_flags"] = 0 if is_dry else out["draft_md"].count("[VERIFY]")
    if req.verify:
        if not out["draft_md"].strip() or is_dry or out["missing_inputs"]:
            out["verification"] = None
            out["verification_note"] = "Nothing to verify: no real draft was produced."
        else:
            out["verification"] = verify_draft(out["draft_md"], completer=anthropic_completer())
    return out
