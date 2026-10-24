from citation_verifier import (
    extract_citations, verify_draft, SourceHit, Citation, _name_sim, IndianKanoonSource,
)

# Same shape as the real draft Trisha ran: sentence words ("See", "Also") glued to case names.
DRAFT = (
    "As held in Kesavananda Bharati v. State of Kerala (1973) 4 SCC 225, the basic structure stands. "
    "See Maneka Gandhi v. Union of India, AIR 1978 SC 597. "
    "The complainant relies on Section 138 of the Negotiable Instruments Act, 1881. "
    "Also Rajesh Kumar v. Imaginary Traders Pvt Ltd (2019) 7 SCC 999."
)


class FakeSource:
    """Mimics real Indian Kanoon results, including long titles and noisy hits
    (titles copied from the live API output)."""
    DB = [
        SourceHit("Article 13 in Constitution of India", "https://indiankanoon.org/doc/134715/", None),
        SourceHit("Kesavananda Bharati Sripadagalvaru ... vs State Of Kerala And Anr on 24 April, 1973",
                  "https://indiankanoon.org/doc/257876/", "1973", "Supreme Court of India"),
        SourceHit("Minerva Mills Ltd. & Ors vs Union Of India & Ors on 31 July, 1980",
                  "https://indiankanoon.org/doc/1939993/", "1980", "Supreme Court of India"),
        SourceHit("Maneka Gandhi vs Union Of India on 25 January, 1978",
                  "https://indiankanoon.org/doc/1766147/", "1978", "Supreme Court of India"),
        SourceHit("Section 138 in The Negotiable Instruments Act, 1881",
                  "https://indiankanoon.org/doc/x/", "1881", "Central Act"),
    ]

    def search(self, c: Citation):
        return list(self.DB)      # worst case: return everything, let the scorer decide


def _by_name(rep, word):
    return next(i for i in rep["items"] if word in (i["citation"]["name"] or i["citation"]["act"]))


def test_extraction_strips_sentence_words():
    names = [c.name or c.act for c in extract_citations(DRAFT)]
    assert "Maneka Gandhi v. Union of India" in names          # not "See Maneka Gandhi ..."
    assert any(n.startswith("Rajesh Kumar") for n in names)    # not "Also Rajesh Kumar ..."
    assert any("Negotiable" in n for n in names)


def test_long_real_titles_match():
    assert _name_sim("Kesavananda Bharati v. State of Kerala",
                     "Kesavananda Bharati Sripadagalvaru ... vs State Of Kerala And Anr on 24 April, 1973") >= 0.85
    assert _name_sim("Kesavananda Bharati v. State of Kerala",
                     "Minerva Mills Ltd. & Ors vs Union Of India & Ors on 31 July, 1980") < 0.55


def test_statuses():
    rep = verify_draft(DRAFT, sources=[FakeSource()])
    assert _by_name(rep, "Kesavananda")["status"] == "verified"
    assert _by_name(rep, "Maneka")["status"] == "verified"
    assert _by_name(rep, "Negotiable")["status"] == "verified"
    fake = _by_name(rep, "Imaginary")
    assert fake["status"] == "unverified"
    assert fake["source"] is None   # never attach a source to an unverified item


def test_year_mismatch_downgrades():
    rep = verify_draft("Maneka Gandhi v. Union of India, AIR 1985 SC 597.", sources=[FakeSource()])
    assert rep["items"][0]["status"] != "verified"


def test_query_building():
    c = Citation(raw="x", kind="case", name="Kesavananda Bharati v. State of Kerala")
    qs = IndianKanoonSource._queries(c)
    assert qs[0] == "title: kesavananda bharati kerala"
    s = Citation(raw="x", kind="statute", section="138", act="Negotiable Instruments Act, 1881")
    assert "section 138 Negotiable Instruments Act" in IndianKanoonSource._queries(s)[0]


if __name__ == "__main__":
    rep = verify_draft(DRAFT, sources=[FakeSource()])
    print(rep["summary"])
    for i in rep["items"]:
        c = i["citation"]
        print(f'{i["status"]:20} {i["score"]:.2f}  {(c["name"] or c["act"])[:50]}')
