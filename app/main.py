from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
from app.core.database import engine
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.models import Base
from app.routers.auth import router as auth_router
from app.routers.hotspots import router as hotspots_router
from app.routers.itineraries import router as itineraries_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Rate limiting: a global default limit via SlowAPIMiddleware, stricter per-route
# limits declared with @limiter.limit(...) on the expensive endpoints.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configure CORS. Origins are read from the OTB_FRONTEND_ORIGINS setting
# (comma-separated); defaults to the local Vite dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(hotspots_router, prefix=settings.API_V1_STR)
app.include_router(itineraries_router, prefix=settings.API_V1_STR)

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


