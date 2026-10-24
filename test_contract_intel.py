from contract_intel import (
    split_clauses, word_diff, values_in, redline, compare, extract_deadlines,
)

V1 = """EMPLOYMENT AGREEMENT

1. Position. The Employee shall serve as Software Engineer from 1 November 2026.

2. Salary. The Company shall pay the Employee a salary of Rs. 12,00,000 per annum, payable monthly.

3. Probation. The Employee shall be on probation for 3 months.

4. Termination. Either party may terminate this Agreement by giving 30 days' notice in writing.

5. Confidentiality. The Employee shall keep all Company information confidential.

6. Governing Law. This Agreement is governed by the laws of India and the courts at Delhi shall have jurisdiction.
"""

V2 = """EMPLOYMENT AGREEMENT

1. Position. The Employee shall serve as Software Engineer from 1 November 2026.

2. Salary. The Company shall pay the Employee a salary of Rs. 14,00,000 per annum, payable monthly.

3. Probation. The Employee shall be on probation for 6 months.

4. Termination. Either party may terminate this Agreement by giving 60 days' notice in writing.

5. Confidentiality. The Employee shall keep all Company information confidential.

6. Non-Compete. The Employee shall not compete with the Company for 12 months after leaving.

7. Governing Law. This Agreement is governed by the laws of India and the courts at Mumbai shall have jurisdiction.
"""


def test_values_money_duration_percent():
    v = {x["kind"]: x for x in values_in("Salary Rs. 12,00,000, notice thirty (30) days, interest 18% per annum")}
    assert v["money"]["key"] == ("money", "INR", 1200000)
    assert v["duration"]["key"] == ("duration", 30, "day", "")
    assert v["percent"]["key"] == ("percent", 18.0)
    assert values_in("₹12 lakh")[0]["key"] == ("money", "INR", 1200000)
    assert values_in("CTC of 18 LPA")[0]["key"] == ("money", "INR", 1800000)
    assert values_in("a 3-month probation")[0]["key"] == ("duration", 3, "month", "")


def test_split_clauses_numbered_and_blank_lines():
    cl = split_clauses(V1)
    assert len(cl) == 7 and cl[0] == "EMPLOYMENT AGREEMENT" and cl[2].startswith("2. Salary")
    wrapped = "1. First clause\ncontinues here\n2. Second clause\n30 days is long"
    assert split_clauses(wrapped) == ["1. First clause continues here", "2. Second clause 30 days is long"]


def test_word_diff_ignores_punctuation_only_changes():
    segs = word_diff("pay 30 days, notice.", "pay 30 days notice")
    assert all(s["op"] == "equal" for s in segs)
    segs = word_diff("notice of 30 days", "notice of 60 days")
    assert [s["op"] for s in segs] == ["equal", "delete", "insert", "equal"] or \
           {"delete", "insert"} <= {s["op"] for s in segs}


def test_redline_flags_salary_notice_probation_noncompete():
    r = redline(V1, V2)
    s = r["summary"]
    assert s["modified"] >= 4 and s["added"] >= 1 and s["review"] >= 4
    mods = {c["old"][:12]: c for c in r["changes"] if c["kind"] == "modified"}
    sal = mods["2. Salary. T"]
    assert sal["review"] and any("12,00,000" in d and "14,00,000" in d for d in sal["details"])
    term = mods["4. Terminati"]
    assert any("30 days" in d and "60 days" in d for d in term["details"])
    added = [c for c in r["changes"] if c["kind"] == "added"]
    assert any("non-compete" in " ".join(c["details"]).lower() and c["review"] for c in added)
    # unchanged clauses stay unflagged
    assert all(not c["review"] for c in r["changes"] if c["kind"] == "unchanged")


def test_redline_identical_and_removed():
    r = redline(V1, V1)
    assert r["summary"]["review"] == 0 and r["summary"]["unchanged"] == 7
    r2 = redline(V1, V1.replace("5. Confidentiality. The Employee shall keep all Company information confidential.\n\n", ""))
    assert r2["summary"]["removed"] == 1


def test_compare_rows_and_review_flags():
    c = compare(V1, V2)
    rows = {r["topic"]: r for r in c["rows"]}
    assert rows["Salary / compensation"]["status"] == "changed" and rows["Salary / compensation"]["review"]
    assert rows["Salary / compensation"]["a"]["value"].startswith("Rs. 12,00,000")
    assert rows["Notice period"]["status"] == "changed"
    assert rows["Probation"]["status"] == "changed" and not rows["Probation"]["review"]
    assert rows["Non-compete"]["status"] == "only_b" and rows["Non-compete"]["review"]
    assert rows["Confidentiality"]["status"] == "same"
    assert rows["Jurisdiction / arbitration"]["status"] == "changed"      # Delhi -> Mumbai
    assert rows["Jurisdiction / arbitration"]["a"]["value"] == "Delhi"
    assert c["summary"]["review"] >= 4


def test_compare_same_document():
    c = compare(V1, V1)
    assert all(r["status"] == "same" for r in c["rows"]) and c["summary"]["review"] == 0


DEAD = """The Employee shall submit all joining documents within 15 days of joining.
The Company shall pay the salary on or before the 5th day of each month.
This Agreement is effective from 1 November 2026.
The Tenant must pay the security deposit by 15/12/2026.
Either party may terminate by giving thirty (30) days' notice.
The Employee shall keep Company information confidential.
Reports are due quarterly.
The meeting was pleasant."""


def test_deadlines_dates_relative_recurring_undated():
    r = extract_deadlines(DEAD, start_date="2026-11-01", today="2026-11-10")
    class By(dict):
        def __getitem__(self, prefix):
            return next(v for k, v in self.items() if k.startswith(prefix))
    by = By({i["text"]: i for i in r["items"]})
    eff = by["This Agreement is effecti"]
    assert eff["date"] == "2026-11-01" and eff["status"] == "overdue" and not eff["is_obligation"]
    dep = by["The Tenant must pay the s"]
    assert dep["date"] == "2026-12-15" and dep["days_left"] == 35 and dep["status"] == "upcoming" and dep["type"] == "Payment"
    docs = by["The Employee shall submit"]
    assert docs["relative"]["amount"] == 15 and docs["date"] == "2026-11-16" and docs["due_from_start"]
    assert docs["relative"]["trigger"].startswith("of joining") and docs["party"] == "Employee"
    notice = by["Either party may termin"]
    assert notice["relative"]["amount"] == 30 and notice["relative"]["kind"] == "notice"
    assert notice["date"] is None and notice["status"] == "notice_period"      # a notice period is not a due date
    assert by["The Company shall pay the"]["recurring"] and by["The Company shall pay the"]["status"] == "recurring"
    assert by["The Employee shall keep C"]["status"] == "undated" and by["The Employee shall keep C"]["is_obligation"]
    assert not any("pleasant" in i["text"] for i in r["items"])          # nothing invented from plain prose
    assert r["summary"]["total"] == len(r["items"])


def test_deadlines_without_start_date_and_bad_input():
    r = extract_deadlines(DEAD, today="2026-11-10")
    docs = next(i for i in r["items"] if i["text"].startswith("The Employee shall submit"))
    assert docs["date"] is None and docs["status"] == "needs_start_date"
    assert extract_deadlines("", today="2026-01-01")["items"] == []
    assert extract_deadlines("The Tenant shall pay by 31/02/2026.", today="2026-01-01")["items"][0]["date"] is None   # impossible date ignored
    assert extract_deadlines("x", start_date="garbage", today="nope")["start_date"] is None


def test_months_and_year_arithmetic():
    from contract_intel import _add
    from datetime import date
    assert _add(date(2026, 1, 31), 1, "month") == date(2026, 2, 28)
    assert _add(date(2026, 11, 1), 2, "month") == date(2027, 1, 1)
    assert _add(date(2024, 2, 29), 1, "year") == date(2025, 2, 28)


def test_routes_work_end_to_end():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from contract_intel import router
    app = FastAPI(); app.include_router(router); c = TestClient(app)
    assert c.post("/contract/redline", json={"old": V1, "new": V2}).json()["summary"]["review"] >= 4
    assert c.post("/contract/compare", json={"a": V1, "b": V2}).json()["summary"]["changed"] >= 3
    assert c.post("/contract/deadlines", json={"text": DEAD, "start_date": "2026-11-01", "today": "2026-11-10"}).json()["summary"]["total"] >= 6
    assert c.post("/contract/redline", json={"old": "x" * 200_001, "new": "y"}).status_code == 422


def test_event_based_deadline_not_dated_from_start():
    r = extract_deadlines("The Buyer shall pay each invoice within 10 days of receipt of the invoice.",
                          start_date="2026-11-01", today="2026-11-10")
    it = r["items"][0]
    assert it["date"] is None and it["status"] == "event_based" and "receipt" in it["relative"]["trigger"]
    r2 = extract_deadlines("The Buyer shall pay the fee within 10 days.", start_date="2026-11-01", today="2026-11-10")
    assert r2["items"][0]["date"] == "2026-11-11"          # no trigger: counted from the effective date
