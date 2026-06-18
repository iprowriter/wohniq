"""FastAPI application entry point.

Boots the app and exposes a health endpoint. Feature routers (search, scam,
listings) get mounted here as they're built in later milestones.
"""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import search as search_router
from core.config import settings
from core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("⚡ WohnIQ: initialising pipeline…")
    try:
        print("✓  Backend ready.")
    except Exception as exc:
        print(f"⚠  Backend failed to initialise properly: {exc}")
    yield


app = FastAPI(
    title="WohnIQ API",
    description="WohnIQ is an AI-assisted apartment-search platform for Berlin.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the Next.js dev server (and the deployed frontend) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Feature routers (search, scam, listings) get included here as they're built.
api_v1 = APIRouter(prefix="/api/v1")


@api_v1.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Used by Railway and the Supabase keep-alive cron."""
    return {"status": "ok", "environment": settings.environment}


api_v1.include_router(search_router.router)
app.include_router(api_v1)
