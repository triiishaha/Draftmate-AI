"""Module 3 helpers: risk radar, deadline/obligation extraction, legal change impact map.
Pure Python, no framework dependency. Rule-based, so results are explainable and
should be treated as flags for legal review, not legal advice."""
import re
from datetime import date, datetime

# ---------- clause splitting ----------
def split_clauses(text: str):
    parts = re.split(r"\n\s*\n|\n(?=\s*(?:\d+(?:\.\d+)*[.)]|Clause\s+\d+|Section\s+\d+))", text or "")
    return [p.strip() for p in parts if p and len(p.strip()) > 20]

# ---------- risk radar ----------
RISK_RULES = [
    ("unilateral_termination", "One-sided termination", "high",
     r"terminat\w+.{0,80}(at any time|sole discretion|without (cause|notice|reason))",
     "One party can end the contract without cause or notice.",
     "Ask for a mutual notice period and defined grounds for termination."),
    ("sole_discretion", "Unilateral changes / sole discretion", "high",
     r"sole discretion|(modify|amend|change|alter).{0,60}without (prior )?(notice|consent)",
     "One party can change terms or decide alone.",
     "Require written consent from both parties for changes."),
    ("non_compete", "Non-compete / restraint", "high",
     r"non-?compete|shall not (work|engage|be employed).{0,80}(competitor|similar business)",
     "Restrains future work. Post-contract restraints can be hard to enforce in India (Indian Contract Act, s.27).",
     "Limit scope, duration and geography, or get legal review."),
    ("indemnity", "Broad indemnity / unlimited liability", "high",
     r"indemnif\w+|hold harmless|unlimited liability",
     "May expose you to uncapped losses.",
     "Cap liability and limit indemnity to direct losses."),
    ("lock_in", "Bond / lock-in / recovery of costs", "medium",
     r"\bbond\b|lock-?in period|recover.{0,50}(training|joining|relocation)",
     "Penalty or repayment if you leave early.",
     "Check amount is reasonable and reduces over time."),
    ("auto_renewal", "Automatic renewal", "medium",
     r"auto(matic(ally)?)?[- ]?renew|renew\w* automatically",
     "Contract may renew without you acting.",
     "Add a reminder before the opt-out date."),
    ("penalty", "Penalty / forfeiture", "medium",
     r"liquidated damages|penalt(y|ies)|forfeit",
     "Fixed charges may be disproportionate.",
     "Confirm amounts are a genuine pre-estimate of loss."),
    ("withholding", "Deductions / set-off", "medium",
     r"(withhold|deduct|set[- ]?off).{0,60}(salary|payment|amount|fees)",
     "Payments can be reduced unilaterally.",
     "List the specific cases where deductions are allowed."),
    ("ip_assignment", "Broad IP assignment", "medium",
     r"all (inventions|work product|intellectual property).{0,100}(whether or not|at any time|during and after)",
     "Claims work outside your job or after you leave.",
     "Limit to work done for the other party during the term."),
    ("perpetual_confidentiality", "Perpetual confidentiality", "medium",
     r"confidential\w*.{0,120}(perpetuity|indefinite|forever)",
     "No end date on confidentiality duty.",
     "Set a fixed period (e.g., 2-5 years) except for trade secrets."),
    ("vague", "Vague wording", "low",
     r"reasonable efforts|as (may be )?deemed (appropriate|necessary)|from time to time|\betc\.",
     "Unclear terms are open to dispute.",
     "Replace with measurable terms."),
    ("jurisdiction", "Exclusive jurisdiction / arbitration", "low",
     r"exclusive jurisdiction|arbitrat\w+",
     "Disputes may have to be handled in a place or forum that is costly for you.",
     "Check the seat of arbitration and who appoints the arbitrator."),
]

# (id, title, severity, regex that shows the clause IS present, why, suggestion)
EXPECTED_CLAUSES = [
    ("termination", "Termination / notice", "high", r"terminat|notice period", "No exit terms found.", "Add notice period and grounds."),
    ("governing_law", "Governing law", "medium", r"governing law|governed by the laws", "Unclear which law applies.", "Name the governing law."),
    ("dispute", "Dispute resolution", "medium", r"dispute|arbitrat|jurisdiction|court", "No process for disputes.", "Add arbitration or court jurisdiction."),
    ("confidentiality", "Confidentiality", "medium", r"confidential", "No protection for sensitive info.", "Add a confidentiality clause."),
    ("liability", "Limitation of liability", "medium", r"limitation of liability|liability (shall|will) (not|be limited)|cap on liability", "Liability is uncapped.", "Add a liability cap."),
    ("payment", "Payment / compensation terms", "high", r"salary|compensation|payment|fees|remuneration|ctc", "No payment terms found.", "State amount, schedule and taxes."),
    ("force_majeure", "Force majeure", "low", r"force majeure", "No relief for events beyond control.", "Add a force majeure clause."),
    ("entire_agreement", "Entire agreement / amendment", "low", r"entire agreement|amendments? (must|shall)", "Side promises may be disputed.", "Add an entire-agreement clause."),
]

WEIGHT = {"high": 20, "medium": 10, "low": 4}

def analyze_risks(text: str):
    clauses = split_clauses(text)
    flags = []
    for cid, title, sev, pat, why, fix in RISK_RULES:
        for i, c in enumerate(clauses):
            m = re.search(pat, c, re.I | re.S)
            if m:
                flags.append({"id": cid, "title": title, "severity": sev, "kind": "risky" if sev != "low" else "unclear",
                              "clause_index": i, "excerpt": c[:280], "match": m.group(0)[:120], "why": why, "suggestion": fix})
    missing = [{"id": cid, "title": t, "severity": s, "kind": "missing", "why": w, "suggestion": f}
               for cid, t, s, pat, w, f in EXPECTED_CLAUSES if not re.search(pat, text or "", re.I)]
    score = min(100, sum(WEIGHT[f["severity"]] for f in flags) + sum(WEIGHT[m["severity"]] for m in missing))
    level = "High" if score >= 60 else "Medium" if score >= 30 else "Low"
    order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: order[f["severity"]])
    missing.sort(key=lambda f: order[f["severity"]])
    return {"score": score, "level": level, "clause_count": len(clauses), "flags": flags, "missing": missing}

# ---------- deadlines & obligations ----------
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}
DATE_PATTERNS = [
    (r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december),?\s+(\d{4})\b",
     lambda m: date(int(m[3]), MONTHS[m[2].lower()], int(m[1]))),
    (r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
     lambda m: date(int(m[3]), MONTHS[m[1].lower()], int(m[2]))),
    (r"\b(\d{4})-(\d{2})-(\d{2})\b", lambda m: date(int(m[1]), int(m[2]), int(m[3]))),
    (r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", lambda m: date(int(m[3]), int(m[2]), int(m[1]))),  # day-first (India)
]
PERIOD_RE = re.compile(r"\b(?:within|after|before|for|of|upon|a period of)?\s*(\d{1,3})\s*(?:\(\w+\)\s*)?(business days?|working days?|days?|weeks?|months?|years?)['’]?\s*(?:prior |written )?(notice|of notice)?", re.I)
OBLIGATION_RE = re.compile(r"\b(shall|must|agrees to|is required to|undertakes to|will be responsible for)\b", re.I)
PARTY_RE = re.compile(r"\b(the )?(employee|employer|company|client|contractor|vendor|supplier|consultant|licensee|licensor|tenant|landlord)\b", re.I)

def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.;])\s+|\n+", text or "") if len(s.strip()) > 15]

def extract_deadlines(text: str, today: date | None = None):
    today = today or date.today()
    items, seen = [], set()
    for s in _sentences(text):
        for pat, build in DATE_PATTERNS:
            for m in re.finditer(pat, s, re.I):
                try:
                    d = build(m)
                except ValueError:
                    continue
                key = ("date", d, s[:60])
                if key in seen:
                    continue
                seen.add(key)
                items.append({"type": "date", "title": s[:140], "date": d.isoformat(), "days_left": (d - today).days, "context": s})
        pm = PERIOD_RE.search(s)
        if pm and re.search(r"notice|payment|pay|cure|renew|terminat|probation|deliver|complete|within|lock", s, re.I):
            items.append({"type": "period", "title": s[:140], "period": f"{pm.group(1)} {pm.group(2).lower()}", "date": None, "days_left": None, "context": s})
        if OBLIGATION_RE.search(s):
            party = PARTY_RE.search(s)
            items.append({"type": "obligation", "title": s[:140], "party": party.group(2).title() if party else "Unspecified", "date": None, "days_left": None, "context": s})
    dated = sorted([i for i in items if i["date"]], key=lambda i: i["date"])
    rest = [i for i in items if not i["date"]]
    for n, it in enumerate(dated + rest, 1):
        it["id"] = n
    return dated + rest

# ---------- legal change impact map ----------
# Starter map. Extend or replace with entries from legal_cache.json. Always verify on the official source.
LAW_TOPICS = {
    "labour_codes": {"label": "Labour codes / wages", "law": "Code on Wages, 2019 and other Labour Codes",
                     "keywords": r"salary|wage|overtime|bonus|gratuity|working hours|leave|provident fund|notice period|retrench",
                     "sources": ["https://labour.gov.in/", "https://www.indiacode.nic.in/"]},
    "data_protection": {"label": "Data protection", "law": "Digital Personal Data Protection Act, 2023",
                        "keywords": r"personal data|data protection|privacy|consent|data processing|confidential",
                        "sources": ["https://www.meity.gov.in/", "https://www.indiacode.nic.in/"]},
    "contract_act": {"label": "Contract law", "law": "Indian Contract Act, 1872",
                     "keywords": r"non-?compete|restraint|penalt|liquidated damages|indemnif|void|consideration",
                     "sources": ["https://www.indiacode.nic.in/"]},
    "arbitration": {"label": "Arbitration", "law": "Arbitration and Conciliation Act, 1996",
                    "keywords": r"arbitrat|dispute|jurisdiction|seat of",
                    "sources": ["https://www.indiacode.nic.in/"]},
    "ip": {"label": "Intellectual property", "law": "Copyright Act, 1957 / Patents Act, 1970",
           "keywords": r"intellectual property|copyright|invention|patent|work product|licen[cs]e",
           "sources": ["https://www.indiacode.nic.in/"]},
    "gst_tax": {"label": "Tax / GST", "law": "CGST Act, 2017 / Income-tax Act",
                "keywords": r"\bgst\b|\btax\b|tds|invoice|withholding",
                "sources": ["https://www.indiacode.nic.in/", "https://www.incometax.gov.in/"]},
}

def list_topics():
    return [{"id": k, "label": v["label"], "law": v["law"]} for k, v in LAW_TOPICS.items()]

def impact_map(text: str, topic: str):
    t = LAW_TOPICS.get(topic)
    if not t:
        return {"error": f"Unknown topic '{topic}'", "topics": list_topics()}
    hits = []
    for i, c in enumerate(split_clauses(text)):
        m = re.search(t["keywords"], c, re.I)
        if m:
            hits.append({"clause_index": i, "matched": m.group(0), "excerpt": c[:300],
                         "action": f"Review against {t['law']} if the law or its rules have changed."})
    return {"topic": topic, "label": t["label"], "law": t["law"], "sources": t["sources"], "affected": hits,
            "note": "Keyword-based screening. Confirm the current text of the law on the official source before acting."}
