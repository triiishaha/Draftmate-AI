from risk_radar import risk_radar, AXES

GOOD = """SERVICES AGREEMENT

1. Services. The Vendor shall provide software development services to the Client.

2. Fees. The Client shall pay the Vendor Rs. 5,00,000 within 30 days of each invoice.

3. Termination. Either party may terminate this Agreement by giving 30 days' written notice to the other party.

4. Confidentiality. Each party shall keep the other's information confidential.

5. Liability. The liability of either party shall not exceed the fees paid in the previous 12 months, and each party shall indemnify the other only for losses caused by its own negligence.

6. Force Majeure. Neither party is liable for delay caused by events beyond its reasonable control.

7. Disputes. Disputes shall be settled by arbitration in Mumbai before a sole arbitrator agreed by both parties. The courts at Mumbai shall have jurisdiction.

8. Governing Law. This Agreement is governed by the laws of India.

9. Entire Agreement. This Agreement supersedes all earlier discussions. Any amendment must be in writing, and if any clause is invalid or unenforceable the rest remains in force. Neither party may assign this Agreement without consent.
"""

BAD = """EMPLOYMENT AGREEMENT

1. The Company may terminate this Agreement at any time without notice at its sole discretion.

2. The Employee shall not, directly or indirectly, compete with the Company anywhere in India for 3 years after leaving.

3. The Employee shall be liable for all losses and damages suffered by the Company and shall indemnify the Company against any and all claims.

4. This Agreement shall automatically renew each year. A penalty of Rs. 2,00,000 is payable on early exit and any payment is forfeited.

5. Interest on late payment shall be charged at 3% per month.

6. The sole arbitrator shall be appointed by the Company.

7. The Employee waives all rights and claims against the Company. All intellectual property created shall be assigned to the Company in perpetuity.

8. The notice period is ______ and bonus is as may be deemed fit by the management as per company policy, and other benefits from time to time, etc.
""" + "x" * 0


def by_id(r, rid):
    return [f for f in r["findings"] if f["id"] == rid]


def test_clean_contract_scores_low_and_has_no_missing():
    r = risk_radar(GOOD)
    assert r["level"] == "Low", [f["title"] for f in r["findings"]]
    assert r["counts"]["missing"] == 0 and r["counts"]["high"] == 0


def test_bad_contract_flags_the_obvious_risks():
    r = risk_radar(BAD)
    ids = {f["id"] for f in r["findings"]}
    for want in ("unilateral_termination", "sole_discretion", "non_compete", "unlimited_liability", "auto_renew",
                 "penalty_clause", "waiver", "perpetual", "one_sided_arbitrator", "ip_assignment", "high_rate",
                 "placeholder", "deemed_fit", "external_policy", "from_time_to_time", "etc"):
        assert want in ids, want
    assert r["level"] == "High" and r["score"] >= 55


def test_every_finding_quotes_the_contract_or_is_a_missing_clause():
    for f in risk_radar(BAD)["findings"]:
        if f["kind"] == "missing":
            assert f["quote"] is None
        else:
            assert f["quote"] and f["quote"].split()[0] in BAD.replace("\n", " ")
            assert f["quote"][:40] in " ".join(BAD.split()) or f["quote"][:25] in " ".join(BAD.split())
        assert f["why"] and f["suggestion"]


def test_missing_clauses_only_for_full_length_contracts():
    short = risk_radar("The Tenant shall pay rent.")
    assert short["counts"]["missing"] == 0 and short["checked_missing"] is False
    partial = "AGREEMENT\n\n" + ("The Supplier shall deliver goods to the Buyer and the Buyer shall pay the price. " * 8)
    r = risk_radar(partial)
    names = {f["id"] for f in r["findings"] if f["kind"] == "missing"}
    assert {"missing_termination", "missing_governing_law"} <= names and "missing_payment" not in names
    assert r["checked_missing"] is True


def test_high_rate_thresholds():
    assert by_id(risk_radar("Interest shall be charged at 3% per month on late payment."), "high_rate")[0]["severity"] == "high"
    assert by_id(risk_radar("Interest shall be charged at 18% per annum on late payment."), "high_rate")[0]["severity"] == "medium"
    assert by_id(risk_radar("Interest shall be charged at 9% per annum on late payment."), "high_rate") == []


def test_law_pointers_are_hedged_and_link_to_a_search():
    f = by_id(risk_radar(BAD), "non_compete")[0]
    assert f["law"]["section"] == "27" and "may be unenforceable" in f["law"]["note"]
    assert f["law"]["url"].startswith("https://indiankanoon.org/search/?formInput=Section+27")


def test_axes_counts_and_order():
    r = risk_radar(BAD)
    assert list(r["axes"]) == AXES and all(0 <= v <= 100 for v in r["axes"].values())
    assert r["axes"]["Restrictions"] > 0 and r["axes"]["Termination"] > 0
    sev = [f["severity"] for f in r["findings"]]
    assert sev == sorted(sev, key=["high", "medium", "low"].index)
    assert [f["n"] for f in r["findings"]] == list(range(1, len(r["findings"]) + 1))


def test_empty_and_route():
    r = risk_radar("")
    assert r["findings"] == [] and r["score"] == 0 and r["level"] == "Low"
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from risk_radar import router
    app = FastAPI(); app.include_router(router)
    c = TestClient(app)
    assert c.post("/contract/risk", json={"text": BAD}).json()["level"] == "High"
    assert c.post("/contract/risk", json={"text": "x" * 200_001}).status_code == 422
