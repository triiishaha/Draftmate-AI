"""
Legal Change Impact Map: when a law changes, which clauses of THIS contract may need review?

How it stays honest:
  * The user tells us which law changed (and optionally what changed). We never claim a law has changed.
  * A law is linked to the kinds of clauses it typically governs (a small, readable table below).
  * Clauses are found in the contract by keyword and quoted word for word.
  * Supporting sources are real results from Indian Kanoon (the law's own text), with links.
  * If we cannot map the law, we say so instead of guessing.

Routes:
    GET  /contract/laws                 -> the laws we can map
    POST /contract/impact               {text, law, change?}
"""
from __future__ import annotations

from typing import Optional
import re
from difflib import SequenceMatcher

from contract_intel import MAX_CHARS, _clip, _sentences

# topic id -> (label, regex that finds clauses on this topic)
TOPICS = {
    "restraint": ("Non-compete and restraint of trade", r"non-?compete|restrain|shall not,?\s*(?:directly or indirectly,?\s*)?(?:compete|engage)|exclusiv"),
    "damages": ("Damages, penalty and liquidated damages", r"damages|penalt|liquidated|compensat|forfeit|indemn"),
    "arbitration": ("Arbitration and dispute resolution", r"arbitrat|dispute|mediation|conciliat"),
    "jurisdiction": ("Courts and jurisdiction", r"jurisdiction|courts? (?:at|of|in)|governed by|governing law"),
    "wages": ("Salary, wages and bonus", r"salary|wages?\b|remuneration|bonus|overtime|\bCTC\b|allowance|increment"),
    "termination": ("Termination, notice and resignation", r"terminat|notice|retrench|resign|severance|dismiss|lay-?off"),
    "benefits": ("Gratuity, provident fund and social security", r"gratuity|provident fund|\bPF\b|\bESI\b|social security|insurance|pension"),
    "leave": ("Leave and working hours", r"\bleave\b|maternity|paternity|working hours|shift|holiday"),
    "data": ("Personal data and privacy", r"personal data|data protection|privacy|consent|processing of (?:personal )?data|data (?:principal|fiduciary)"),
    "electronic": ("Electronic records and signatures", r"electronic|e-?sign|digital signature|by e-?mail|online"),
    "tax": ("Tax, GST and invoicing", r"\bGST\b|goods and services tax|\btax(?:es)?\b|\bTDS\b|invoice|withholding"),
    "cheque": ("Cheques and payment instruments", r"cheque|dishonou?r|negotiable instrument|post-?dated"),
    "rent": ("Rent, lease and possession of premises", r"\brent\b|lease|tenant|landlord|premises|security deposit|evict|licen[cs]e fee"),
    "realestate": ("Possession, delay and builder obligations", r"possession|builder|promoter|allottee|delay in (?:handing|delivery)|carpet area"),
    "consumer": ("Warranty, refund and consumer rights", r"warrant|refund|defect|consumer|guarantee|return policy"),
    "stamp": ("Stamp duty and registration", r"stamp duty|stamped|registration|registered"),
    "harassment": ("Workplace conduct and harassment policy", r"harass|internal complaints|code of conduct|misconduct"),
    "governance": ("Directors, shareholders and company governance", r"director|shareholder|board of|share capital|\bAGM\b"),
    "ip": ("Intellectual property", r"intellectual property|copyright|patent|trade ?mark|\bIP\b|licen[cs]e of"),
}

# law id -> name, aliases, search query for sources, {topic: why this law matters for it}
LAWS = {
    "contract_act": {
        "name": "Indian Contract Act, 1872", "aliases": ["contract act", "ica", "indian contract act"],
        "query": "Indian Contract Act 1872",
        "topics": {
            "restraint": "Section 27 deals with agreements in restraint of trade.",
            "damages": "Sections 73 and 74 deal with damages and with penalty or liquidated damages.",
            "jurisdiction": "Section 28 deals with agreements that restrict legal proceedings.",
        }},
    "arbitration": {
        "name": "Arbitration and Conciliation Act, 1996", "aliases": ["arbitration act", "arbitration and conciliation", "a&c act"],
        "query": "Arbitration and Conciliation Act 1996",
        "topics": {
            "arbitration": "The Act sets the rules for the arbitration agreement, the arbitrator and the seat of arbitration.",
            "jurisdiction": "The seat of arbitration decides which courts supervise the process.",
        }},
    "wages_code": {
        "name": "Code on Wages, 2019", "aliases": ["code on wages", "wages code", "payment of wages", "minimum wages"],
        "query": "Code on Wages 2019",
        "topics": {"wages": "Rules on wages, bonus, overtime and minimum pay."}},
    "ir_code": {
        "name": "Industrial Relations Code, 2020", "aliases": ["industrial relations code", "ir code", "industrial disputes"],
        "query": "Industrial Relations Code 2020",
        "topics": {"termination": "Rules on notice, retrenchment, lay-off and closure for workers.",
                   "arbitration": "Rules on how workplace disputes are raised and settled."}},
    "ss_code": {
        "name": "Code on Social Security, 2020", "aliases": ["code on social security", "social security code", "epf", "esi act"],
        "query": "Code on Social Security 2020",
        "topics": {"benefits": "Rules on provident fund, ESI, gratuity and maternity benefit.",
                   "leave": "Rules on maternity benefit."}},
    "osh_code": {
        "name": "Occupational Safety, Health and Working Conditions Code, 2020", "aliases": ["osh code", "working conditions code", "factories act"],
        "query": "Occupational Safety Health and Working Conditions Code 2020",
        "topics": {"leave": "Rules on working hours, leave and shifts."}},
    "gratuity": {
        "name": "Payment of Gratuity Act, 1972", "aliases": ["gratuity act", "payment of gratuity"],
        "query": "Payment of Gratuity Act 1972",
        "topics": {"benefits": "Rules on who gets gratuity and how it is calculated."}},
    "maternity": {
        "name": "Maternity Benefit Act, 1961", "aliases": ["maternity benefit act", "maternity act"],
        "query": "Maternity Benefit Act 1961",
        "topics": {"leave": "Rules on paid maternity leave and related benefits."}},
    "dpdp": {
        "name": "Digital Personal Data Protection Act, 2023", "aliases": ["dpdp", "dpdp act", "data protection act", "data protection"],
        "query": "Digital Personal Data Protection Act 2023",
        "topics": {"data": "Rules on consent, purpose and handling of personal data."}},
    "it_act": {
        "name": "Information Technology Act, 2000", "aliases": ["it act", "information technology act"],
        "query": "Information Technology Act 2000",
        "topics": {"electronic": "Recognises electronic records and electronic signatures.",
                   "data": "Rules on data security and electronic records."}},
    "ni_act": {
        "name": "Negotiable Instruments Act, 1881", "aliases": ["ni act", "negotiable instruments act", "section 138", "cheque bounce"],
        "query": "Negotiable Instruments Act 1881 Section 138",
        "topics": {"cheque": "Section 138 deals with dishonour of cheques."}},
    "cgst": {
        "name": "Central Goods and Services Tax Act, 2017", "aliases": ["gst", "cgst", "goods and services tax", "gst act"],
        "query": "Central Goods and Services Tax Act 2017",
        "topics": {"tax": "Rules on GST, tax invoices and input tax credit."}},
    "tpa": {
        "name": "Transfer of Property Act, 1882", "aliases": ["transfer of property act", "tpa", "property act"],
        "query": "Transfer of Property Act 1882",
        "topics": {"rent": "Sets rules for leases, including notice and eviction.",
                   "stamp": "Transfers of property usually need proper documentation."}},
    "rera": {
        "name": "Real Estate (Regulation and Development) Act, 2016", "aliases": ["rera", "real estate act"],
        "query": "Real Estate Regulation and Development Act 2016",
        "topics": {"realestate": "Rules on possession dates, delay and promoter obligations.",
                   "damages": "Rules on interest and compensation for delay."}},
    "consumer": {
        "name": "Consumer Protection Act, 2019", "aliases": ["consumer protection act", "cpa"],
        "query": "Consumer Protection Act 2019",
        "topics": {"consumer": "Rules on defects, refunds and unfair contract terms.",
                   "damages": "Compensation for loss caused by defects or poor service."}},
    "stamp": {
        "name": "Indian Stamp Act, 1899", "aliases": ["stamp act", "indian stamp act", "stamp duty"],
        "query": "Indian Stamp Act 1899",
        "topics": {"stamp": "Rules on stamp duty payable on documents."}},
    "posh": {
        "name": "Sexual Harassment of Women at Workplace Act, 2013", "aliases": ["posh", "posh act", "sexual harassment act"],
        "query": "Sexual Harassment of Women at Workplace Act 2013",
        "topics": {"harassment": "Requires an internal complaints process at workplaces."}},
    "companies": {
        "name": "Companies Act, 2013", "aliases": ["companies act", "company law"],
        "query": "Companies Act 2013",
        "topics": {"governance": "Rules on directors, shareholders and company decisions."}},
    "copyright": {
        "name": "Copyright Act, 1957", "aliases": ["copyright act", "copyright"],
        "query": "Copyright Act 1957",
        "topics": {"ip": "Rules on who owns and can license creative work."}},
}


def list_laws() -> list[dict]:
    return [{"id": k, "name": v["name"], "topics": [TOPICS[t][0] for t in v["topics"]]} for k, v in LAWS.items()]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def match_law(text: str) -> str | None:
    """Law id for a free-text name ('DPDP', 'code on wages 2019'), or None. No guessing on weak matches."""
    q = _norm(text or "")
    if not q:
        return None
    if q in LAWS:
        return q
    best, bid = 0.0, None
    for lid, law in LAWS.items():
        for cand in [law["name"]] + law["aliases"]:
            c = _norm(cand)
            if q == c:
                score = 1.0
            elif f" {c} " in f" {q} " and len(c) >= 3:          # 'the dpdp act 2023' contains the alias 'dpdp act'
                score = 0.95
            elif q in c and len(q) / len(c) >= 0.6:              # 'contract' is most of 'contract act'; 'code' is not
                score = 0.9
            else:
                score = SequenceMatcher(None, q, c).ratio()
            if score > best:
                best, bid = score, lid
    return bid if best >= 0.75 else None


def topics_from_change(change: str) -> list[str]:
    """When the law is not in our table, fall back to the topics the user's own description mentions."""
    return [t for t, (_, pat) in TOPICS.items() if re.search(pat, change or "", re.I)][:4]


def _clauses_for(topic: str, sentences: list[str], limit: int = 5) -> list[str]:
    rx = re.compile(TOPICS[topic][1], re.I)
    return [s for s in sentences if rx.search(s)][:limit]


def _sources(query: str, researcher) -> list[dict]:
    if researcher is None:
        return []
    try:
        r = researcher(query)
    except Exception:
        return []
    return [{"title": x["title"], "url": x["url"], "court": x.get("court"), "snippet": x.get("snippet", "")}
            for x in r.get("results", [])[:3]]


def impact_map(text: str, law: str, change: str = "", researcher=None) -> dict:
    sents = _sentences(_clip(text))
    law_id = match_law(law)
    note = None
    if law_id:
        entry = LAWS[law_id]
        topic_why = dict(entry["topics"])
        name, query = entry["name"], entry["query"]
        for t in topics_from_change(change):          # the user's description can add topics, never remove them
            topic_why.setdefault(t, "You mentioned this in your description of the change.")
    else:
        topic_why = {t: "You mentioned this in your description of the change." for t in topics_from_change(change)}
        name, query = (law or "").strip()[:120] or "The law you entered", (law or change or "").strip()[:150]
        note = ("We do not have this law in our table, so the clauses below come only from the words in your description. "
                if topic_why else
                "We could not map this law to clause types. Pick one from the list, or describe what changed (for example, 'notice period' or 'data consent').")

    impacted, absent = [], []
    for t, why in topic_why.items():
        quotes = _clauses_for(t, sents)
        row = {"topic": t, "label": TOPICS[t][0], "why": why}
        if quotes:
            impacted.append({**row, "clauses": quotes})
        else:
            absent.append({**row})
    return {
        "law": name, "law_id": law_id, "change": (change or "").strip()[:500] or None,
        "impacted": impacted, "no_clause_found": absent,
        "sources": _sources(query, researcher),
        "search_url": "https://indiankanoon.org/search/?formInput=" + re.sub(r"\s+", "+", query.strip()) if query.strip() else None,
        "note": note,
        "disclaimer": ("We do not say whether or how this law has changed. You tell us the law, and we show which clauses of your "
                       "contract deal with what it covers. Sources are the law's own text from Indian Kanoon. A lawyer must review."),
    }


try:
    from fastapi import APIRouter
    from pydantic import BaseModel, Field

    router = APIRouter()

    class ImpactReq(BaseModel):
        text: str = Field(..., max_length=MAX_CHARS)
        law: str = Field(..., max_length=200)
        change: Optional[str] = Field("", max_length=1000)

    @router.get("/contract/laws")
    def laws_endpoint():
        return {"laws": list_laws()}

    @router.post("/contract/impact")
    def impact_endpoint(req: ImpactReq):
        from research import research

        def researcher(q: str) -> dict:
            return research(q, "laws")
        return impact_map(req.text, req.law, req.change or "", researcher)
except ImportError:
    router = None
