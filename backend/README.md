# DraftMate AI backend (all Python modules in one app)

One FastAPI server on **http://localhost:8000**. The React app keeps its Node server on port 5000 for the existing
`/api/draft`, `/api/research` and `/api/chat` routes; everything below is new and lives here.

## Run (Mac)

```
cd integrated-backend
python3 -m venv .venv && source .venv/bin/activate     # optional but tidy
python3 -m pip install -r requirements.txt
cp .env.example .env                                   # then fill in the keys you have
python3 -m uvicorn main:app --reload
```

* http://localhost:8000/status shows what is switched on (key set or not, never the key itself).
* http://localhost:8000/docs lists every route and lets you try them.
* http://localhost:8000/demo is a small test UI for the research and contract pages.

Nothing crashes if a key is missing. That feature explains what is missing and the rest keeps working.

## Keys (`.env`)

| Variable | Used by | Without it |
|---|---|---|
| `INDIANKANOON_API_TOKEN` | research, citation verification, law sources | falls back to `legal_cache.json`; results say what could not be checked |
| `ANTHROPIC_API_KEY` | AI summaries in research, AI-assisted citation finding | rule-based citation finding, no summaries |
| `LLM_PROVIDER`, `LLM_MODEL`, provider key | `/draft/run` (drafting engine) | **dry run**: returns the prompt it would send, no model called |
| `GEMINI_API_KEY` | AI answer in `/document/process` | context is still returned; `ai_error` explains |

Never commit `.env`.

## Routes

| Area | Route | What it does |
|---|---|---|
| Verify | `POST /verify` `{text}` | find citations in a draft and check each against a legal source |
| Research | `GET /research?q=`, `GET /research/doc/{id}`, `GET /research/answer`, `POST /research/summarize` | Indian Kanoon search, passages, evidence-first answers |
| Contracts | `POST /contract/redline`, `/compare`, `/deadlines`, `/risk`, `/impact`; `GET /contract/laws` | redlining, key-term compare, deadlines, risk radar, law-change impact |
| Store | `/store/templates`, `/store/documents`, `.../versions`, `.../diff`, `.../restore` | approved templates and append-only version history (SQLite) |
| Documents | `POST /doc/convert` (file) | PDF/DOCX/HTML/CSV to Markdown (MarkItDown if installed) |
| Context | `POST /context/optimize` `{text, query, max_tokens}` | keep only the sections that matter, within a token budget |
| Pipeline | `POST /document/process` (file, command, max_tokens, ai) | upload + command ("Explain clause 1.1") to selected context and optional AI answer |
| Voice | `POST /voice/parse` `{transcript}` | spoken or typed instruction to action and target clause |
| Drafting | `GET /draft/skills`, `POST /draft/run` | run a drafting skill; optional `verify` and `max_context_tokens` |

### How the pieces connect

`POST /draft/run` is where the modules meet:

1. If `source_text` is longer than `max_context_tokens` (default 6000), it is cut to the sections that best match the
   instruction (same wording, same order) and the response says what was left out. `revise_draft` is never cut, because it
   returns the whole document.
2. The drafting engine runs the chosen skill.
3. With `"verify": true`, the finished draft goes through the citation verifier and the response includes
   `verification` (verified / partially verified / unverified, with source links). Dry runs are not verified.

## Calling it from React

```js
const API = "http://localhost:8000";

// Draft, then verify the citations in one call
const res = await fetch(`${API}/draft/run`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    skill_id: "legal_notice",
    instruction: "Draft a legal notice for non-payment of rent",
    inputs: { sender: "...", recipient: "...", facts: "...", relief_sought: "..." },
    verify: true,
  }),
});
const { draft_md, warnings, missing_inputs, verification } = await res.json();

// Upload a document and ask about it
const form = new FormData();
form.append("file", fileInput.files[0]);
form.append("command", "Summarise this agreement");
form.append("max_tokens", "6000");
const doc = await (await fetch(`${API}/document/process`, { method: "POST", body: form })).json();
```

If `missing_inputs` is not empty, ask the user for those fields and call again. Allowed browser origins are
`localhost:3000/5173` by default; add more with `DRAFTMATE_CORS` in `.env`.

## Tests

```
python3 -m pytest -q
```
120 tests, no keys and no internet needed. (Token counts use `tiktoken` when it can download its vocabulary, otherwise a close estimate.)

## Layout

```
main.py                     the app: mounts every router, /status, CORS
routes_draft.py             /draft/*  (drafting engine + context + verification)
routes_document.py          /document/process, /voice/parse
citation_verifier.py  research.py  contract_intel.py  risk_radar.py  impact_map.py  doc_store.py
doc_convert.py  context_opt.py                         conversion and token budget
document_service.py  markdown_converter.py  structure_parser.py  context_service.py  voice_service.py
pipeline_service.py  ai_service.py                    Member 4 pipeline
drafting_engine/            skills (YAML), engine, model wrapper
drafting_demo_app.py        Streamlit demo of the engine (optional, pip install streamlit)
legal_cache.json            local authorities used when the network is unavailable
demo/ testpage.py           browser test pages
tests/
```

## Known limits

* The store has no login. Anyone who can reach the server can read it. Add auth before real use.
* The drafting engine and the document pipeline use different AI providers (`LLM_PROVIDER` vs Gemini). Both are optional and independent.
* Scanned PDFs need OCR; the converter says so instead of guessing.
* Every legal output is a prompt to review, not legal advice.
