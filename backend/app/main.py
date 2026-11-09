"""FastAPI application entry point.

Boots the app and exposes a health endpoint. Feature routers (search, scam,
listings) get mounted here as they're built in later milestones.
"""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import lifestyle as lifestyle_router
from app.routers import search as search_router
from core.config import settings
from core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("⚡ WohnIQ: initialising pipeline…")
    try:
        if settings.demo_mode:
            from data.demo_repository import get_demo_repository

            get_demo_repository()  # load + validate fixtures now, not on first request
            print(
                f"✓  OFFLINE DEMO MODE: {settings.demo_mode_reason}. Bundled fixtures; "
                "no database, Gemini, transit or OSM calls."
            )
            from enrich.places import get_place_index
            from enrich.transit_network import get_network

            has_stops, network = get_place_index().has_stops, get_network()
            if has_stops and network is not None:
                print(
                    f"✓  Commute: route-based estimates over the VBB weekday-peak network "
                    f"({len(network.stations)} stations)."
                )
            elif has_stops:
                print(
                    "⚠  Commute: VBB network missing, so estimates use straight-line distance. "
                    "Run `make demo-stops` once while online."
                )
            else:
                print(
                    "⚠  Commute: VBB data not downloaded, so estimates only work for Kiez "
                    "names and use straight-line distance. Run `make demo-stops` once while online."
                )
        else:
            print("✓  LIVE MODE: using DATABASE_URL.")
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
    return {
        "status": "ok",
        "environment": settings.environment,
        "mode": "demo" if settings.demo_mode else "live",
    }


api_v1.include_router(search_router.router)
api_v1.include_router(lifestyle_router.router)
app.include_router(api_v1)

if settings.demo_mode:
    # Local copies of listing photos (`make demo-photos`), so the demo needs no CDN.
    from data.demo_repository import PHOTOS_DIR, PHOTOS_URL_PREFIX

    app.mount(
        PHOTOS_URL_PREFIX,
        StaticFiles(directory=PHOTOS_DIR, check_dir=False),
        name="demo-photos",
    )
