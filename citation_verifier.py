"""
Citation verification module for DraftMate / Legal Drafting Studio.

Pipeline:
  draft text -> extract_citations() -> verify_citation() per item -> VerificationReport

Status meanings (match the PS):
  verified           - found in an external legal source AND key details match
  partially_verified - found something close, but some detail differs (year, court, name)
  unverified         - nothing found; never invent an authority

Sources are pluggable adapters. Order of lookup:
  1. LOCAL_CACHE  (pre-fetched demo data, works offline, guarantees a clean demo)
  2. IndianKanoonSource (needs INDIANKANOON_API_TOKEN env var)
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from difflib import SequenceMatcher
from typing import Protocol

import requests

# ----------------------------------------------------------------------------
# 1. Data models
# ----------------------------------------------------------------------------

@dataclass
class Citation:
    raw: str                    # exact text found in the draft
    kind: str                   # "case" | "statute"
    name: str | None = None     # e.g. "Kesavananda Bharati v. State of Kerala"
    year: str | None = None
    reporter: str | None = None  # e.g. "AIR", "SCC", "SCR"
    court: str | None = None
    section: str | None = None   # for statutes
    act: str | None = None
    span: tuple[int, int] = (0, 0)  # char offsets so the UI can highlight


@dataclass
class SourceHit:
    title: str
    url: str
    year: str | None = None
    court: str | None = None
    snippet: str = ""


@dataclass
class Verdict:
    citation: Citation
    status: str                  # verified | partially_verified | unverified
    score: float                 # 0..1 confidence
    reasons: list[str] = field(default_factory=list)
    source: SourceHit | None = None


# ----------------------------------------------------------------------------
# 2. Extraction (regex first; cheap, deterministic, explainable)
#    Optional: add an LLM pass for citations regex misses.
# ----------------------------------------------------------------------------

PARTY = r"[A-Z][A-Za-z0-9&.'\-]*(?:\s+(?:[A-Z][A-Za-z0-9&.'\-]*|of|and|the|for|vs?\.?))*"
V = r"(?:v\.?|vs\.?|versus)"

# "Kesavananda Bharati v. State of Kerala (1973) 4 SCC 225" / "... AIR 1973 SC 1461"
CASE_WITH_CITE = re.compile(
    rf"(?P<name>{PARTY}\s+{V}\s+{PARTY})\s*,?\s*"
    r"(?:\(\s*(?P<y1>\d{4})\s*\)\s*\d+\s*(?P<rep1>SCC|SCR|SCALE)\s*\d+"
    r"|(?P<rep2>AIR)\s*(?P<y2>\d{4})\s*(?P<ct>SC|[A-Z]{2,4})\s*\d+"
    r"|\(\s*(?P<y3>\d{4})\s*\)\s*\d+\s*(?P<rep3>SCC\s*OnLine\s*[A-Za-z]+)\s*\d+)"
)

# Bare case name, no reporter: "Maneka Gandhi v. Union of India"
CASE_NAME_ONLY = re.compile(rf"(?P<name>{PARTY}\s+{V}\s+{PARTY})")

# "Section 138 of the Negotiable Instruments Act, 1881"  /  "Sec. 420 IPC"
STATUTE = re.compile(
    r"(?:Section|Sec\.?|S\.|Article|Art\.?)\s*(?P<sec>\d+[A-Za-z]?(?:\(\d+\))?)"
    r"\s*(?:of\s+(?:the\s+)?)?"
    r"(?P<act>(?:[A-Z][A-Za-z&]*\s+){1,8}(?:Act|Code|Constitution)(?:,?\s*(?P<yr>\d{4}))?|IPC|CrPC|CPC|BNS|BNSS|BSA)",
)


def extract_citations(text: str) -> list[Citation]:
    found: list[Citation] = []
    taken: list[tuple[int, int]] = []

    def overlaps(a: int, b: int) -> bool:
        return any(not (b <= s or a >= e) for s, e in taken)

    for m in CASE_WITH_CITE.finditer(text):
        year = m.group("y1") or m.group("y2") or m.group("y3")
        rep = m.group("rep1") or m.group("rep2") or m.group("rep3")
        found.append(Citation(
            raw=m.group(0).strip(), kind="case", name=m.group("name").strip(),
            year=year, reporter=rep, court="SC" if m.group("ct") == "SC" or rep in ("SCC", "SCR") else m.group("ct"),
            span=m.span(),
        ))
        taken.append(m.span())

    for m in CASE_NAME_ONLY.finditer(text):
        if overlaps(*m.span()):
            continue
        found.append(Citation(raw=m.group(0).strip(), kind="case", name=m.group("name").strip(), span=m.span()))
        taken.append(m.span())

    for m in STATUTE.finditer(text):
        if overlaps(*m.span()):
            continue
        found.append(Citation(
            raw=m.group(0).strip(), kind="statute", section=m.group("sec"),
            act=m.group("act").strip(), year=m.group("yr"), span=m.span(),
        ))
        taken.append(m.span())

    return sorted(found, key=lambda c: c.span[0])


# ----------------------------------------------------------------------------
# 3. Sources
# ----------------------------------------------------------------------------

class Source(Protocol):
    def search(self, c: Citation) -> list[SourceHit]: ...


class LocalCacheSource:
    """Pre-fetched hits stored in a JSON file. Guarantees demo works offline.

    File format: [{"title": ..., "url": ..., "year": ..., "court": ..., "snippet": ...}, ...]
    Build it by running real Indian Kanoon searches for the cases in your demo draft.
    """
    def __init__(self, path: str = "legal_cache.json"):
        self.entries: list[SourceHit] = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.entries = [SourceHit(**e) for e in json.load(f)]

    def search(self, c: Citation) -> list[SourceHit]:
        if c.kind == "case" and c.name:
            return [h for h in self.entries if _name_sim(c.name, h.title) >= 0.55]
        if c.kind == "statute" and c.act:
            return [h for h in self.entries if _name_sim(c.act, h.title) >= 0.55]
        return []


class IndianKanoonSource:
    """Official API: https://api.indiankanoon.org/documentation/
    Auth header: 'Authorization: Token <token>'. Search is a POST to /search/.
    Paid per call (small), signup gives trial credit. Token via INDIANKANOON_API_TOKEN.
    """
    BASE = "https://api.indiankanoon.org"

    def __init__(self, token: str | None = None, timeout: int = 15):
        self.token = token or os.getenv("INDIANKANOON_API_TOKEN")
        self.timeout = timeout

    def search(self, c: Citation) -> list[SourceHit]:
        if not self.token:
            return []
        query = c.name if c.kind == "case" else f"{c.act} section {c.section}"
        if not query:
            return []
        try:
            r = requests.post(
                f"{self.BASE}/search/",
                params={"formInput": f'"{query}"', "pagenum": 0},
                headers={"Authorization": f"Token {self.token}"},
                timeout=self.timeout,
            )
            r.raise_for_status()
            docs = r.json().get("docs", [])
        except (requests.RequestException, ValueError):
            return []   # network failure => unverified, never a fake pass
        hits = []
        for d in docs[:5]:
            title = re.sub(r"<[^>]+>", "", d.get("title", ""))
            hits.append(SourceHit(
                title=title,
                url=f"https://indiankanoon.org/doc/{d.get('tid')}/",
                year=_year_from(title) or _year_from(d.get("docsource", "")),
                court=d.get("docsource"),
                snippet=re.sub(r"<[^>]+>", "", d.get("headline", ""))[:300],
            ))
        return hits


# ----------------------------------------------------------------------------
# 4. Scoring
# ----------------------------------------------------------------------------

def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(vs?\.?|versus)\b", "v", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(the|of|and|on|its)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _name_sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    # case name often is a prefix/part of a longer title ("... vs State Of Kerala And Anr")
    ratio = SequenceMatcher(None, a, b).ratio()
    contain = 1.0 if a in b or b in a else 0.0
    return max(ratio, 0.9 * contain)


def _year_from(s: str | None) -> str | None:
    m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", s or "")
    return m.group(1) if m else None


def verify_citation(c: Citation, sources: list[Source]) -> Verdict:
    best: tuple[float, SourceHit, list[str]] | None = None

    for src in sources:
        for hit in src.search(c):
            key = c.name if c.kind == "case" else (c.act or "")
            sim = _name_sim(key, hit.title)
            reasons = [f"name similarity {sim:.2f} with '{hit.title}'"]
            score = sim

            if c.kind == "case" and c.year:
                if hit.year and hit.year == c.year:
                    reasons.append(f"year {c.year} matches")
                    score = min(1.0, score + 0.1)
                elif hit.year:
                    reasons.append(f"year mismatch: draft says {c.year}, source says {hit.year}")
                    score -= 0.25
                else:
                    reasons.append("source gave no year to compare")
                    score -= 0.05
            elif c.kind == "case":
                reasons.append("draft gave no year, so only the name could be checked")
                score -= 0.1

            if best is None or score > best[0]:
                best = (score, hit, reasons)
        if best and best[0] >= 0.85:
            break  # good enough, skip slower/paid sources

    if best is None:
        return Verdict(c, "unverified", 0.0,
                       ["no matching authority found in any accessible source; do not rely on it"])

    score, hit, reasons = best
    score = max(0.0, min(1.0, score))
    if score >= 0.85:
        status = "verified"
    elif score >= 0.55:
        status = "partially_verified"
    else:
        status = "unverified"
    return Verdict(c, status, round(score, 2), reasons, hit if status != "unverified" else None)


# ----------------------------------------------------------------------------
# 5. Report + entry point
# ----------------------------------------------------------------------------

def verify_draft(text: str, sources: list[Source] | None = None) -> dict:
    sources = sources or [LocalCacheSource(), IndianKanoonSource()]
    verdicts = [verify_citation(c, sources) for c in extract_citations(text)]
    summary = {"verified": 0, "partially_verified": 0, "unverified": 0}
    for v in verdicts:
        summary[v.status] += 1
    return {"summary": summary, "items": [asdict(v) for v in verdicts]}


# ----------------------------------------------------------------------------
# 6. FastAPI route (mount in your backend)
# ----------------------------------------------------------------------------
try:
    from fastapi import APIRouter
    from pydantic import BaseModel

    router = APIRouter()

    class VerifyRequest(BaseModel):
        text: str

    @router.post("/verify")
    def verify_endpoint(req: VerifyRequest):
        return verify_draft(req.text)
except ImportError:
    router = None
