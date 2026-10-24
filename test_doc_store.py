import pytest

import doc_store
from doc_store import Store, NotFound, Conflict, Invalid

V1 = "1. Salary. The Company shall pay Rs. 12,00,000 per annum.\n\n2. Notice. Either party may terminate by giving 30 days' notice."
V2 = V1.replace("12,00,000", "14,00,000")
V3 = V2.replace("30 days", "60 days")


@pytest.fixture
def s(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_template_save_list_get_delete(s):
    t = s.save_template("Employment v1", V1, category="HR", approved_by="Aarush", note="Approved by counsel")
    assert t["replaced"] is False and t["approved_by"] == "Aarush" and t["approved_at"].endswith("+00:00")
    assert s.list_templates()[0]["preview"].startswith("1. Salary") and "text" not in s.list_templates()[0]
    assert s.get_template(t["id"])["text"] == V1
    assert s.delete_template(t["id"]) == {"deleted": t["id"]}
    with pytest.raises(NotFound):
        s.get_template(t["id"])
    with pytest.raises(NotFound):
        s.delete_template(t["id"])


def test_template_name_clash_needs_explicit_replace(s):
    s.save_template("NDA", V1)
    with pytest.raises(Conflict):
        s.save_template("nda", V2)                       # names are case-insensitive
    assert s.get_template(s.list_templates()[0]["id"])["text"] == V1      # nothing was overwritten
    r = s.save_template("nda", V2, replace=True)
    assert r["replaced"] is True and s.get_template(r["id"])["text"] == V2 and len(s.list_templates()) == 1


def test_validation(s):
    for bad in ({"name": "", "text": V1}, {"name": "x", "text": "   "}, {"name": "x" * 121, "text": V1},
                {"name": "x", "text": "y" * 200_001}, {"name": "x", "text": V1, "note": "n" * 301}):
        with pytest.raises(Invalid):
            s.save_template(**bad)


def test_versions_are_append_only_and_numbered(s):
    d = s.create_document("Employment contract")
    assert d["created"] is True and s.create_document("employment CONTRACT") == {**d, "created": False}
    a = s.add_version(d["id"], V1, "First draft", "Aarush")
    b = s.add_version(d["id"], V2, "Raised salary", "Trisha")
    c = s.add_version(d["id"], V3, "Notice 60 days")
    assert [a["version"]["n"], b["version"]["n"], c["version"]["n"]] == [1, 2, 3]
    vs = s.list_versions(d["id"])["versions"]
    assert [v["n"] for v in vs] == [3, 2, 1] and "text" not in vs[0] and vs[1]["author"] == "Trisha"
    assert s.get_version(d["id"], 1)["text"] == V1          # old versions are untouched


def test_saving_identical_text_does_not_create_a_version(s):
    d = s.create_document("Doc")
    s.add_version(d["id"], V1)
    r = s.add_version(d["id"], V1, "again")
    assert r["unchanged"] is True and len(s.list_versions(d["id"])["versions"]) == 1
    assert s.add_version(d["id"], V1 + " ")["unchanged"] is False        # any real edit counts


def test_diff_between_any_two_versions(s):
    d = s.create_document("Doc")
    for t in (V1, V2, V3):
        s.add_version(d["id"], t)
    r = s.diff(d["id"], 1, 3)
    assert r["from"]["n"] == 1 and r["to"]["n"] == 3 and r["summary"]["modified"] == 2 and r["summary"]["review"] >= 1
    details = " ".join(x for c in r["changes"] for x in c["details"])
    assert "12,00,000" in details and "14,00,000" in details and "30 days" in details and "60 days" in details
    assert s.diff(d["id"], 2, 2)["summary"]["modified"] == 0
    with pytest.raises(NotFound):
        s.diff(d["id"], 1, 9)


def test_restore_makes_a_new_version_and_keeps_history(s):
    d = s.create_document("Doc")
    for t in (V1, V2, V3):
        s.add_version(d["id"], t)
    r = s.restore(d["id"], 1, "Aarush")
    assert r["restored_from"] == 1 and r["version"]["n"] == 4 and r["version"]["note"] == "Restored version 1"
    assert s.get_version(d["id"], 4)["text"] == V1 and s.get_version(d["id"], 3)["text"] == V3
    assert s.restore(d["id"], 4)["unchanged"] is True              # already the latest text
    with pytest.raises(NotFound):
        s.restore(d["id"], 99)


def test_documents_list_and_unknown_ids(s):
    a, b = s.create_document("A"), s.create_document("B")
    s.add_version(a["id"], V1)
    docs = {x["title"]: x for x in s.list_documents()}
    assert docs["A"]["versions"] == 1 and docs["A"]["latest"] == 1 and docs["B"]["versions"] == 0
    with pytest.raises(NotFound):
        s.add_version(999, V1)
    with pytest.raises(NotFound):
        s.list_versions(999)


def test_sql_injection_is_just_text(s):
    evil = "x'); DROP TABLE templates;--"
    t = s.save_template(evil, V1)
    assert s.get_template(t["id"])["name"] == evil and len(s.list_templates()) == 1


def test_data_survives_a_new_connection(tmp_path):
    p = str(tmp_path / "keep.db")
    d = Store(p).create_document("Doc")
    Store(p).add_version(d["id"], V1, "kept")
    assert Store(p).list_versions(d["id"])["versions"][0]["note"] == "kept"


def test_routes_end_to_end(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    doc_store.set_store(Store(str(tmp_path / "r.db")))
    app = FastAPI(); app.include_router(doc_store.router); c = TestClient(app)
    try:
        t = c.post("/store/templates", json={"name": "NDA", "text": V1, "approved_by": "Aarush"}).json()
        assert c.post("/store/templates", json={"name": "NDA", "text": V2}).status_code == 409
        assert c.get(f"/store/templates/{t['id']}").json()["text"] == V1
        assert c.get("/store/templates/999").status_code == 404
        assert c.post("/store/templates", json={"name": "", "text": V1}).status_code == 422
        d = c.post("/store/documents", json={"title": "Contract"}).json()
        for text in (V1, V2):
            c.post(f"/store/documents/{d['id']}/versions", json={"text": text, "author": "A"})
        assert [v["n"] for v in c.get(f"/store/documents/{d['id']}/versions").json()["versions"]] == [2, 1]
        assert c.get(f"/store/documents/{d['id']}/diff", params={"a": 1, "b": 2}).json()["summary"]["modified"] == 1
        assert c.post(f"/store/documents/{d['id']}/restore", json={"n": 1}).json()["version"]["n"] == 3
        assert c.get(f"/store/documents/{d['id']}/versions/7").status_code == 404
        assert c.delete(f"/store/templates/{t['id']}").json() == {"deleted": t["id"]}
    finally:
        doc_store.set_store(None)
