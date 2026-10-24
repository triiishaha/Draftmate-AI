"""
Templates & Version History (SQLite, standard library only; no setup needed).

  * Templates: text a user has approved for reuse. Saving one records who approved it and when.
  * Version history: every save of a document is a NEW numbered version. Old versions are never changed
    or deleted. "Restore" copies an old version into a new latest version, so history stays complete.
  * Compare any two versions with the same redline engine as Smart Redline.

The database file is created next to this module (draftmate_store.db). Set DRAFTMATE_DB to change it.
There is no login in this demo: anyone who can reach the server can read the store.

Routes (prefix /store): see the bottom of this file or CITATION_VERIFIER_README.md.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from contract_intel import MAX_CHARS, redline

MAX_TEMPLATES = 200
MAX_VERSIONS = 500
SCHEMA = """
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    category TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL REFERENCES documents(id),
    n INTEGER NOT NULL,
    text TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    sha TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (doc_id, n)
);
"""


class NotFound(LookupError):
    pass


class Conflict(ValueError):
    pass


class Invalid(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(s: Optional[str], limit: int, field: str, required: bool = False) -> str:
    s = (s or "").strip()
    if required and not s:
        raise Invalid(f"{field} is required.")
    if len(s) > limit:
        raise Invalid(f"{field} is too long (max {limit} characters).")
    return s


def _text(s: Optional[str]) -> str:
    s = s or ""
    if not s.strip():
        raise Invalid("The text is empty.")
    if len(s) > MAX_CHARS:
        raise Invalid(f"The text is too long (max {MAX_CHARS} characters).")
    return s


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, path: Optional[str] = None):
        self.path = path or os.getenv("DRAFTMATE_DB") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "draftmate_store.db")
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    # ---------------- templates ----------------
    @staticmethod
    def _tpl(r: sqlite3.Row, full: bool) -> dict:
        d = {"id": r["id"], "name": r["name"], "category": r["category"], "note": r["note"],
             "approved_by": r["approved_by"], "approved_at": r["approved_at"], "chars": len(r["text"])}
        d["text" if full else "preview"] = r["text"] if full else " ".join(r["text"].split())[:160]
        return d

    def save_template(self, name, text, category="", note="", approved_by="", replace=False) -> dict:
        name = _clean(name, 120, "Name", True)
        text = _text(text)
        category, note, by = _clean(category, 60, "Category"), _clean(note, 300, "Note"), _clean(approved_by, 80, "Approved by")
        with self._conn() as c:
            row = c.execute("SELECT id FROM templates WHERE name = ?", (name,)).fetchone()
            if row and not replace:
                raise Conflict(f"A template named '{name}' already exists. Choose another name or replace it on purpose.")
            if not row and c.execute("SELECT COUNT(*) FROM templates").fetchone()[0] >= MAX_TEMPLATES:
                raise Invalid("Template limit reached.")
            if row:
                c.execute("UPDATE templates SET text=?, category=?, note=?, approved_by=?, approved_at=? WHERE id=?",
                          (text, category, note, by, _now(), row["id"]))
                tid = row["id"]
            else:
                tid = c.execute("INSERT INTO templates (name, category, text, note, approved_by, approved_at) VALUES (?,?,?,?,?,?)",
                                (name, category, text, note, by, _now())).lastrowid
            return self._tpl(c.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone(), False) | {"replaced": bool(row)}

    def list_templates(self) -> list:
        with self._conn() as c:
            return [self._tpl(r, False) for r in c.execute("SELECT * FROM templates ORDER BY name COLLATE NOCASE")]

    def get_template(self, tid: int) -> dict:
        with self._conn() as c:
            r = c.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()
        if not r:
            raise NotFound("Template not found.")
        return self._tpl(r, True)

    def delete_template(self, tid: int) -> dict:
        with self._conn() as c:
            if c.execute("DELETE FROM templates WHERE id=?", (tid,)).rowcount == 0:
                raise NotFound("Template not found.")
        return {"deleted": tid}

    # ---------------- documents and versions ----------------
    def create_document(self, title) -> dict:
        title = _clean(title, 120, "Title", True)
        with self._conn() as c:
            row = c.execute("SELECT * FROM documents WHERE title = ?", (title,)).fetchone()
            if row:
                return {"id": row["id"], "title": row["title"], "created": False}
            did = c.execute("INSERT INTO documents (title, created_at) VALUES (?,?)", (title, _now())).lastrowid
            return {"id": did, "title": title, "created": True}

    def list_documents(self) -> list:
        with self._conn() as c:
            rows = c.execute("""SELECT d.id, d.title, d.created_at, COUNT(v.id) AS versions,
                                       COALESCE(MAX(v.n), 0) AS latest, MAX(v.created_at) AS updated_at
                                FROM documents d LEFT JOIN versions v ON v.doc_id = d.id
                                GROUP BY d.id ORDER BY COALESCE(MAX(v.created_at), d.created_at) DESC""").fetchall()
        return [dict(r) for r in rows]

    def _doc(self, c, doc_id: int) -> sqlite3.Row:
        r = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not r:
            raise NotFound("Document not found.")
        return r

    @staticmethod
    def _ver(r: sqlite3.Row, full: bool = False) -> dict:
        d = {"n": r["n"], "note": r["note"], "author": r["author"], "created_at": r["created_at"],
             "sha": r["sha"][:12], "chars": len(r["text"]), "words": len(r["text"].split())}
        if full:
            d["text"] = r["text"]
        return d

    def add_version(self, doc_id: int, text, note="", author="") -> dict:
        text = _text(text)
        note, author = _clean(note, 300, "Note"), _clean(author, 80, "Author")
        sha = _sha(text)
        with self._conn() as c:
            doc = self._doc(c, doc_id)
            last = c.execute("SELECT * FROM versions WHERE doc_id=? ORDER BY n DESC LIMIT 1", (doc_id,)).fetchone()
            if last and last["sha"] == sha:
                return {"unchanged": True, "document": doc["title"], "version": self._ver(last)}
            n = (last["n"] if last else 0) + 1
            if n > MAX_VERSIONS:
                raise Invalid("Version limit reached for this document.")
            c.execute("INSERT INTO versions (doc_id, n, text, note, author, sha, created_at) VALUES (?,?,?,?,?,?,?)",
                      (doc_id, n, text, note, author, sha, _now()))
            return {"unchanged": False, "document": doc["title"],
                    "version": self._ver(c.execute("SELECT * FROM versions WHERE doc_id=? AND n=?", (doc_id, n)).fetchone())}

    def list_versions(self, doc_id: int) -> dict:
        with self._conn() as c:
            doc = self._doc(c, doc_id)
            rows = c.execute("SELECT * FROM versions WHERE doc_id=? ORDER BY n DESC", (doc_id,)).fetchall()
        return {"id": doc["id"], "title": doc["title"], "versions": [self._ver(r) for r in rows]}

    def get_version(self, doc_id: int, n: int) -> dict:
        with self._conn() as c:
            doc = self._doc(c, doc_id)
            r = c.execute("SELECT * FROM versions WHERE doc_id=? AND n=?", (doc_id, n)).fetchone()
        if not r:
            raise NotFound("Version not found.")
        return {"document": doc["title"], **self._ver(r, True)}

    def diff(self, doc_id: int, a: int, b: int) -> dict:
        va, vb = self.get_version(doc_id, a), self.get_version(doc_id, b)
        return {"document": va["document"], "from": {k: va[k] for k in ("n", "note", "author", "created_at")},
                "to": {k: vb[k] for k in ("n", "note", "author", "created_at")}, **redline(va["text"], vb["text"])}

    def restore(self, doc_id: int, n: int, author="") -> dict:
        old = self.get_version(doc_id, n)
        out = self.add_version(doc_id, old["text"], f"Restored version {n}", author)
        out["restored_from"] = n
        return out


_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def set_store(s: Optional[Store]) -> None:     # tests and custom setups
    global _store
    _store = s


try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field

    router = APIRouter(prefix="/store")

    class TemplateReq(BaseModel):
        name: str = Field(..., max_length=200)
        text: str = Field(..., max_length=MAX_CHARS)
        category: str = Field("", max_length=200)
        note: str = Field("", max_length=1000)
        approved_by: str = Field("", max_length=200)
        replace: bool = False

    class DocReq(BaseModel):
        title: str = Field(..., max_length=200)

    class VersionReq(BaseModel):
        text: str = Field(..., max_length=MAX_CHARS)
        note: str = Field("", max_length=1000)
        author: str = Field("", max_length=200)

    class RestoreReq(BaseModel):
        n: int
        author: str = Field("", max_length=200)

    def _run(fn, *a, **k):
        try:
            return fn(*a, **k)
        except NotFound as e:
            raise HTTPException(404, str(e))
        except Conflict as e:
            raise HTTPException(409, str(e))
        except Invalid as e:
            raise HTTPException(422, str(e))

    @router.get("/templates")
    def templates_list():
        return {"templates": get_store().list_templates()}

    @router.post("/templates")
    def templates_save(req: TemplateReq):
        return _run(get_store().save_template, req.name, req.text, req.category, req.note, req.approved_by, req.replace)

    @router.get("/templates/{tid}")
    def templates_get(tid: int):
        return _run(get_store().get_template, tid)

    @router.delete("/templates/{tid}")
    def templates_delete(tid: int):
        return _run(get_store().delete_template, tid)

    @router.get("/documents")
    def documents_list():
        return {"documents": get_store().list_documents()}

    @router.post("/documents")
    def documents_create(req: DocReq):
        return _run(get_store().create_document, req.title)

    @router.get("/documents/{doc_id}/versions")
    def versions_list(doc_id: int):
        return _run(get_store().list_versions, doc_id)

    @router.post("/documents/{doc_id}/versions")
    def versions_add(doc_id: int, req: VersionReq):
        return _run(get_store().add_version, doc_id, req.text, req.note, req.author)

    @router.get("/documents/{doc_id}/versions/{n}")
    def versions_get(doc_id: int, n: int):
        return _run(get_store().get_version, doc_id, n)

    @router.get("/documents/{doc_id}/diff")
    def versions_diff(doc_id: int, a: int, b: int):
        return _run(get_store().diff, doc_id, a, b)

    @router.post("/documents/{doc_id}/restore")
    def versions_restore(doc_id: int, req: RestoreReq):
        return _run(get_store().restore, doc_id, req.n, req.author)
except ImportError:
    router = None
