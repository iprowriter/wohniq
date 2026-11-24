"""FastAPI application entry point.

Boots the app and exposes a health endpoint. Feature routers (search, scam,
listings) get mounted here as they're built in later milestones.
"""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import berlin as berlin_router
from app.routers import lifestyle as lifestyle_router
from app.routers import neighborhoods as neighborhoods_router
from app.routers import search as search_router
from core.config import settings
from core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def _warm_listing_locations(berlin) -> None:
    """Match every listing to its address in the background (live mode: ~1 query batch per
    listing), so the first search doesn't wait. Offline it takes milliseconds anyway."""
    import threading

    from app.repository import get_repository_for_warmup
    from berlin.listings import warm_listing_locations

    def run() -> None:
        try:
            listings = get_repository_for_warmup()
            n = warm_listing_locations(berlin, listings)
            logger.info("Berlin data: matched %d listings to their addresses.", n)
        except Exception:  # noqa: BLE001 - warm-up is best effort
            logger.warning("Listing address warm-up failed", exc_info=True)

    threading.Thread(target=run, name="berlin-warmup", daemon=True).start()


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
        from berlin import get_berlin_data
        from berlin.files import BuildMissing
        from neighborhoods.bundle import get_bundle as get_neighbourhoods

        try:
            berlin = get_berlin_data()  # offline: loads the build files now (≈ 1 s)
            n_rows = len(berlin.rent_rows())
            print(f"✓  Berlin data: rent index ({n_rows} rows), addresses, stops and area data.")
            _warm_listing_locations(berlin)
        except BuildMissing:
            print(
                "⚠  Berlin data not built: rent check and Around this flat are unavailable. "
                "Run `make berlin-data` (ADR-0016)."
            )
        hoods = get_neighbourhoods()  # validate the bundle now, not on first request
        print(
            f"✓  Berlin Neighbourhoods: {len(hoods.regions)} areas, "
            f"{len(hoods.available())} metrics ({len(hoods.pending())} waiting for data)."
        )
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
    # The offline map is read with HTTP range requests (berlin.pmtiles, ADR-0019).
    expose_headers=["Content-Range", "Content-Length", "Accept-Ranges", "ETag"],
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


@api_v1.get("/status")
def status() -> dict:
    """What the header badge shows: data mode, and whether live departures are reachable."""
    from berlin.departures import departures_reachable
    from berlin.files import is_built

    live = settings.wohniq_live_departures and departures_reachable()
    return {
        "mode": "demo" if settings.demo_mode else "live",
        "berlin_data": is_built() or not settings.demo_mode,
        "map_tiles": (
            f"{MAP_URL_PREFIX}/berlin.pmtiles"
            if MAP_DIR.joinpath("berlin.pmtiles").is_file()
            else None
        ),
        "online": live,
    }


api_v1.include_router(search_router.router)
api_v1.include_router(lifestyle_router.router)
api_v1.include_router(neighborhoods_router.router)
api_v1.include_router(berlin_router.router)
app.include_router(api_v1)

# The offline base map from the Berlin data build (`make berlin-data`), read by the
# frontend with range requests. Absent on a server without the build; the frontend then
# uses NEXT_PUBLIC_MAP_TILES_URL (e.g. the file in Supabase Storage).
from berlin.files import BUILD_DIR as _BERLIN_BUILD  # noqa: E402
from berlin.files import MAP_DIR as _MAP_SUBDIR  # noqa: E402

MAP_URL_PREFIX = "/tiles"
MAP_DIR = _BERLIN_BUILD / _MAP_SUBDIR
app.mount(MAP_URL_PREFIX, StaticFiles(directory=MAP_DIR, check_dir=False), name="tiles")

if settings.demo_mode:
    # Local copies of listing photos (`make demo-photos`), so the demo needs no CDN.
    from data.demo_repository import PHOTOS_DIR, PHOTOS_URL_PREFIX

    app.mount(
        PHOTOS_URL_PREFIX,
        StaticFiles(directory=PHOTOS_DIR, check_dir=False),
        name="demo-photos",
    )
