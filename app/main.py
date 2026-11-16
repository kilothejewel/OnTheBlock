from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
from app.core.http_client import close_http_client, open_http_client
from app.core.observability import REQUEST_ID_HEADER, RequestContextMiddleware, configure_error_tracking, configure_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers.auth import router as auth_router
from app.routers.cities import router as cities_router
from app.routers.hotspots import router as hotspots_router
from app.routers.itineraries import router as itineraries_router
from app.routers.places import router as places_router

configure_logging(settings.LOG_FORMAT, settings.LOG_LEVEL)
configure_error_tracking(settings.SENTRY_DSN, settings.SENTRY_ENVIRONMENT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only the shared HTTP client opens and closes here. No schema work at
    # startup: migrations own it (python -m app.migrate; see render.yaml).
    open_http_client()
    yield
    await close_http_client()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Rate limiting: a global default limit via SlowAPIMiddleware, stricter per-route
# limits declared with @limiter.limit(...) on the expensive endpoints.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configure CORS. Origins are read from the OTB_FRONTEND_ORIGINS setting
# (comma-separated) plus OTB_FRONTEND_ORIGIN_REGEX (any local port by default).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_origin_regex=settings.FRONTEND_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],  # so the web app can show it in error reports
)

# Added last, so it runs first: every response, including errors and CORS
# preflights, carries X-Request-ID, and every log line has the request ID.
app.add_middleware(RequestContextMiddleware)

# Include API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(cities_router, prefix=settings.API_V1_STR)
app.include_router(hotspots_router, prefix=settings.API_V1_STR)
app.include_router(itineraries_router, prefix=settings.API_V1_STR)
app.include_router(places_router, prefix=settings.API_V1_STR)

@app.get("/")
def read_root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }

@app.get("/health")
@limiter.exempt
def health_check():
    return {"status": "healthy"}


