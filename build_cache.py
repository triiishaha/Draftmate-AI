"""
Build legal_cache.json for offline demos.

Run ONCE at home with Wi-Fi and your token set:
    python3 build_cache.py demo_draft.txt

It reads every citation in the text, searches Indian Kanoon for each, and saves the
GOOD matches only. Made-up citations find nothing, so they never enter the cache and
will still come out 'unverified' on stage.

Cost: roughly 1-2 searches per citation (about Rs 0.5 each).
"""
import json
import sys

from citation_verifier import (
    IndianKanoonSource, SourceHit, extract_citations, _name_sim, Citation,
)

GOOD_MATCH = 0.55   # same bar the verifier uses for 'partially verified'


def build(text: str, source, out_path: str = "legal_cache.json") -> list[dict]:
    kept: dict[str, SourceHit] = {}
    for c in extract_citations(text):
        key = c.name if c.kind == "case" else c.act
        hits = source.search(c)
        good = [h for h in hits if _name_sim(key or "", h.title) >= GOOD_MATCH]
        print(f"{c.raw[:60]:60} -> {len(good)} good hit(s)")
        for h in good:
            kept[h.url] = h                      # dedupe by link
    data = [h.__dict__ for h in kept.values()]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(data)} entries to {out_path}")
    return data


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "demo_draft.txt"
    build(open(path, encoding="utf-8").read(), IndianKanoonSource())
