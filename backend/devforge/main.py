"""
DevForge — FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from devforge.api import analyze, auth, evidence, execute, executions, missions, report, verify
from devforge.config import settings
from devforge.db.session import DATABASE_URL, init_db

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise the database."""
    logger.info("DevForge starting — initialising database")
    init_db()
    logger.info("Database ready")
    yield
    logger.info("DevForge shutting down")


app = FastAPI(
    title="DevForge",
    description="Agentic AI Engineering Control Center",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(analyze.repositories_router)
app.include_router(auth.router)
app.include_router(missions.router)
app.include_router(evidence.router)
app.include_router(execute.router)
app.include_router(executions.router)
app.include_router(verify.router)
app.include_router(report.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Health check — returns 200 when the application is running."""
    return {"status": "ok", "app": settings.app_name, "database": "postgresql" if DATABASE_URL.startswith("postgresql") else "sqlite", "auth_configured": len(settings.auth_secret) >= 32}


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        """Serve the built React app and support browser-router refreshes."""
        requested = FRONTEND_DIST / path
        if path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")
