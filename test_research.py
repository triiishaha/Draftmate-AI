from citation_verifier import SourceHit, LocalCacheSource
from research import research, _build_query


class FakeKanoon:
    token = "x"
    BASE = "https://api.indiankanoon.org"
    seen = []

    def _call(self, query):
        self.seen.append(query)
        return [{"title": "<b>Maneka</b> Gandhi vs Union Of India on 25 January, 1978",
                 "tid": 1766147, "headline": "procedure must be <b>fair</b> &amp; just",
                 "docsource": "Supreme Court of India"},
                {"title": "Section 138 in The Negotiable Instruments Act, 1881",
                 "tid": 5, "headline": "", "docsource": "Central Act"}]

    @staticmethod
    def _to_hit(d):
        from citation_verifier import IndianKanoonSource
        return IndianKanoonSource._to_hit(d)


class NoToken(FakeKanoon):
    token = None


def _cache(tmp_path):
    p = tmp_path / "c.json"
    import json
    p.write_text(json.dumps([{"title": "Vishaka & Ors vs State Of Rajasthan & Ors on 13 August, 1997",
                              "url": "https://indiankanoon.org/doc/1031794/", "year": "1997",
                              "court": "Supreme Court of India", "snippet": ""}]))
    return LocalCacheSource(str(p))


def test_live_results_have_links_and_kinds(tmp_path):
    r = research("personal liberty", source=FakeKanoon(), cache=_cache(tmp_path))
    assert r["origin"] == "indiankanoon" and r["count"] == 2
    a, b = r["results"]
    assert a["url"] == "https://indiankanoon.org/doc/1766147/" and a["kind"] == "judgment"
    assert "<b>" not in a["title"] and a["snippet"] == "procedure must be fair & just"
    assert b["kind"] == "law"


def test_filter_and_query_building():
    assert _build_query("breach of contract", "supremecourt") == "breach of contract doctypes: supremecourt"
    assert _build_query("  breach   of contract ", "all") == "breach of contract"
    assert _build_query("x" * 500, "all") == "x" * 200


def test_offline_fallback_uses_cache_only(tmp_path):
    r = research("vishaka rajasthan", source=NoToken(), cache=_cache(tmp_path))
    assert r["origin"] == "cache" and r["count"] == 1 and "offline" in r["note"].lower()


def test_nothing_found_is_honest(tmp_path):
    r = research("zzzz qqqq", source=NoToken(), cache=_cache(tmp_path))
    assert r["count"] == 0 and r["results"] == [] and r["note"]


def test_short_query_rejected(tmp_path):
    assert research("a", source=FakeKanoon(), cache=_cache(tmp_path))["count"] == 0


def test_snippet_whitespace_collapsed_and_constitution_is_law():
    from research import _card
    c = _card(SourceHit("Constitution of India", "u", None, "Constitution and Amendments", "a \n\n  b\n"))
    assert c["snippet"] == "a b" and c["kind"] == "law"


def test_title_matches_ranked_first():
    from research import _rank
    hs = [SourceHit("Article 21 in Constitution of India", "a"),
          SourceHit("Vishaka & Ors vs State Of Rajasthan & Ors on 13 August, 1997", "b")]
    assert _rank("vishaka rajasthan", hs)[0].url == "b"


def test_court_label_cleaned_and_has_more(tmp_path):
    class K(FakeKanoon):
        def _call(self, q):
            return [{"title": "Section 73 in The Indian Contract Act, 1872", "tid": i,
                     "headline": "", "docsource": "Union of India - Section"} for i in range(10)]
    r = research("breach of contract", source=K(), cache=_cache(tmp_path))
    assert r["results"][0]["court"] == "Central Act" and r["has_more"] is True
    off = research("vishaka rajasthan", source=NoToken(), cache=_cache(tmp_path))
    assert off["has_more"] is False
    assert research("vishaka rajasthan", page=1, source=NoToken(), cache=_cache(tmp_path))["count"] == 0


# ---------------- passage + evidence-first answer ----------------
from research import answer, fragment


def test_fragment_rejects_bad_id_and_no_token():
    assert fragment("../etc", "x", source=NoToken())["ok"] is False
    r = fragment("1031794", "x", source=NoToken())
    assert r["ok"] is False and r["url"].endswith("/1031794/")


def _fk():
    class K(FakeKanoon):
        def _call(self, q):
            return [{"title": "Section 73 in The Indian Contract Act, 1872", "tid": 1,
                     "headline": "damage caused by breach of contract", "docsource": "Union of India - Section"},
                    {"title": "Section 74 in The Indian Contract Act, 1872", "tid": 2,
                     "headline": "penalty stipulated for breach", "docsource": "Union of India - Section"}]
    return K()


def test_answer_keeps_only_cited_sentences(tmp_path):
    def llm(prompt):
        assert "untrusted" in prompt and "[1] Section 73" in prompt
        return ("A party who suffers by breach can receive compensation [1]. "
                "The Supreme Court always awards double damages. "         # no citation -> dropped
                "Penalty clauses are limited [2]. "
                "Invented claim [9].")                                      # bad source number -> dropped
    r = answer("breach of contract", completer=llm, source=_fk(), cache=_cache(tmp_path))
    assert [a["sources"] for a in r["answer"]] == [[1], [2]]
    assert all("[" not in a["text"] and "double" not in a["text"] for a in r["answer"])
    assert len(r["sources"]) == 2


def test_answer_degrades_safely(tmp_path):
    r = answer("breach of contract", completer=None, source=_fk(), cache=_cache(tmp_path))
    assert r["answer"] == [] and r["sources"] and r["note"]
    def boom(p): raise TimeoutError()
    assert answer("breach of contract", completer=boom, source=_fk(), cache=_cache(tmp_path))["answer"] == []
    assert answer("breach of contract", completer=lambda p: "INSUFFICIENT", source=_fk(), cache=_cache(tmp_path))["answer"] == []
    assert answer("zzzz qqqq", completer=lambda p: "x [1].", source=NoToken(), cache=_cache(tmp_path))["answer"] == []


# ---------------- per-result summaries ----------------
from research import summarize_results, _grounded

EX = "damage caused by breach of contract. When a contract has been broken, the party who suffers by such breach is entitled to receive compensation"
ITEMS = [{"url": "https://indiankanoon.org/doc/111/", "title": "Section 73", "snippet": EX},
         {"url": "https://indiankanoon.org/doc/222/", "title": "Section 74", "snippet": "penalty stipulated for breach of contract where a sum is named in the contract as the amount"},
         {"url": "https://evil.example/doc/1/", "title": "x", "snippet": EX},
         {"url": "https://indiankanoon.org/doc/333/", "title": "short", "snippet": "tiny"}]


def test_grounding_check():
    assert _grounded("A party who suffers by breach of contract can receive compensation.", EX)
    assert not _grounded("The Supreme Court awarded Rs 50 lakh in 1999.", EX)          # invented number
    assert not _grounded("Tenants must vacate premises after eviction notices.", EX)   # invented content
    assert not _grounded("x" * 400, EX)


def test_summaries_keep_only_grounded_and_keyed_by_link():
    import json
    def llm(prompt):
        assert "untrusted" in prompt and "evil.example" not in prompt and "tiny" not in prompt
        return json.dumps([
            {"id": 1, "summary": "A party who suffers by breach of contract can receive compensation."},
            {"id": 2, "summary": "The Supreme Court awarded Rs 50 lakh in 1999 for every penalty clause."},  # invented -> dropped
            {"id": 9, "summary": "bad id"}])
    r = summarize_results("breach", ITEMS, completer=llm)
    assert list(r["summaries"]) == ["https://indiankanoon.org/doc/111/"]


def test_summaries_degrade_safely():
    assert summarize_results("q", ITEMS, completer=None)["summaries"] == {}
    def boom(p): raise TimeoutError()
    assert summarize_results("q", ITEMS, completer=boom)["summaries"] == {}
    assert summarize_results("q", ITEMS, completer=lambda p: "not json")["summaries"] == {}
    assert summarize_results("q", [], completer=lambda p: "[]")["note"]
    assert summarize_results("q", ITEMS * 5, completer=lambda p: "[]")["summaries"] == {}
