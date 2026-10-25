"""Serves a small test page for the Legal Research UI from the same server (no CORS setup needed).

    from testpage import router as test_router
    app.include_router(test_router)

Then open  http://localhost:8000/test
"""
import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

HERE = os.path.dirname(os.path.abspath(__file__))
router = APIRouter()


@router.get("/test", include_in_schema=False)
def test_page():
    return FileResponse(os.path.join(HERE, "research_test.html"))


@router.get("/Research.css", include_in_schema=False)
def research_css():
    return FileResponse(os.path.join(HERE, "Research.css"), media_type="text/css")


# Demo of all three pages (Research, Contract Intelligence, Deadline Tracker): open http://localhost:8000/demo
DEMO = os.path.join(HERE, "demo")


@router.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(os.path.join(DEMO, "index.html"))


@router.get("/demo/app.js", include_in_schema=False)
def demo_js():
    return FileResponse(os.path.join(DEMO, "app.js"), media_type="application/javascript")


@router.get("/demo/app.css", include_in_schema=False)
def demo_css():
    return FileResponse(os.path.join(DEMO, "app.css"), media_type="text/css")
