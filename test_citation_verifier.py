from citation_verifier import (
    extract_citations, verify_draft, SourceHit, Citation, _name_sim,
)

DRAFT = (
    "As held in Kesavananda Bharati v. State of Kerala (1973) 4 SCC 225, the basic structure "
    "cannot be amended. See also Maneka Gandhi v. Union of India, AIR 1978 SC 597. "
    "The complainant relies on Section 138 of the Negotiable Instruments Act, 1881. "
    "Reliance is also placed on Rajesh Kumar v. Imaginary Traders Pvt Ltd (2019) 7 SCC 999."
)


class FakeSource:
    """Stands in for Indian Kanoon so tests run offline."""
    DB = [
        SourceHit("Kesavananda Bharati vs State Of Kerala And Anr on 24 April, 1973",
                  "https://indiankanoon.org/doc/257876/", "1973", "Supreme Court"),
        SourceHit("Maneka Gandhi vs Union Of India on 25 January, 1978",
                  "https://indiankanoon.org/doc/1766147/", "1978", "Supreme Court"),
        SourceHit("Negotiable Instruments Act, 1881", "https://indiacode.nic.in/x", "1881"),
    ]

    def search(self, c: Citation):
        key = c.name or c.act or ""
        return [h for h in self.DB if _name_sim(key, h.title) >= 0.5]


def test_extraction():
    cites = extract_citations(DRAFT)
    names = [c.name or c.act for c in cites]
    assert any("Kesavananda" in n for n in names)
    assert any("Maneka" in n for n in names)
    assert any("Negotiable" in n for n in names)
    assert any("Imaginary" in n for n in names)


def test_statuses():
    rep = verify_draft(DRAFT, sources=[FakeSource()])
    by = {(i["citation"]["name"] or i["citation"]["act"]): i for i in rep["items"]}
    kes = next(v for k, v in by.items() if "Kesavananda" in k)
    fake = next(v for k, v in by.items() if "Imaginary" in k)
    assert kes["status"] == "verified"
    assert fake["status"] == "unverified"
    assert fake["source"] is None   # never attach a source to an unverified item


def test_year_mismatch_downgrades():
    wrong = "Maneka Gandhi v. Union of India, AIR 1985 SC 597."
    rep = verify_draft(wrong, sources=[FakeSource()])
    assert rep["items"][0]["status"] != "verified"


if __name__ == "__main__":
    import json
    print(json.dumps(verify_draft(DRAFT, sources=[FakeSource()])["summary"]))
    for i in verify_draft(DRAFT, sources=[FakeSource()])["items"]:
        c = i["citation"]
        print(f'{i["status"]:20} {i["score"]:.2f}  {(c["name"] or c["act"])[:50]}')
