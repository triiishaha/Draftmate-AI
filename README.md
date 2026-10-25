# DraftMate AI: Legal Drafting Studio

> Upload a reference, pick a skill, generate a draft, check its citations, edit it by voice, and export it, all on one screen.

**Live demo:** https://draftmate-app-snowy.vercel.app  
**Drafter page:** https://draftmate-app-snowy.vercel.app/drafter

Built for the KodeKurrent S2 hackathon (RGIPT), Legal Drafting Studio problem statement.

> The live demo runs on free hosting. If nobody has used it for about 15 minutes, the first request can take up to a minute while the servers wake up. After that it is fast.

---

## What it does

| Problem statement requirement | What DraftMate does |
|---|---|
| **R1** Upload documents, templates, earlier drafts, references | Upload PDF, Word, PowerPoint, Excel, HTML or text. Files are converted to Markdown. Attach several at once and add saved templates |
| **R2** Text or voice instructions to generate, revise, format, review | Typed box and voice agent in the Drafter. A Format menu applies layout presets (numbering, letter, contract, plain English) |
| **R3** Adopt a reference style, keep the meaning | A reference document is analysed for tone, numbering, headings, defined terms and clause patterns, and the draft follows it. A meaning check compares amounts, dates, time limits and names before any revision is applied |
| **R4** Dynamic skills, invoked in natural language | 68 skills, each one a small JSON file. Click a chip, type `@contract-review`, or say "use contract review". Anyone can add a skill |
| **R5** Citation verification | Every case and section is checked against Indian Kanoon, an accessible public legal database, and marked **Verified**, **Needs Review** or **Not Found** in a separate panel |
| **R6** Voice agent with status and confirmation | Dictation, replace, rewrite, insert, undo, read back, export and skill activation, with a visible status line. Deleting or overwriting asks for a yes first |
| **R7** Token and context management | Markdown conversion, selective retrieval of the sections relevant to each request, a prompt-quality meter and a token-savings readout. The draft is always sent whole; only attached material is trimmed |
| **R8** Minimal UI | One drafting screen with a model picker, voice panel, skill chips and a separate verification panel |

Also included: contract risk radar and redlining, deadline extraction, a legal research page with AI summaries, and version history for saved documents.

---

## Demo flow (about three minutes)

1. Open the **Drafting Workspace** and upload a formal agreement as the **Reference document**.
2. Fill in the details (for example a rent-default legal notice) and click **Generate legal draft**. The draft follows the reference style, and missing facts become `[PLACEHOLDERS]`, not inventions.
3. In the **AI assistant**, click a skill chip, or type `@legal-notice-drafting`. Review the proposal and its meaning check, then click **Replace draft**.
4. Say **"make it more formal"** into the voice panel, then **"delete paragraph two"** to see the confirmation prompt.
5. Click **Check citations**. Each authority is marked Verified, Needs Review or Not Found.
6. Click **Export Word (.docx)** or **Export PDF**.

---

## Architecture

```
React app (Vercel)
   ├── Node / Express server (Render)   drafting prompt, research answers, chat   → Gemini
   └── Python FastAPI backend (Render)  skills, voice, style profile, conversion,
                                        token optimisation, citations, export
                                         → Gemini, Indian Kanoon
```

| Part | Folder | Port | Responsibility |
|---|---|---|---|
| React frontend | `frontend/` | 3000 | All pages and the Drafter assistant |
| Node server | `frontend/server/` | 5000 | Draft generation and "Ask DraftMate" chat, with Gemini retry, model fallback and friendly quota messages |
| Python backend | `backend/` | 8000 | Skills engine, voice commands, reference-style analysis, meaning check, document-to-Markdown, context and token optimisation, citation verification, contract tools, Word and PDF export |

### Source map

| Area | Files |
|---|---|
| Skills and routing | `backend/skills_registry.py`, `backend/skills_data/` (68 JSON skills), `backend/agent_routes.py` |
| Voice agent | `backend/voice_agent.py`, `frontend/src/components/VoiceAgent.js` |
| Reference style and meaning check | `backend/style_profile.py`, `frontend/src/components/ReferenceStyle.js` |
| Token and context management | `backend/token_optimizer.py`, `backend/context_opt.py`, `frontend/src/components/ContextTools.js` |
| Document conversion | `backend/file_to_markdown.py`, `backend/doc_convert.py` |
| Citation verification | `backend/citation_verifier.py` |
| Export | `backend/export_docx.py` (Word and PDF), `frontend/src/components/exportDraft.js` |
| Model access | `backend/llm_client.py`, `backend/ai_service.py`, `frontend/server/gemini.js` |
| Drafter UI | `frontend/src/pages/Drafter.js`, `frontend/src/components/DraftAssistant.js` |

---

## Run it locally (three terminals)

```bash
# 1. Python backend
cd backend
cp .env.example .env        # add INDIANKANOON_API_TOKEN and GEMINI_API_KEY
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --reload --port 8000

# 2. Node server
cd frontend/server
cp .env.example .env        # add GEMINI_API_KEY
npm install
npm start

# 3. React app
cd frontend
npm install --legacy-peer-deps
npm start                   # opens http://localhost:3000
```

On macOS, turn off **AirPlay Receiver** (System Settings, General, AirDrop & Handoff), or port 5000 answers 403.

Check `http://localhost:8000/status` to see which keys are loaded. Without keys the app still runs; AI answers and live case search are off.

### Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Python and Node | Drafting, revisions, chat |
| `INDIANKANOON_API_TOKEN` | Python | Citation verification and case search |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | Python (optional) | Adds Claude and GPT tiers to the model picker |
| `DRAFTMATE_CORS` | Python | Comma-separated web addresses allowed to call the backend |
| `CORS_ORIGINS` | Node | Comma-separated web addresses allowed to call the Node server |
| `REACT_APP_API_URL`, `REACT_APP_NODE_URL` | React build | Addresses of the Python and Node servers (default `localhost`) |

`.env` files are git-ignored. Never commit them.

---

## Deploying

The live demo uses three free services.

1. **Python backend on Render.** Web Service, root directory `backend`, build `pip install -r requirements.txt`, start `uvicorn main:app --host 0.0.0.0 --port $PORT`. Set `GEMINI_API_KEY`, `INDIANKANOON_API_TOKEN` and `DRAFTMATE_CORS`.
2. **Node server on Render.** Web Service, root directory `frontend/server`, build `npm install`, start `node index.js`. Set `GEMINI_API_KEY` and `CORS_ORIGINS`.
3. **React app on Vercel.** Root directory `frontend`, install command `npm install --legacy-peer-deps`. Set `REACT_APP_API_URL` and `REACT_APP_NODE_URL`, and set `CI=false` so old lint warnings do not fail the build. Make `integrated-app` the production branch.

`render.yaml` describes the two Render services.

---

## Tests

```bash
cd backend && python3 -m pip install pytest httpx && python3 -m pytest -q
```

135 tests cover skills routing, voice commands, style profile and meaning check, export, conversion, token optimisation, citations, contract tools and the document store.

---

## How a few things work

- **Skills.** A skill is a JSON file with a name, description, instructions and the inputs it needs. The router matches typed or spoken text to a skill, then the skill's instructions and your document go to the model.
- **Reference style.** Rule-based, not a model call, so it is instant and free. It measures obligation verbs (shall, will, must), numbering style, heading case and defined terms, and turns them into a style guide in the draft prompt. The model is told to copy style only and never reuse names, amounts or dates.
- **Meaning check.** Deterministic. It extracts amounts, dates, time limits and names from the old and new text and lists anything missing or new, so a "more formal" rewrite cannot quietly change a deadline.
- **Citation status.** **Verified** means the authority exists under that name and year in a legal source. **Needs Review** is a partial match. **Not Found** means no matching authority, so do not rely on it. It does not confirm what a judgment says.
- **Token control.** Documents are converted to Markdown, split into sections and ranked against your request. Only the relevant sections go to the model, within a budget you choose. The tool shows how many tokens were saved.

---

## Limits and notes

- AI output is general information, not legal advice. A qualified lawyer must review every draft and every citation.
- On the free tier, saved templates and uploads are lost when a server restarts.
- Gemini's free quota is shared across a key. When it runs out, the app shows a clear message instead of retrying.
- Secrets live only in environment settings and `.env` files.

## Team

Built by the DraftMate AI team for KodeKurrent S2, RGIPT.
