import pytest
from context_opt import optimize, clean, split_sections, est_tokens, CITATION


def make_contract(n=14):
    parts = ["EMPLOYMENT AGREEMENT\n\nThis Agreement is made between Acme Pvt Ltd and Ravi Kumar."]
    topics = ["Salary", "Termination", "Confidentiality", "Leave", "Governing Law", "Non-Compete", "Training", "Travel",
              "Equipment", "Data Protection", "Notices", "Amendments", "Severability", "Entire Agreement"]
    for i in range(n):
        body = f"{i+1}. {topics[i]}\n\nThe parties agree on the following about {topics[i].lower()}. " + "Lorem ipsum filler sentence for the clause. " * 30
        parts.append(body)
    return "\n\n".join(parts)


def test_est_tokens_is_positive_and_monotonic():
    assert est_tokens("") == 0 and est_tokens("hello world") >= 2
    assert est_tokens("word " * 400) > est_tokens("word " * 100)


def test_clean_drops_repeated_headers_page_numbers_and_duplicates():
    pages = ["Acme Confidential\n" + f"Para {i} " + "text " * 30 + "\n12\n" for i in range(5)]
    dup = "Real clause text here " * 5
    body = "\n\n".join(["intro line"] + pages + [dup, dup]) + "\n" * 30
    out, steps = clean(body)
    assert "Acme Confidential" not in out and "repeated header" in " ".join(steps)
    assert out.split("\n\n").count(dup.strip()) == 1 and "duplicate" in " ".join(steps)


def test_clean_keeps_headings_even_if_repeated():
    t = "\n\n".join(["1. Payment\n\ntext a"] * 1 + ["Section 2\n\ntext b"] + ["Section 2\n\ntext c"] + ["Section 2\n\ntext d"])
    out, _ = clean(t)
    assert out.count("Section 2") == 3


def test_split_sections_follow_numbered_clauses():
    secs = split_sections(make_contract(5))
    assert len(secs) >= 5 and any("Salary" in s["title"] for s in secs) and all(s["tokens"] > 0 for s in secs)


def test_query_keeps_matching_sections_and_stays_in_budget():
    t = make_contract(14)
    r = optimize(t, "termination notice", max_tokens=900)
    assert r["final_tokens"] <= 900 and r["within_budget"] and r["saved_pct"] > 40
    kept_titles = [s["title"] for s in r["sections"] if s["kept"]]
    assert any("Termination" in k for k in kept_titles)
    assert "Termination" in r["text"] and "[Omitted" in r["text"]
    # original wording and order
    assert r["text"].index("Termination") < r["text"].index("Notices") if "Notices" in r["text"] else True


def test_everything_fits_means_nothing_dropped():
    r = optimize(make_contract(3), "salary", max_tokens=50_000)
    assert all(s["kept"] for s in r["sections"]) and "[Omitted" not in r["text"] and r["saved_pct"] <= 10


def test_citations_are_counted_and_favoured():
    t = make_contract(10) + "\n\n11. Authorities\n\nSee Section 27 of the Indian Contract Act, 1872 and AIR 1967 SC 1098 on restraint of trade."
    r = optimize(t, "salary", max_tokens=700)
    assert r["citations"]["total"] >= 2
    assert r["citations"]["kept"] == r["citations"]["total"] and r["citations"]["lost"] == []


def test_citation_regex_finds_common_forms():
    s = "AIR 1950 SC 27; (2017) 10 SCC 1; Section 74 of the Indian Contract Act, 1872; Article 21"
    found = [m.group(0) for m in CITATION.finditer(s)]
    assert len(found) >= 3


def test_no_query_uses_legal_signals():
    r = optimize(make_contract(14), "", max_tokens=700)
    assert r["final_tokens"] <= 700 and r["query_terms"] == []


def test_tiny_budget_still_returns_something_and_validates():
    r = optimize(make_contract(6), "salary", max_tokens=100)
    assert r["text"].strip()
    with pytest.raises(ValueError):
        optimize("   ")
    with pytest.raises(ValueError):
        optimize("x" * 2_000_001)


def test_route():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from context_opt import router
    app = FastAPI(); app.include_router(router); c = TestClient(app)
    r = c.post("/context/optimize", json={"text": make_contract(10), "query": "termination", "max_tokens": 800}).json()
    assert r["final_tokens"] <= 800 and r["saved_tokens"] > 0
    assert c.post("/context/optimize", json={"text": "  ", "max_tokens": 800}).status_code == 422
    assert c.post("/context/optimize", json={"text": "abc", "max_tokens": 5}).status_code == 422


@pytest.mark.parametrize("budget", [100, 300, 600, 800, 2000])
def test_budget_is_a_hard_limit_even_when_one_section_is_bigger_than_it(budget):
    big = "\n\n".join([f"{i}. {t}\n\n{t} terms. " + "Standard filler wording applies here. " * 90
                       for i, t in enumerate(["Payment", "Termination", "Notices", "Liability"], 1)])
    r = optimize(big, "termination", max_tokens=budget)
    assert r["final_tokens"] <= budget and r["within_budget"]
    assert "Termination" in r["text"]
