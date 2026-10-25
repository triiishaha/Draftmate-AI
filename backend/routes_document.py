"""
Member 4 document pipeline over HTTP.

  POST /document/process   multipart: file (PDF/DOCX), command, max_tokens, ai
  POST /voice/parse        {"transcript": "..."} -> action and target clause
"""
from __future__ import annotations

import importlib.util

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from doc_convert import MAX_BYTES
from pipeline_service import process_document_command
from voice_service import parse_voice_command

router = APIRouter()


class VoiceReq(BaseModel):
    transcript: str = Field("", max_length=5000)


@router.post("/voice/parse")
def voice_parse(req: VoiceReq):
    return parse_voice_command(req.transcript)


def _process(filename: str, data: bytes, command: str, max_tokens: int, ai: bool) -> dict:
    if not command.strip():
        raise HTTPException(422, "Please enter a command.")
    if not data:
        raise HTTPException(422, "The file is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(422, f"The file is too large (max {MAX_BYTES // (1024 * 1024)} MB).")
    try:
        result = process_document_command(filename, data, command, max_tokens=max_tokens, generate_ai=False)
    except ValueError as e:
        raise HTTPException(422, str(e))
    result["ai_error"] = None
    if ai and result["context"].get("found") and result["action"] != "clarification_needed":
        try:
            from ai_service import generate_document_response      # needs GEMINI_API_KEY
            result["ai_response"] = generate_document_response(
                action=result["action"], context=result["context"], transcript=command)
        except Exception as e:                                       # no key, no network, quota: keep the rest of the result
            result["ai_error"] = f"AI response unavailable ({type(e).__name__}). The selected context is still returned."
    return result


if importlib.util.find_spec("multipart") or importlib.util.find_spec("python_multipart"):
    from fastapi import File, Form, UploadFile

    @router.post("/document/process")
    async def document_process(file: UploadFile = File(...), command: str = Form(...),
                               max_tokens: int = Form(6000), ai: bool = Form(True)):
        data = await file.read(MAX_BYTES + 1)
        return _process(file.filename or "", data, command, max(500, min(max_tokens, 200_000)), ai)
else:
    @router.post("/document/process")
    async def document_process_unavailable():
        raise HTTPException(501, "File upload needs python-multipart. Run: python3 -m pip install python-multipart")
