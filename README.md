# DraftMate AI: Legal Drafting Studio

One app, three parts:

| Part | Folder | Port | What it does |
|---|---|---|---|
| React frontend | `frontend/` | 3000 | All pages: Drafter, Understand Mode, Case Law & Citations, Contract Intelligence, Productivity |
| Node server | `frontend/server/` | 5000 | Drafter and the "Ask DraftMate" chat (Gemini) |
| Python backend | `backend/` | 8000 | Citation verification, document-to-Markdown, context and token optimisation, contract risk and redline, deadlines, templates and version history, drafting-skills engine |

## Run it (three terminals)

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

On macOS, turn off **AirPlay Receiver** (System Settings, General, AirDrop & Handoff) or port 5000 will answer 403.

Check `http://localhost:8000/status` to see which keys are loaded. Without keys everything still runs; AI answers and live case search are off.

## Tests

```bash
cd backend && python3 -m pip install pytest httpx && python3 -m pytest -q
```

## Notes

- Citation status means: **Verified** = the authority exists under that name and year in a legal source; **Needs Review** = a partial match; **Not Found** = no matching authority, do not rely on it. It does not confirm what a judgment says.
- Secrets live only in `.env` files, which are git-ignored. Never commit them.
- AI output is general information, not legal advice.

## Skills, voice and model picker (Drafter)

The Drafter has an **AI assistant** panel under the draft: skill chips (68 skills, full list at `/skills-library`),
a model picker, an instruction box and a voice agent. Voice commands include `use contract review`, `replace X with Y`,
`make it more formal`, `delete paragraph 2` (asks for confirmation), `undo`, `read it back`, `export as Word/PDF`.
AI revisions are shown as a proposal and only replace the draft after you confirm. API: `/api/skills`, `/api/models`,
`/api/voice/*`, `/api/convert` (see `/docs`). Gemini is the default model; Claude/GPT tiers appear if their keys are set.

## Reference-style adaptation

In the Drafter, upload a **Reference document** (an earlier draft or template). `POST /style/profile` measures its tone,
obligation verb (shall/will), numbering, heading case, defined terms and opening/closing phrases, and builds a style guide
that is added to the draft prompt and to AI revisions. Only style is copied, never facts. No model call is used for the analysis.

## Export

`POST /export/docx` builds a real Word file (python-docx) from the draft: Times New Roman 12 pt, centred bold headings, justified paragraphs.
The Drafter's **Export Word (.docx)** button uses it (falls back to a Word-compatible `.doc` if the backend is down). PDF uses the browser's Save as PDF.
