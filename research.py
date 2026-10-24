"""
Legal Research search (Member 2).  Evidence-first: every result is a real Indian Kanoon
document with a link and the extract the source itself returned. Nothing here is generated
by an AI model, so nothing can be invented.

Mount it next to the verifier:
    from citation_verifier import router as verify_router
    from research import router as research_router
    app.include_router(verify_router)
    app.include_router(research_router)

Endpoint:  GET /research?q=breach of contract&type=supremecourt&page=0
"""
from __future__ import annotations

import re
from dataclasses import asdict

from citation_verifier import (
    IndianKanoonSource, LocalCacheSource, SourceHit, _norm, _name_sim, PARTY_STOPWORDS,
)

# Indian Kanoon "doctypes:" filter values we expose to the UI.
DOCTYPES = {"all": "", "supremecourt": "doctypes: supremecourt", "laws": "doctypes: laws"}
MAX_QUERY_CHARS = 200


def _build_query(q: str, doctype: str) -> str:
    q = " ".join(q.split())[:MAX_QUERY_CHARS]
    flt = DOCTYPES.get(doctype, "")
    return f"{q} {flt}".strip()


def _kind(h: SourceHit) -> str:
    court = (h.court or "").lower()
    title = h.title.lower()
    if (re.match(r"^(section|article|rule)\b", title)
            or any(w in court for w in ("central act", "constitution", "state act", "rules"))
            or (" act" in title and " vs " not in title)):
        return "law"
    return "judgment"


def _card(h: SourceHit) -> dict:
    d = asdict(h)
    d["snippet"] = re.sub(r"\s+", " ", d["snippet"] or "").strip()   # no stray line breaks
    d["kind"] = _kind(h)
    if d["kind"] == "law" and (d["court"] or "").endswith("- Section"):
        d["court"] = "Central Act"          # Indian Kanoon's label is "Union of India - Section"
    return d


def _rank(q: str, hits: list[SourceHit]) -> list[SourceHit]:
    """Stable re-rank: results whose TITLE matches the query come first.
    Everything else keeps Indian Kanoon's own order. Only reorders, never adds."""
    return sorted(hits, key=lambda h: 0 if _name_sim(q, h.title) >= 0.55 else 1)


def _cache_search(q: str, cache: LocalCacheSource) -> list[SourceHit]:
    toks = [t for t in _norm(q).split() if t not in PARTY_STOPWORDS and len(t) > 2]
    if not toks:
        return []
    out = []
    for h in cache.entries:
        title = _norm(h.title)
        if all(t in title for t in toks):
            out.append(h)
    return out


def research(q: str, doctype: str = "all", page: int = 0,
             source: IndianKanoonSource | None = None,
             cache: LocalCacheSource | None = None) -> dict:
    """Search legal topics, laws and case names. Returns real sources only."""
    q = (q or "").strip()
    if len(q) < 2:
        return {"query": q, "count": 0, "results": [], "origin": None,
                "note": "Type a topic, a law or a case name."}

    source = source or IndianKanoonSource()
    cache = cache or LocalCacheSource()
    page = max(0, int(page))

    hits: list[SourceHit] = []
    origin = None
    live_full = False
    if source.token:
        try:
            docs = source._call(_build_query(q, doctype)) if page == 0 else _call_page(source, _build_query(q, doctype), page)
        except Exception:                      # never crash the page
            docs = []
        hits = _rank(q, [source._to_hit(d) for d in docs[:10]])
        origin = "indiankanoon" if hits else None
        live_full = len(docs) >= 10
    if not hits and page == 0:                  # offline / no token / nothing found
        hits = _cache_search(q, cache)[:10]
        origin = "cache" if hits else None

    note = None
    if not hits and page > 0:
        note = "No more results."
    elif not hits:
        note = ("No sources found. Try a case name, a law name or fewer words. "
                "If this keeps happening, the Indian Kanoon token may be missing.")
    elif origin == "cache":
        note = "Showing saved demo results (offline). Live search was unavailable or found nothing."

    return {"query": q, "type": doctype, "page": page, "count": len(hits),
            "results": [_card(h) for h in hits], "origin": origin, "note": note,
            "has_more": bool(live_full and origin == "indiankanoon")}


def _call_page(source: IndianKanoonSource, query: str, page: int) -> list[dict]:
    import requests
    try:
        r = requests.post(f"{source.BASE}/search/",
                          params={"formInput": query, "pagenum": page},
                          headers={"Authorization": f"Token {source.token}"},
                          timeout=source.timeout)
        r.raise_for_status()
        return r.json().get("docs", [])
    except (requests.RequestException, ValueError):
        return []


try:
    from fastapi import APIRouter, Query

    router = APIRouter()

    @router.get("/research")
    def research_endpoint(q: str = Query(..., min_length=2, max_length=MAX_QUERY_CHARS),
                          type: str = "all", page: int = 0):
        return research(q, type, page)
except ImportError:
    router = None
