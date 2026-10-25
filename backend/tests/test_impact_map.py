from impact_map import impact_map, match_law, topics_from_change, list_laws, LAWS, TOPICS

CONTRACT = """EMPLOYMENT AGREEMENT

1. Salary. The Company shall pay the Employee a salary of Rs. 12,00,000 per annum and a performance bonus.

2. Termination. Either party may terminate this Agreement by giving 30 days' notice in writing.

3. Non-Compete. The Employee shall not compete with the Company for 12 months after leaving.

4. Confidentiality. The Employee shall keep all personal data and Company information confidential and shall not disclose it.

5. Disputes. Any dispute shall be settled by arbitration in Mumbai. The courts at Mumbai shall have jurisdiction.
"""


def fake_research(q):
    return {"results": [{"title": "Section 27 in The Indian Contract Act, 1872", "url": "https://indiankanoon.org/doc/1/",
                         "court": "Central Act", "snippet": "Agreement in restraint of trade, void"}] * 5}


def test_every_law_points_only_at_known_topics():
    for lid, law in LAWS.items():
        assert law["topics"] and law["query"] and law["name"]
        assert set(law["topics"]) <= set(TOPICS), lid


def test_match_law_by_name_alias_and_typo():
    assert match_law("Indian Contract Act, 1872") == "contract_act"
    assert match_law("DPDP") == "dpdp"
    assert match_law("code on wages 2019") == "wages_code"
    assert match_law("Digital Personal Data Protection Act") == "dpdp"
    assert match_law("Industrial Relation Code") == "ir_code"          # small typo still matches
    assert match_law("GST") == "cgst"
    assert match_law("") is None and match_law("Law of the Jungle") is None
    assert match_law("the dpdp act 2023") == "dpdp" and match_law("gst on invoices") == "cgst"
    assert match_law("code") is None and match_law("act") is None and match_law("labour code") is None   # too vague: no guessing


def test_contract_act_flags_noncompete_and_jurisdiction_with_quotes_and_sources():
    r = impact_map(CONTRACT, "Indian Contract Act", researcher=fake_research)
    got = {i["topic"]: i for i in r["impacted"]}
    assert "restraint" in got and "Non-Compete" in got["restraint"]["clauses"][0]
    assert "Section 27" in got["restraint"]["why"]
    assert "jurisdiction" in got and any("Mumbai" in c for c in got["jurisdiction"]["clauses"])
    assert r["law"] == "Indian Contract Act, 1872" and r["law_id"] == "contract_act"
    assert len(r["sources"]) == 3 and r["sources"][0]["url"].startswith("https://indiankanoon.org/doc/")
    assert r["search_url"] == "https://indiankanoon.org/search/?formInput=Indian+Contract+Act+1872"
    assert "do not say whether" in r["disclaimer"]


def test_clauses_are_quoted_from_the_contract():
    r = impact_map(CONTRACT, "Industrial Relations Code 2020")
    flat = " ".join(CONTRACT.split())
    for imp in r["impacted"]:
        for c in imp["clauses"]:
            assert c in flat or c[:30] in flat


def test_topics_with_no_clause_are_reported_not_invented():
    r = impact_map(CONTRACT, "Payment of Gratuity Act")
    assert r["impacted"] == []
    assert [x["topic"] for x in r["no_clause_found"]] == ["benefits"]


def test_unknown_law_uses_only_the_users_description():
    r = impact_map(CONTRACT, "New Employment Rules 2027", change="notice period for resignation is now 60 days")
    assert r["law_id"] is None and "do not have this law" in r["note"]
    assert [i["topic"] for i in r["impacted"]] == ["termination"]
    r2 = impact_map(CONTRACT, "Some Unmapped Statute")
    assert r2["impacted"] == [] and "could not map" in r2["note"]


def test_description_adds_topics_for_a_known_law():
    r = impact_map(CONTRACT, "Digital Personal Data Protection Act, 2023", change="consent and arbitration rules")
    topics = [i["topic"] for i in r["impacted"]]
    assert "data" in topics and "arbitration" in topics


def test_researcher_failure_never_breaks_the_map():
    def boom(q): raise TimeoutError()
    r = impact_map(CONTRACT, "Indian Contract Act", researcher=boom)
    assert r["sources"] == [] and r["impacted"] and r["search_url"]


def test_topics_from_change_and_list():
    assert "data" in topics_from_change("personal data consent") and topics_from_change("hello") == []
    assert len(list_laws()) == len(LAWS)


def test_routes(monkeypatch):
    import research
    monkeypatch.setattr(research, "research", lambda q, kind="all", **k: {"results": []})   # no network, whatever token you have set
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from impact_map import router
    app = FastAPI(); app.include_router(router); c = TestClient(app)
    assert any(l["id"] == "dpdp" for l in c.get("/contract/laws").json()["laws"])
    r = c.post("/contract/impact", json={"text": CONTRACT, "law": "Indian Contract Act"}).json()
    assert r["impacted"] and r["sources"] == []          # nothing found: honest empty sources, link still given
    assert r["search_url"]
    assert c.post("/contract/impact", json={"text": CONTRACT}).status_code == 422


def test_route_accepts_null_change(monkeypatch):
    import research
    monkeypatch.setattr(research, "research", lambda q, kind="all", **k: {"results": []})
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from impact_map import router
    app = FastAPI(); app.include_router(router)
    r = TestClient(app).post("/contract/impact", json={"text": CONTRACT, "law": "Indian Contract Act", "change": None})
    assert r.status_code == 200 and r.json()["impacted"]
