from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from citation_verifier import router as verify_router
from research import router as research_router
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
app.include_router(test_router)
