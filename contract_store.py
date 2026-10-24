"""Templates and version history, stored in a local JSON file (swap for a DB later)."""
import hashlib, json, os, threading, uuid
from datetime import datetime, timezone

PATH = os.environ.get("CONTRACT_STORE", os.path.join(os.path.dirname(__file__), "contract_store.json"))
_lock = threading.Lock()

def _load():
    if not os.path.exists(PATH):
        return {"templates": [], "versions": []}
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)

def _save(d):
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def list_templates():
    return [{k: t[k] for k in ("id", "name", "category", "created_at")} for t in _load()["templates"]]

def get_template(tid):
    return next((t for t in _load()["templates"] if t["id"] == tid), None)

def save_template(name, text, category="General"):
    with _lock:
        d = _load()
        t = {"id": uuid.uuid4().hex[:8], "name": name.strip(), "category": category, "text": text, "created_at": _now()}
        d["templates"].append(t); _save(d)
    return t

def delete_template(tid):
    with _lock:
        d = _load(); n = len(d["templates"])
        d["templates"] = [t for t in d["templates"] if t["id"] != tid]; _save(d)
    return n != len(d["templates"])

def add_version(doc_name, text, note=""):
    with _lock:
        d = _load()
        same = [v for v in d["versions"] if v["doc"] == doc_name]
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]
        if same and same[-1]["hash"] == digest:
            return {**same[-1], "unchanged": True}
        v = {"id": uuid.uuid4().hex[:8], "doc": doc_name, "version": len(same) + 1, "hash": digest,
             "note": note, "text": text, "created_at": _now()}
        d["versions"].append(v); _save(d)
    return v

def list_docs():
    docs = {}
    for v in _load()["versions"]:
        docs.setdefault(v["doc"], []).append({k: v[k] for k in ("id", "version", "note", "created_at", "hash")})
    return docs

def get_version(vid):
    return next((v for v in _load()["versions"] if v["id"] == vid), None)
