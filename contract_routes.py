"""FastAPI router for Module 3. In main.py:
    from contract_routes import router as contract_router
    app.include_router(contract_router)
Needs: fastapi, python-multipart (uploads). Optional: pypdf, python-docx (PDF/DOCX text)."""
import io
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import contract_analysis as ca
import contract_comparison as cc
import contract_store as store

router = APIRouter(prefix="/api/contract", tags=["contract-intelligence"])

class TextIn(BaseModel):
    text: str
class CompareIn(BaseModel):
    text_a: str
    text_b: str
class ImpactIn(BaseModel):
    text: str
    topic: str
class TemplateIn(BaseModel):
    name: str
    text: str
    category: str = "General"
class VersionIn(BaseModel):
    doc: str
    text: str
    note: str = ""

@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    data, name = await file.read(), (file.filename or "").lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader
            text = "\n\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        elif name.endswith(".docx"):
            import docx
            text = "\n\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
        else:
            text = data.decode("utf-8", errors="ignore")
    except ImportError as e:
        raise HTTPException(400, f"Install the parser for this file type: {e.name}")
    if not text.strip():
        raise HTTPException(422, "No text found. Scanned PDFs need OCR first.")
    return {"text": text, "filename": file.filename}

@router.post("/analyze")
def analyze(body: TextIn): return ca.analyze_risks(body.text)

@router.post("/compare")
def compare(body: CompareIn): return cc.redline(body.text_a, body.text_b)

@router.post("/deadlines")
def deadlines(body: TextIn): return {"items": ca.extract_deadlines(body.text)}

@router.get("/impact/topics")
def impact_topics(): return ca.list_topics()

@router.post("/impact")
def impact(body: ImpactIn): return ca.impact_map(body.text, body.topic)

@router.get("/templates")
def templates(): return store.list_templates()
@router.get("/templates/{tid}")
def template(tid: str):
    t = store.get_template(tid)
    if not t: raise HTTPException(404, "Template not found")
    return t
@router.post("/templates")
def add_template(body: TemplateIn): return store.save_template(body.name, body.text, body.category)
@router.delete("/templates/{tid}")
def del_template(tid: str):
    if not store.delete_template(tid): raise HTTPException(404, "Template not found")
    return {"deleted": tid}

@router.get("/versions")
def versions(): return store.list_docs()
@router.post("/versions")
def add_version(body: VersionIn): return store.add_version(body.doc, body.text, body.note)
@router.get("/versions/{vid}")
def version(vid: str):
    v = store.get_version(vid)
    if not v: raise HTTPException(404, "Version not found")
    return v
