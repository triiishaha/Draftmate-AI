# Citation Verification Module

Checks every case and statute cited in a draft against Indian Kanoon and labels each one
**verified / partially_verified / unverified**, with a source link. It never invents an authority.
Human review stays central: "verified" means the authority exists under that name and year,
not that it supports the point the draft makes.

## Files

| File | Purpose |
|---|---|
| `citation_verifier.py` | The module (extraction, lookup, scoring, suggestions, FastAPI router) |
| `test_citation_verifier.py` | 14 offline tests (no token or internet needed) |
| `build_cache.py` | One-off script that builds `legal_cache.json` for offline demos |
| `demo_draft.txt` | Demo legal notice: 6 real cases, 2 statutes, 1 wrong year, 1 invented case |
| `legal_cache.json` | Saved Indian Kanoon results for the demo draft |
| `research.py` | `GET /research` search route (real Indian Kanoon results only) |
| `test_research.py` | 5 offline tests for the search route |
| `Research.js`, `Research.css` | React Legal Research page (search, results, citation checker) |
| `contract_intel.py`, `test_contract_intel.py` | Redline, compare and deadline routes with 12 tests |
| `ContractIntelligence.js/.css`, `Productivity.js/.css` | React pages for Member 3's module |
| `demo/` | Prebuilt bundle of all three pages, served at `/demo` |

## Setup

```
pip3 install requests pytest fastapi uvicorn
export INDIANKANOON_API_TOKEN=<token>      # backend only, NEVER in frontend or git
python3 -m pytest -q test_citation_verifier.py     # expect: 40 passed
```

Optional LLM pass (finds citations the regex misses): set `ANTHROPIC_API_KEY`, or pass your own
`completer=` function (prompt in, text out). Without it everything still works.

## Backend: mount the route

```python
from citation_verifier import router
app.include_router(router)
```

Run the server from the folder that contains `legal_cache.json`.

## API

`POST /verify`

Request:
```json
{ "text": "See Vishaka v. State of Rajasthan, AIR 1999 SC 3011." }
```

Response (one entry in `items` per citation found):
```json
{
  "summary": { "verified": 0, "partially_verified": 1, "unverified": 0 },
  "items": [
    {
      "citation": {
        "raw": "Vishaka v. State of Rajasthan, AIR 1999 SC 3011",
        "kind": "case",
        "name": "Vishaka v. State of Rajasthan",
        "year": "1999",
        "reporter": "AIR",
        "court": "SC",
        "section": null,
        "act": null,
        "span": [4, 51]
      },
      "status": "partially_verified",
      "score": 0.7,
      "reasons": [
        "name similarity 0.95 with 'Vishaka & Ors vs State Of Rajasthan & Ors on 13 August, 1997'",
        "year mismatch: draft says 1999, source says 1997"
      ],
      "source": {
        "title": "Vishaka & Ors vs State Of Rajasthan & Ors on 13 August, 1997",
        "url": "https://indiankanoon.org/doc/1031794/",
        "year": "1997",
        "court": "Supreme Court of India",
        "snippet": ""
      },
      "suggestion": {
        "message": "The case exists, but the source dates it 1997, not 1999. Closest authority: ...",
        "replace_with": "Vishaka v. State of Rajasthan, AIR 1997 SC 3011",
        "source_url": "https://indiankanoon.org/doc/1031794/"
      }
    }
  ]
}
```

### Field notes

| Field | Meaning |
|---|---|
| `status` | `verified` (score 0.85+), `partially_verified` (0.55 to 0.85), `unverified` (below 0.55 or nothing found) |
| `score` | 0 to 1 confidence in the match |
| `reasons` | Plain-English list of why. Show it when the user clicks an item |
| `source` | Closest real authority and link. `null` when unverified |
| `citation.span` | `[start, end]` character positions in the submitted text, for highlighting |
| `suggestion` | `null` unless partially verified. See below |
| `citation.kind` | `case` or `statute` (Acts, Codes, Articles of the Constitution) |

## Frontend guidance

- **Colours:** verified = green, partially_verified = amber, unverified = red.
- **Highlight** each citation in the draft using `citation.span`.
- **Review panel:** list the items. On click show `reasons`, the `source.url` link and `suggestion.message`.
- **Apply fix button:** show only when `suggestion.replace_with` is not null. It replaces the text at
  `citation.span` with `replace_with`. It fixes the year only, so keep the message telling the user to
  check the reporter reference. **Call `/verify` again after applying**, because later spans shift.
- **Unverified:** show a clear warning, for example "No matching authority found. Do not rely on it."
- Call `/verify` from a **Verify button**, not on every keystroke (each call may cost money and takes seconds).

## Demo checklist

1. Paste `demo_draft.txt` into the draft box and click Verify.
2. Expected: 7 verified, 1 partially verified (Vishaka, wrong year, with Apply fix), 1 unverified (invented case).
3. Works offline from `legal_cache.json` for the demo citations; unknown citations fall back to the live API.
4. To change the demo draft: edit `demo_draft.txt`, then run `python3 -W ignore build_cache.py demo_draft.txt`
   (needs the token; costs a few rupees) and commit the new `legal_cache.json`.

## How it works (for judges)

1. **Extract:** regex finds cases (with or without reporter citations), Acts/sections and Constitution articles.
   An optional LLM pass finds the rest. The LLM only finds citations. Anything it reports must quote the draft
   word for word, or it is dropped.
2. **Look up:** local cache first, then the Indian Kanoon API (`title:` filter for cases, `section/article N` for laws).
3. **Score:** matches on the distinctive words of the case name, then checks year (case) or section (statute).
   Generic words ("Union", "India") and initials never count as a match on their own.
4. **Label and explain:** every status comes with reasons and a source link. Network failure means unverified,
   never a false pass.

## Known limits

- Verified means the authority exists, not that it supports the draft's argument. A lawyer must review.
- Statute checks confirm the Act and the section number appear in the source title, not the section text.
- Regex plus the optional LLM pass can still miss unusual citation formats.
- Coverage is limited to what Indian Kanoon holds.

## Legal Research page (search)

Backend (`main.py`):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from citation_verifier import router as verify_router
from research import router as research_router

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(verify_router)
app.include_router(research_router)
```

`GET /research?q=breach of contract&type=all|supremecourt|laws&page=0` returns
`{query, count, results:[{title, url, court, year, snippet, kind}], origin, note}`.
`origin` is `indiankanoon` (live) or `cache` (offline demo). Nothing is AI-generated:
`snippet` is the extract Indian Kanoon returned.

Frontend: copy `Research.js` and `Research.css` into `src/`, route to `<Research />`.
Edit the `API` constant at the top of `Research.js` if the backend is not on `http://localhost:8000`. In a Vite project, rename the file to `Research.jsx`.
The page also has a "Check a citation" box that calls `/verify`. Status wording in the UI:
verified = Verified, partially_verified = Needs Review, unverified = Not Found.

### Research API routes

| Route | What it returns |
|---|---|
| `GET /research?q=&type=all\|supremecourt\|laws&page=0` | Search results: `title, url, court, year, snippet, kind`, plus `has_more` |
| `GET /research/doc/{doc_id}?q=` | The passages of one document that match `q` (Indian Kanoon `docfragment`): `{ok, title, url, passages[]}` |
| `GET /research/answer?q=` | Evidence-first summary: `{answer:[{text, sources:[n]}], sources[], note}` |

`/research/answer` rules: the model sees only the extracts, every sentence must cite `[n]` of a real source,
and any sentence without a valid citation is dropped. If the AI key is missing or fails, it returns the sources
with a note and no summary. It costs one search call plus one AI call, so trigger it from a button.
`doc_id` must be digits only. Test page: `http://localhost:8000/test` (add `testpage` router in `main.py`).

### Short summaries (one per result)

`POST /research/summarize` with `{"query": "...", "results": [{"url","title","snippet"}, ...]}` (send back exactly what
`/research` returned). Returns `{"summaries": {"<source url>": "one sentence"}, "note": ...}`.

- One AI call for the whole page. The AI sees only the extracts, never the open web.
- A summary is kept only if it passes a grounding check: every number in it must appear in the extract and at
  least 70% of its meaningful words must appear there. Anything else is dropped and the card keeps its extract.
- Summaries are keyed by the source link, so the link always travels with the text. Only `https://indiankanoon.org/doc/<digits>/` links are accepted.
- No AI key or AI failure: the cards still show extracts and links. Nothing breaks.
- Needs `ANTHROPIC_API_KEY` in the terminal that runs uvicorn. Cost: one AI call per search page, no extra Indian Kanoon call.

### Citation status UI (Research page)

The "Check a citation" panel calls `POST /verify` and shows:
- a status summary: green **Verified**, amber **Needs Review** (`partially_verified`), red **Not Found** (`unverified`)
- **Your draft, checked**: the pasted text with every citation highlighted by status using `citation.span`
  (click a highlight to jump to its card)
- one card per citation with the reasons, the source link and the warning for Not Found
- **Apply fix** (only when `suggestion.replace_with` exists): replaces the text at the span, then calls `/verify` again.
  If the text at the span no longer matches `citation.raw` it does not edit, it just re-checks.
- if the user edits the draft after a check, a note asks them to re-check and Apply fix is disabled

## Contract Intelligence (Member 3 core): redline, compare, deadlines

`contract_intel.py` is plain text analysis. **No AI model is used**, so nothing can be invented, and every
result quotes the contract's own words. Mount: `app.include_router(contract_router)` (already in `main.py`).

| Route (POST, JSON) | Input | Returns |
|---|---|---|
| `/contract/redline` | `{old, new}` | `summary` + `changes[]`: `kind` (added / removed / modified / unchanged), `segments[]` (word diff: equal / delete / insert), `topics`, `details` ("Notice period: 30 days → 60 days"), `review` |
| `/contract/compare` | `{a, b}` | `rows[]`: `topic`, `status` (same / changed / only_a / only_b), `a` and `b` with `value` and `quote`, `review` |
| `/contract/deadlines` | `{text, start_date?}` | `items[]`: `type`, `party`, `text` (source sentence), `date`, `days_left`, `status`, `relative`, `recurring`, `is_obligation` |

Rules worth knowing:
- `review: true` marks a change to money, notice, termination, non-compete, penalty, liability or governing law. It is a
  prompt to look closely, not a legal opinion.
- Deadline `status`: overdue, due_soon (30 days), upcoming, needs_start_date, event_based, notice_period, recurring, undated.
  "30 days' notice" is a **notice period**, never a due date. "Within 15 days of joining" is dated from the optional
  effective date. "Within 10 days of receipt of invoice" is **event_based** and never dated.
- Numeric dates are read as DD/MM/YYYY. Impossible dates (31/02/2026) are ignored. Input is capped at 200,000 characters.
- Not built yet: Risk Radar, Legal Change Impact Map, Templates & Version History.

Frontend files: `ContractIntelligence.js/.css` (Smart Redline + Compare key terms) and `Productivity.js/.css`
(Deadline & Obligation Tracker with Done checkboxes saved in the browser, and a calendar `.ics` download).
They use the same one-line `API` constant as `Research.js`.

### Demo of all three pages (no React setup)
Keep the `demo/` folder next to `main.py` (it holds `app.js`, `app.css`, `index.html`) and open
`http://localhost:8000/demo`. It is a prebuilt bundle of the real components, not a copy. If you change a component,
rebuild with esbuild: `esbuild demo/entry.js --bundle --minify --loader:.js=jsx --define:process.env.NODE_ENV='"production"' --outfile=demo/app.js`
(needs `npm i react react-dom esbuild`).

## Member 3 additions: Risk Radar, Law change impact, Templates and Version history

New files: `risk_radar.py`, `impact_map.py`, `doc_store.py` (+ tests). `main.py` already includes their routers.

| Route | What it does |
|---|---|
| POST `/contract/risk` `{text}` | Risk score, six-axis radar, findings with quotes, why, what to ask for, Indian-law pointers |
| GET `/contract/laws` | Laws the impact map knows |
| POST `/contract/impact` `{text, law, change?}` | Which clauses deal with the subjects a law covers, plus real sources from Indian Kanoon |
| GET/POST `/store/templates`, GET/DELETE `/store/templates/{id}` | Approved templates (name clash returns 409 unless `replace: true`) |
| GET/POST `/store/documents`, GET/POST `/store/documents/{id}/versions`, GET `.../versions/{n}`, GET `.../diff?a=&b=`, POST `.../restore` | Append-only version history; restore creates a new version |

Notes
- The store is SQLite in `draftmate_store.db` next to `main.py` (change with env `DRAFTMATE_DB`). There is no login in this demo, so do not expose it publicly.
- The impact map never says a law changed. You name the law; it shows matching clauses and sources.
- React: `ContractIntelligence.js` has Risk Radar and Law change impact tabs; `Productivity.js` has Deadlines, Templates and Version history tabs (it imports `RedlineResult` from `ContractIntelligence.js`, so give your frontend teammate both files and both CSS files).
- Everything is rule-based. No AI key is needed for any of this.
