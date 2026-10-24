"""
Contract Risk Radar: flags risky, missing and unclear clauses in a contract.

Deterministic rules, no AI. Every finding quotes the exact sentence it came from (or says which standard
clause is missing), explains why in plain English, and suggests what to do. A finding is a prompt to look
closely, not a legal opinion: a lawyer must review the contract.

Route:  POST /contract/risk   {text}
"""
from __future__ import annotations

import re

from contract_intel import MAX_CHARS, _clip, _sentences, values_in

AXES = ["Termination", "Payment", "Liability", "Restrictions", "Disputes", "Clarity"]
WEIGHT = {"high": 18, "medium": 8, "low": 3}
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}

# Indian-law pointers are hedged on purpose ("may be", "check") and always link to a search of the law's text,
# so the user reads the source instead of trusting this tool.
LAW = {
    "s27": {"act": "Indian Contract Act, 1872", "section": "27",
            "note": "Section 27 makes agreements in restraint of trade void to that extent. Post-termination non-competes may be unenforceable.",
            "query": "Section 27 Indian Contract Act restraint of trade"},
    "s74": {"act": "Indian Contract Act, 1872", "section": "74",
            "note": "Section 74 lets courts award only reasonable compensation for a breach, even if a larger penalty is written in the contract.",
            "query": "Section 74 Indian Contract Act penalty liquidated damages"},
    "s28": {"act": "Indian Contract Act, 1872", "section": "28",
            "note": "Section 28 makes agreements that restrict legal proceedings void to that extent (arbitration is treated separately).",
            "query": "Section 28 Indian Contract Act restraint of legal proceedings"},
    "arb": {"act": "Arbitration and Conciliation Act, 1996", "section": None,
            "note": "Courts have set aside arbitrator appointments made by one party alone. Check how the arbitrator is chosen.",
            "query": "unilateral appointment of arbitrator"},
}

# (id, title, regex, severity, axis, why, suggestion, law key)
RISKY = [
    ("unilateral_termination", "One side can end the contract at will",
     r"(?:may|can|shall be entitled to|has the right to|reserves the right to)\s+terminate[^.;]{0,100}?"
     r"(?:at any time|at its sole discretion|without (?:any )?(?:cause|reason|notice)|forthwith|immediately)",
     "high", "Termination",
     "This lets one party end the contract suddenly, with no reason or warning.",
     "Ask for a notice period and a reason, and make the right apply to both parties.", None),
    ("sole_discretion", "One side decides alone",
     r"sole (?:and absolute )?discretion|absolute discretion",
     "medium", "Clarity",
     "'Sole discretion' means the other party has no say and may not be able to challenge the decision.",
     "Replace with 'reasonable discretion' or add a clear test for the decision.", None),
    ("unlimited_liability", "Open-ended liability or indemnity",
     r"unlimited liability|liable for (?:all|any and all) (?:losses|damages|claims|costs)"
     r"|indemnif[^.;]{0,100}?(?:all|any and all) (?:losses|claims|damages|liabilit|costs)",
     "high", "Liability",
     "There is no cap, so one mistake could cost far more than the contract is worth.",
     "Ask for a cap (for example, the fees paid) and carve out only the cases you truly accept.", None),
    ("auto_renew", "Renews by itself",
     r"automatically (?:renew|extend)|auto-?renew|deemed to (?:be )?(?:renewed|extended)",
     "medium", "Termination",
     "The contract keeps going unless you cancel in time, and the cancel window is easy to miss.",
     "Diarise the cancel date (see the Deadline Tracker) or ask for opt-in renewal.", None),
    ("non_compete", "Restriction on working or doing business elsewhere",
     r"non-?compete|shall not,?\s*(?:directly or indirectly,?\s*)?(?:compete|engage in|be engaged|carry on)|restrain[^.;]{0,50}(?:trade|business|profession)",
     "high", "Restrictions",
     "It limits where you can work or trade, possibly even after the contract ends.",
     "Have a lawyer check whether it can be enforced, and keep the scope, area and time short.", "s27"),
    ("penalty_clause", "Penalty or fixed damages",
     r"liquidated damages|\bpenalt(?:y|ies)\b|forfeit(?:ed|ure|s)?",
     "medium", "Payment",
     "A fixed amount is payable if something goes wrong, whatever the actual loss.",
     "Check that the amount is a fair estimate of loss and applies to both sides.", "s74"),
    ("waiver", "Gives up rights or claims",
     r"waives? (?:all|any|his|her|its|their)\s+(?:rights?|claims?|remedies)|irrevocably waives?",
     "high", "Disputes",
     "You would lose the right to claim or object, now or later.",
     "Limit the waiver to specific, named matters.", None),
    ("perpetual", "Never ends or cannot be undone",
     r"\birrevocabl[ey]\b|in perpetuity|\bperpetual(?:ly)?\b",
     "medium", "Termination",
     "The commitment has no end date and cannot be withdrawn.",
     "Ask for a fixed term or a way to exit.", None),
    ("ip_assignment", "Hands over all intellectual property",
     r"(?:assign|transfer)s?[^.;]{0,60}(?:all|any) (?:intellectual property|IP\b|rights? (?:in|to) (?:the )?(?:work|deliverables))"
     r"|(?:all|any) (?:intellectual property|IP\b)[^.;]{0,60}(?:assigned|transferred|vest(?:s|ed)? in|belong)",
     "medium", "Restrictions",
     "Everything you create may belong to the other party, possibly including work done outside this job.",
     "Limit it to work done for this contract and keep prior or unrelated work.", None),
    ("no_notice", "Action allowed without warning",
     r"without (?:any )?(?:prior )?(?:written )?notice",
     "medium", "Termination",
     "The other side may act first and tell you later.",
     "Ask for written notice and a short cure period.", None),
    ("lock_in", "Lock-in period",
     r"lock-?in period|minimum (?:commitment|term) of",
     "medium", "Termination",
     "You cannot leave before the lock-in ends without paying.",
     "Check the length and what leaving early costs.", None),
    ("one_sided_arbitrator", "Arbitrator chosen by one side",
     r"(?:sole )?arbitrator[^.;]{0,80}(?:appointed|nominated|chosen) by (?:the )?(?:company|employer|landlord|licensor|lender|bank|vendor)",
     "high", "Disputes",
     "If one party picks the arbitrator, the process may be unfair or open to challenge.",
     "Ask for a mutually agreed arbitrator or appointment by an institution.", "arb"),
    ("exclusive_jurisdiction", "Disputes only in one city",
     r"exclusive jurisdiction",
     "low", "Disputes",
     "Any court case must be filed in that place, which may be costly to attend.",
     "Check that the city is practical for you.", "s28"),
]

UNCLEAR = [
    ("placeholder", "Blank or placeholder left in the text",
     r"_{3,}|\[\s*[●•]?\s*\]|\bTBD\b|\bTBC\b|to be (?:decided|determined|agreed)|\[insert[^\]]*\]",
     "medium", "Clarity",
     "Something that should be filled in is still empty, so the term is not agreed.",
     "Fill in the blank before signing."),
    ("deemed_fit", "Left to someone's judgement",
     r"as (?:may be )?(?:deemed|decided|determined|considered) (?:fit|necessary|appropriate|proper)",
     "medium", "Clarity",
     "The standard is whatever one party decides, which is hard to challenge.",
     "State the actual rule, amount or test."),
    ("external_policy", "Refers to a document you may not have seen",
     r"as per (?:the )?(?:company|employer|landlord|management)(?:'s)? (?:policy|policies|rules|guidelines)|company policy|as amended from time to time by",
     "medium", "Clarity",
     "The terms sit in another document that can be changed, and you may not have it.",
     "Ask for a copy and for changes to need your written consent."),
    ("best_efforts", "'Best efforts' is vague",
     r"\bbest efforts\b|\breasonable efforts\b",
     "low", "Clarity",
     "It is not clear how much effort is enough.",
     "Say what must actually be done, and by when."),
    ("from_time_to_time", "'From time to time' is open-ended",
     r"\bfrom time to time\b",
     "low", "Clarity",
     "It lets terms or duties change without a fixed schedule.",
     "State how often, or require notice of any change."),
    ("and_or", "'And/or' can be read two ways",
     r"\band/or\b",
     "low", "Clarity",
     "It is unclear whether both items are needed or only one.",
     "Choose 'and' or 'or'."),
    ("etc", "'Etc.' leaves the list open",
     r"\betc\.?(?=\s|$|[,;)])",
     "low", "Clarity",
     "The list is not complete, so you cannot tell what else is included.",
     "List everything that is meant."),
]

# standard clauses: (id, name, regex, severity, axis, why)
CHECKLIST = [
    ("termination", "Termination", r"terminat", "high", "Termination", "There is no clear way to end the contract."),
    ("governing_law", "Governing law", r"governed by|governing law|laws of", "high", "Disputes", "It is not stated which country's or state's law applies."),
    ("payment", "Payment terms", r"\bpay|salary|fees?\b|rent\b|consideration|remuneration", "high", "Payment", "The amount, timing or method of payment is not described."),
    ("dispute", "Dispute resolution", r"arbitrat|jurisdiction|courts? (?:at|of|in)|mediation", "medium", "Disputes", "There is no stated place or method to settle disagreements."),
    ("notice", "Notice", r"\bnotice\b", "medium", "Termination", "There is no rule on how and when notices must be given."),
    ("liability", "Liability or indemnity", r"liabilit|indemn", "medium", "Liability", "Who bears the loss if something goes wrong is not addressed."),
    ("force_majeure", "Force majeure", r"force majeure|act of god|beyond (?:the )?reasonable control", "low", "Liability", "Events outside anyone's control (floods, strikes) are not covered."),
    ("confidentiality", "Confidentiality", r"confidential", "low", "Restrictions", "Nothing says information must be kept private."),
    ("entire_agreement", "Entire agreement", r"entire agreement|supersede", "low", "Clarity", "Earlier promises and emails may still be argued to apply."),
    ("severability", "Severability", r"severab|invalid or unenforceable", "low", "Disputes", "If one clause fails, it is not clear the rest still stands."),
    ("assignment", "Assignment", r"\bassign", "low", "Restrictions", "It is not stated whether either side may hand the contract to someone else."),
    ("amendment", "Changes in writing", r"amend|modif[iy]|variation", "low", "Clarity", "There is no rule on how the contract can be changed."),
]
MIN_CHARS_FOR_MISSING = 400      # a short snippet is not a whole contract; do not list "missing" clauses for it


def _finding(kind, rid, title, sev, axis, why, suggestion, quote=None, law=None, pos=0):
    f = {"id": rid, "kind": kind, "severity": sev, "axis": axis, "title": title, "why": why,
         "suggestion": suggestion, "quote": quote, "law": None, "pos": pos}
    if law:
        l = LAW[law]
        f["law"] = {"act": l["act"], "section": l["section"], "note": l["note"], "query": l["query"],
                    "url": "https://indiankanoon.org/search/?formInput=" + l["query"].replace(" ", "+")}
    return f


def _high_rate(sentence: str):
    """Interest / penalty percentages: 18% and above is flagged (24%+ high)."""
    if not re.search(r"interest|penalt|late fee|liquidated|per (?:month|annum|year)", sentence, re.I):
        return None
    pcts = [v for v in values_in(sentence, ("percent",))]
    if not pcts:
        return None
    top = max(p["key"][1] for p in pcts)
    per_month = bool(re.search(r"per month|monthly|p\.m\.", sentence, re.I))
    annual = top * 12 if per_month else top
    if annual >= 24:
        return "high", pcts, top, per_month
    if annual >= 18:
        return "medium", pcts, top, per_month
    return None


def risk_radar(text: str) -> dict:
    text = _clip(text)
    sents = _sentences(text)
    findings: list[dict] = []
    seen: set[tuple] = set()

    def add(f):
        key = (f["id"], f["quote"])
        if key not in seen:
            seen.add(key)
            findings.append(f)

    per_rule: dict[str, int] = {}
    for pos, s in enumerate(sents):
        for rid, title, pat, sev, axis, why, sug, law in RISKY:
            if per_rule.get(rid, 0) < 3 and re.search(pat, s, re.I):
                per_rule[rid] = per_rule.get(rid, 0) + 1
                add(_finding("risky", rid, title, sev, axis, why, sug, s, law, pos))
        for rid, title, pat, sev, axis, why, sug in UNCLEAR:
            if per_rule.get(rid, 0) < 3 and re.search(pat, s, re.I):
                per_rule[rid] = per_rule.get(rid, 0) + 1
                add(_finding("unclear", rid, title, sev, axis, why, sug, s, None, pos))
        hr = _high_rate(s)
        if hr and per_rule.get("high_rate", 0) < 3:
            per_rule["high_rate"] = per_rule.get("high_rate", 0) + 1
            sev, pcts, top, per_month = hr
            unit = "a month" if per_month else "a year"
            add(_finding("risky", "high_rate", f"High rate: {pcts[0]['text']} {unit}".replace("  ", " "), sev, "Payment",
                         "This rate is high enough that courts or regulators may question it, and it adds up quickly.",
                         "Ask for a lower rate or a cap on the total.", s, "s74", pos))

    if len(text) >= MIN_CHARS_FOR_MISSING:
        low = text.lower()
        for rid, name, pat, sev, axis, why in CHECKLIST:
            if not re.search(pat, low):
                add(_finding("missing", "missing_" + rid, f"No {name.lower()} clause found", sev, axis, why,
                             f"Consider adding a {name.lower()} clause. If it exists under another name, ignore this.", None, None, 10 ** 6))

    findings.sort(key=lambda f: (SEV_ORDER[f["severity"]], f["pos"]))
    for n, f in enumerate(findings, 1):
        f["n"] = n
        f.pop("pos", None)

    score = min(100, sum(WEIGHT[f["severity"]] for f in findings))
    axes = {a: 0 for a in AXES}
    for f in findings:
        axes[f["axis"]] = min(100, axes[f["axis"]] + WEIGHT[f["severity"]] * 2)
    counts = {k: sum(1 for f in findings if f["severity"] == k) for k in ("high", "medium", "low")}
    counts.update({k: sum(1 for f in findings if f["kind"] == k) for k in ("risky", "missing", "unclear")})
    level = "High" if score >= 55 else "Medium" if score >= 25 else "Low"
    return {"score": score, "level": level, "axes": axes, "counts": counts, "findings": findings,
            "checked_missing": len(text) >= MIN_CHARS_FOR_MISSING,
            "disclaimer": "These are prompts to look closely, not legal opinions. A lawyer must review the contract."}


try:
    from fastapi import APIRouter
    from pydantic import BaseModel, Field

    router = APIRouter()

    class RiskReq(BaseModel):
        text: str = Field(..., max_length=MAX_CHARS)

    @router.post("/contract/risk")
    def risk_endpoint(req: RiskReq):
        return risk_radar(req.text)
except ImportError:
    router = None
