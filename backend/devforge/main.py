"""
DevForge — FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devforge.api import analyze, auth, evidence, execute, executions, missions, report, verify
from devforge.config import settings
from devforge.db.session import init_db

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


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

# CORS — allow the Vite dev server (port 5173) and any localhost origin
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

# Register API routers
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
    return {"status": "ok", "app": settings.app_name}
