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
