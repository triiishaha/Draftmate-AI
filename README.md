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
