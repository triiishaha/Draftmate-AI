from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from citation_verifier import router as verify_router
from research import router as research_router
from testpage import router as test_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(verify_router)
app.include_router(research_router)
app.include_router(test_router)