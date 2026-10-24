from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from citation_verifier import router as verify_router
from research import router as research_router
from contract_intel import router as contract_router
from risk_radar import router as risk_router
from impact_map import router as impact_router
from doc_store import router as store_router
from testpage import router as test_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    # 3000 = Create React App / Next, 5173 = Vite. Add your frontend's port if it differs.
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(verify_router)
app.include_router(research_router)
app.include_router(contract_router)
app.include_router(risk_router)
app.include_router(impact_router)
app.include_router(store_router)
app.include_router(test_router)
