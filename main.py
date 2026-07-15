import os
import asyncio
import logging
from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, Request
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import RedirectResponse, JSONResponse
# pyrefly: ignore [missing-import]
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from rate_limit import limiter
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
# pyrefly: ignore [missing-import]
from sqladmin import Admin
# pyrefly: ignore [missing-import]
from starlette.middleware.sessions import SessionMiddleware
# pyrefly: ignore [missing-import]
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# pyrefly: ignore [missing-import]
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("posturfit")

from database import engine, Base
from sqlalchemy import text
from admin_auth import AdminAuthBackend
from admin_change_password import router as change_password_router
from sync_service import sync_education_from_mongo
from admin_panel import (
    UserAdmin, CvAssessmentAdmin, DailyTrackerAdmin,
    DailyWorkoutPlanAdmin, WorkoutTaskAdmin,
    WorkoutLogAdmin, EducationArticleAdmin, NotificationAdmin,
    AdminUserAdmin, FcmTokenAdmin, LoginLogAdmin, NotificationPreferenceAdmin,
    admin_api_router,
)
from routers import (
    auth_router,
    cv_router,
    tracker_router,
    home_router,
    workout_log_router,
    education_router,
    notification_router,
    progress_router,
    workout_plan_router,
)

# Secret key untuk menandatangani session cookie — WAJIB ada di .env
_SESSION_SECRET = os.getenv("SESSION_SECRET")
if not _SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET belum diatur di file .env!")


# ---------------------------------------------------------------------------
# Request body size limit middleware
# ---------------------------------------------------------------------------
MAX_BODY_SIZE = 5 * 1024 * 1024  # 5MB

async def _body_size_middleware(request: Request, call_next):
    try:
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            if size > MAX_BODY_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"status": "error", "message": "Request body terlalu besar. Maksimal 5MB."},
                )
    except (ValueError, TypeError):
        pass
    return await call_next(request)


# ---------------------------------------------------------------------------
# Lifespan — create tables on startup
# ---------------------------------------------------------------------------
# Scheduler untuk sinkronisasi otomatis
_scheduler = AsyncIOScheduler()


def _run_migrations():
    """Jalankan migration untuk menyesuaikan skema database."""
    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE otp_requests MODIFY otp_code VARCHAR(64) NOT NULL"
            ))
            conn.commit()
            logger.info("[Migration] otp_requests.otp_code → VARCHAR(64)")
    except Exception as e:
        logger.warning("[Migration] otp_requests gagal: %s", e)

    try:
        with engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE password_reset_otps MODIFY otp_code VARCHAR(64) NOT NULL"
            ))
            conn.commit()
            logger.info("[Migration] password_reset_otps.otp_code → VARCHAR(64)")
    except Exception as e:
        logger.warning("[Migration] password_reset_otps gagal: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _run_migrations()

    try:
        result = await asyncio.wait_for(sync_education_from_mongo(), timeout=15.0)
        logger.info("Startup sync MongoDB->MySQL: %d baru, %d diperbarui.", result["added"], result["updated"])
    except asyncio.TimeoutError:
        logger.warning("Startup sync MongoDB timeout.")
    except Exception as e:
        logger.error("Startup sync gagal: %s", e)

    _scheduler.add_job(
        sync_education_from_mongo,
        trigger=IntervalTrigger(hours=6),
        id="sync_education",
        name="Sync Education MongoDB->MySQL",
        replace_existing=True,
    )
    _scheduler.start()

    yield

    _scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# App Initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PostureFit API",
    description=(
        "Backend API for PostureFit — a fitness application that uses "
        "Computer Vision and the SAW (Simple Additive Weighting) method "
        "for personalized workout recommendations.\n\n"
        "All response fields are aligned with Flutter frontend field names."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Rate Limiter  —  slowapi
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Middleware — order matters
# ---------------------------------------------------------------------------
app.middleware("http")(_body_size_middleware)

app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    session_cookie="pf_admin_session",
    max_age=60 * 60 * 8,               # 8 hours
    https_only=os.getenv("APP_ENV", "development") == "production",
    same_site="lax",
)

_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
]
if os.getenv("APP_ENV", "development") == "production":
    _ALLOWED_ORIGINS = [
        "https://posturefit-server.com",  # ganti dengan domain production
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Admin Dashboard  —  accessible at /admin
# ---------------------------------------------------------------------------
authentication_backend = AdminAuthBackend(secret_key=_SESSION_SECRET)
admin = Admin(
    app,
    engine,
    title="PostureFit Admin",
    templates_dir="templates",
    authentication_backend=authentication_backend,
)
admin.add_view(UserAdmin)
admin.add_view(CvAssessmentAdmin)
admin.add_view(DailyTrackerAdmin)
admin.add_view(DailyWorkoutPlanAdmin)
admin.add_view(WorkoutTaskAdmin)
admin.add_view(WorkoutLogAdmin)
admin.add_view(EducationArticleAdmin)
admin.add_view(NotificationAdmin)
admin.add_view(AdminUserAdmin)
admin.add_view(FcmTokenAdmin)
admin.add_view(LoginLogAdmin)
admin.add_view(NotificationPreferenceAdmin)

# ---------------------------------------------------------------------------
# Custom Admin Routes  —  HARUS di-include SEBELUM static mount
# ---------------------------------------------------------------------------
app.include_router(change_password_router)

# Mount static files — must come AFTER admin mount so /static doesn't shadow /admin
app.mount("/static", StaticFiles(directory="static"), name="static")



# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router.router)
app.include_router(cv_router.router)
app.include_router(tracker_router.router)
app.include_router(home_router.router)
app.include_router(workout_log_router.router)
app.include_router(education_router.router)
app.include_router(notification_router.router)
app.include_router(progress_router.router)
app.include_router(workout_plan_router.router)
app.include_router(admin_api_router)


# ---------------------------------------------------------------------------
# Root — redirect straight to the admin dashboard (login page if not authed)
# ---------------------------------------------------------------------------
@app.get("/", tags=["Root"], include_in_schema=False)
def root():
    """Redirect root URL to the admin login page."""
    return RedirectResponse(url="/admin", status_code=302)


# ---------------------------------------------------------------------------
# Health-check endpoint (explicit path so it doesn't conflict with redirect)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "success",
        "env": os.getenv("APP_ENV", "unknown"),
        "message": "PostureFit Backend Engine v2.0.0 beroperasi penuh.",
        "endpoints": {
            "auth":         "/api/auth",
            "assessment":   "/api/assessment",
            "tracker":      "/api/tracker",
            "home":         "/api/home",
            "workout_log":  "/api/workout-log",
            "education":    "/api/education",
            "notifications":"/api/notifications",
            "progress":     "/api/progress",
            "admin":        "/admin",
            "docs":         "/docs",
        },
    }

# ---------------------------------------------------------------------------
# Global Exception Handlers  —  return JSON instead of HTML
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"status": "error", "message": "Endpoint tidak ditemukan."},
    )


@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=405,
        content={"status": "error", "message": "Metode tidak diizinkan."},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("[500] %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Terjadi kesalahan internal server."},
    )


