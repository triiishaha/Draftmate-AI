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


def test_naming_variants_in_real_titles():
    # Indian Kanoon abbreviates / reformats some titles
    assert _name_sim("Shreya Singhal v. Union of India",
                     "Shreya Singhal vs U.O.I on 24 March, 2015") >= 0.85
    assert _name_sim("K.S. Puttaswamy v. Union of India",
                     "Justice K.S.Puttaswamy(Retd) vs Union Of India on 24 August, 2017") >= 0.85
    assert _name_sim("K.S. Puttaswamy v. Union of India",
                     "Justice Puttaswamy vs Union Of India") >= 0.85
    # still must not match unrelated cases that share generic words
    assert _name_sim("Rajesh Kumar v. Imaginary Traders Pvt Ltd",
                     "Rajesh Kumar vs State Of Bihar on 3 May, 2010") < 0.55
    assert _name_sim("Navtej Singh Johar v. Union of India",
                     "Article 13 in Constitution of India") == 0.0


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


# ---------------- LLM extraction pass ----------------
import json as _json
from citation_verifier import extract_citations_hybrid, verify_citation

TEXT2 = ("The petitioner relies on Article 21 of the Constitution of India. "
         "Refer Bandhua Mukti Morcha v. Union of India, 1984 3 SCC 161. "
         "Reliance is also placed on Indra Sawhney (1992) Supp (3) SCC 217. "
         "The Court also followed Totally Fake v. Nobody Ltd (2020) 1 SCC 1.")


def fake_llm(prompt: str) -> str:
    return "```json\n" + _json.dumps([
        # regex only sees the bare name; LLM supplies the year -> enrichment
        {"quote": "Bandhua Mukti Morcha v. Union of India, 1984 3 SCC 161", "kind": "case",
         "name": "Bandhua Mukti Morcha v. Union of India", "year": "1984", "reporter": "SCC"},
        # regex cannot see this at all (no "v.")
        {"quote": "Indra Sawhney (1992) Supp (3) SCC 217", "kind": "case",
         "name": "Indra Sawhney", "year": "1992", "reporter": "SCC"},
        # HALLUCINATED: quote is not in the draft -> must be dropped
        {"quote": "Maneka Gandhi v. Union of India (1978) 1 SCC 248", "kind": "case",
         "name": "Maneka Gandhi v. Union of India", "year": "1978"},
        # name words invented (not in the quote) -> must be dropped
        {"quote": "Reliance is also placed", "kind": "case",
         "name": "Kesavananda Bharati v. State of Kerala", "year": None},
    ]) + "\n```"


def test_names_do_not_swallow_neighbouring_sentences():
    t = ("Article 21 applies under the Constitution of India. Refer Bandhua Mukti Morcha v. "
         "Union of India. The Court then held otherwise. Mohd. Ahmed Khan v. Shah Bano Begum "
         "(1985) 2 SCC 556 is also relevant, as is Hindustan Lever Ltd. v. Ashok Kate.")
    got = {c.name: c for c in extract_citations(t) if c.kind == "case"}
    assert "Bandhua Mukti Morcha v. Union of India" in got            # no 'Refer', no 'The Court'
    assert "Mohd. Ahmed Khan v. Shah Bano Begum" in got               # 'Mohd.' is not a sentence end
    assert "Hindustan Lever Ltd. v. Ashok Kate" in got
    b = got["Bandhua Mukti Morcha v. Union of India"]
    assert t[b.span[0]:b.span[1]] == "Bandhua Mukti Morcha v. Union of India"


def test_suggestion_for_wrong_year():
    class Src:
        def search(self, c):
            return [SourceHit("Vishaka And Ors vs State Of Rajasthan And Ors on 13 August, 1997",
                              "https://indiankanoon.org/doc/1031794/", "1997", "Supreme Court of India")]
    c = extract_citations("See Vishaka v. State of Rajasthan, AIR 1999 SC 3011.")[0]
    v = verify_citation(c, [Src()])
    assert v.status == "partially_verified"
    s = v.suggestion
    assert "1997" in s["message"] and "1999" in s["message"]
    assert s["replace_with"] == "Vishaka v. State of Rajasthan, AIR 1997 SC 3011"
    assert s["source_url"].endswith("/1031794/")


def test_no_suggestion_when_verified_or_unverified():
    rep = verify_draft(DRAFT, sources=[FakeSource()])
    for i in rep["items"]:
        if i["status"] in ("verified", "unverified"):
            assert i["suggestion"] is None


def test_suggestion_never_rewrites_when_name_is_shaky():
    class Src:
        def search(self, c):
            return [SourceHit("Shreya Singhal vs Union Of India on 24 March, 2015", "u", "2015")]
    c = Citation(raw="Shreya Singhal v. Union of India (2012) 5 SCC 1", kind="case",
                 name="Shreya Singhal v. Union of India", year="2012")
    v = verify_citation(c, [Src()])
    assert v.suggestion["replace_with"] == "Shreya Singhal v. Union of India (2015) 5 SCC 1"
    # an unrelated name must get no suggestion and no source, however similar the year looks
    c2 = Citation(raw="Totally Different v. Union of India (2015) 5 SCC 1", kind="case",
                  name="Totally Different v. Union of India", year="2015")
    v2 = verify_citation(c2, [Src()])
    assert v2.status == "unverified" and v2.suggestion is None and v2.source is None


def test_article_regex_without_llm():
    cites = extract_citations("Article 21 of the Constitution of India applies.")
    assert cites[0].kind == "statute" and cites[0].section == "21"
    assert cites[0].act == "Constitution of India"


def test_llm_fills_gaps_and_enriches():
    cites = extract_citations_hybrid(TEXT2, completer=fake_llm)
    by = {(c.name or c.act): c for c in cites}
    assert by["Bandhua Mukti Morcha v. Union of India"].year == "1984"     # enriched
    assert "Indra Sawhney" in by                                           # LLM-only find
    assert "Constitution of India" in by                                   # regex find kept
    assert not any("Maneka" in (c.name or "") for c in cites)              # hallucination dropped
    assert not any("Kesavananda" in (c.name or "") for c in cites)         # invented name dropped
    assert not any(c.raw == "Reliance is also placed" for c in cites)


def test_llm_failures_never_break_extraction():
    def boom(prompt): raise TimeoutError("llm down")
    base = [c.raw for c in extract_citations(TEXT2)]
    assert [c.raw for c in extract_citations_hybrid(TEXT2, completer=boom)] == base
    assert [c.raw for c in extract_citations_hybrid(TEXT2, completer=lambda p: "not json")] == base
    assert [c.raw for c in extract_citations_hybrid(TEXT2, completer=None)] == base


def test_article_verifies_against_constitution_title():
    class Src:
        def search(self, c):
            return [SourceHit("Article 21 in Constitution of India", "https://indiankanoon.org/doc/1/", None)]
    c = extract_citations("Article 21 of the Constitution of India")[0]
    v = verify_citation(c, [Src()])
    assert v.status == "verified"
    c2 = Citation(raw="x", kind="statute", act="Constitution of India", section="99")
    assert verify_citation(c2, [Src()]).status != "verified"


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
