"""Dynamic legal skills framework. Each skill is a JSON file under skills_data/<category>/.
Add a file and call reload() (or POST /api/skills/custom) and it appears in the library."""
import json, os, re

DATA = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills_data"))

BASE_RULES = (
    "You are DraftMate AI, a legal drafting assistant that supports a human lawyer or law student. "
    "Never invent case names, citations, statutes, section numbers or quotations. If you are not sure an authority "
    "exists or says what you claim, say so and mark it [UNVERIFIED]. Keep the substantive meaning of supplied text unless "
    "asked to change it. State the jurisdiction you assume. Mark missing facts as [PLACEHOLDER] instead of guessing. "
    "Your output is a draft for professional review, not legal advice."
)
CATEGORY_RULES = {
    "Legal Research": "For every authority give court, year and the proposition it supports, and label it Verified, Partially Verified or Unverified.",
    "Case & Judgment Tools": "Use only the supplied judgment text. Give paragraph references where available.",
    "Drafting & Writing": "Use consistent defined terms, numbered clauses and a professional tone.",
    "Document Review & Analysis": "Quote the clause or section you refer to.",
    "Compliance & Advisory": "Name the statute or regulation applied and flag anything to confirm on the official source.",
    "Student Learning & Exam Prep": "Teach, do not just answer. Mark case names as [VERIFY] unless supplied.",
}
OUTPUT_HINT = {
    "draft": "Return the document text in Markdown.", "analysis": "Return a structured analysis with short headings.",
    "summary": "Return a concise summary with section references.", "table": "Return the result as a Markdown table, then a short note.",
    "notes": "Return structured notes with action items.", "study": "Return an interactive, study-friendly response.",
}

_cache = None

def _stem(w):
    w, changed = w.lower(), True
    while changed:  # strip repeatedly so 'citations' and 'citation' reach the same stem
        changed = False
        for suf in ("ation", "ing", "ion", "ed", "es", "s", "e"):
            if len(w) > len(suf) + 3 and w.endswith(suf):
                w, changed = w[: -len(suf)], True
                break
    return w

def _toks(s):
    return {_stem(t) for t in re.findall(r"[a-zA-Z]{3,}", s or "")}

def load():
    global _cache
    if _cache is None:
        _cache = {}
        for root, _, files in os.walk(DATA):
            for f in files:
                if f.endswith(".json"):
                    try:
                        s = json.load(open(os.path.join(root, f), encoding="utf-8"))
                        if s.get("id") and s.get("name") and s.get("instruction"):
                            _cache[s["id"]] = s
                    except (OSError, ValueError):
                        continue  # skip a bad skill file instead of breaking the library
    return _cache

def reload():
    global _cache
    _cache = None
    return load()

def get(skill_id):
    return load().get(skill_id)

def public(s):
    return {k: s[k] for k in ("id", "name", "category", "audience", "description", "needs_document", "output")}

def categories():
    out = {}
    for s in load().values():
        out.setdefault(s["category"], []).append(s["name"])
    return out

def list_skills(q=None, category=None, audience=None):
    items = list(load().values())
    if category: items = [s for s in items if s["category"] == category]
    if audience: items = [s for s in items if audience in s["audience"]]
    if q:
        qt = _toks(q)
        scored = [(len(qt & _toks(s["name"] + " " + s["description"])), s) for s in items]
        items = [s for sc, s in sorted(scored, key=lambda x: -x[0]) if sc > 0]
    return [public(s) for s in items]

def route(query):
    """Pick a skill from natural language or an @mention (e.g. '@redlining', 'redline this NDA')."""
    skills = load()
    m = re.search(r"@([a-z0-9\-]+)", query or "", re.I)
    if m:
        key = m.group(1).lower()
        hit = skills.get(key) or next((s for sid, s in skills.items() if sid.startswith(key)), None)
        if hit:
            return {"skill": public(hit), "confidence": 1.0, "alternatives": [], "via": "mention"}
    qt, ql = _toks(query), (query or "").lower()
    scored = []
    for s in skills.values():
        name_t = _toks(s["name"])
        score = 3 * len(qt & name_t) + len(qt & set(map(_stem, s["keywords"]))) + 0.5 * len(qt & _toks(s["description"]))
        if s["name"].lower() in ql: score += 6
        if name_t and name_t <= qt: score += 3
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    top = scored[0] if scored else (0, None)
    if top[0] < 3:
        return {"skill": None, "confidence": 0.0, "alternatives": [public(s) for sc, s in scored[:3] if sc > 0], "via": "none"}
    return {"skill": public(top[1]), "confidence": round(min(1.0, top[0] / 9), 2),
            "alternatives": [public(s) for sc, s in scored[1:4] if sc >= 2], "via": "text"}

def system_prompt(skill):
    return "\n\n".join([BASE_RULES, CATEGORY_RULES.get(skill["category"], ""),
                        f"ACTIVE SKILL: {skill['name']}\n{skill['instruction']}", OUTPUT_HINT.get(skill["output"], "")]).strip()

def save_custom(name, description, instruction, needs_document=False):
    sid = "custom-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    d = os.path.join(DATA, "custom"); os.makedirs(d, exist_ok=True)
    s = {"id": sid, "name": name.strip(), "category": "General Utilities", "audience": ["lawyer", "student"],
         "description": description.strip(), "instruction": instruction.strip(), "needs_document": needs_document,
         "output": "draft", "keywords": sorted(_toks(name + " " + description))}
    json.dump(s, open(os.path.join(d, sid + ".json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    reload()
    return public(s)
