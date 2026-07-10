"""
tracker_router.py — /api/tracker endpoints.

Create or update daily activity tracking.
Response fields aligned with Flutter ActivityEntity:
    olahraga, nutrisi, tidur, sleep_duration,
    hydration_current, hydration_target, activity_score
"""

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from datetime import date

from database import get_db
from models import DailyTracker, User
from schemas import DailyTrackerUpdate, DailyTrackerOut, ApiResponse
from auth import get_current_user

router = APIRouter(prefix="/api/tracker", tags=["Daily Tracking"])


# ---------------------------------------------------------------------------
# POST /api/tracker/daily  —  Upsert today's tracker data
# ---------------------------------------------------------------------------
@router.post("/daily", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def update_daily_tracker(
    payload: DailyTrackerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a daily tracker entry.

    Accepts Flutter ActivityEntity fields:
        hidrasi_ml          → hydrationCurrent
        hydration_target_ml → hydrationTarget
        tidur_jam           → sleepDuration
        olahraga            → olahraga % (0-100)
        nutrisi             → nutrisi % (0-100)
        tidur_persen        → tidur % (0-100)
        skor_aktivitas      → activityScore (0-100)

    - If a record for the given ``tanggal`` already exists → partial update.
    - If no record exists → create a new one.
    """
    uid = current_user.id

    # Verify user exists
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User tidak ditemukan.",
        )

    # Upsert tracker
    tracker = (
        db.query(DailyTracker)
        .filter(
            DailyTracker.user_id == uid,
            DailyTracker.tanggal == payload.tanggal,
        )
        .first()
    )

    if tracker is None:
        tracker = DailyTracker(user_id=uid, tanggal=payload.tanggal)
        db.add(tracker)

    # Partial update — only set provided fields
    if payload.hidrasi_ml is not None:
        tracker.hidrasi_ml = payload.hidrasi_ml
    if payload.hydration_target_ml is not None:
        tracker.hydration_target_ml = payload.hydration_target_ml
    if payload.tidur_jam is not None:
        tracker.tidur_jam = payload.tidur_jam
    if payload.olahraga is not None:
        tracker.olahraga = payload.olahraga
    if payload.nutrisi is not None:
        tracker.nutrisi = payload.nutrisi
    if payload.tidur_persen is not None:
        tracker.tidur_persen = payload.tidur_persen
    if payload.skor_aktivitas is not None:
        tracker.skor_aktivitas = payload.skor_aktivitas

    db.commit()
    db.refresh(tracker)

    return ApiResponse(
        status="success",
        message="Data harian berhasil diperbarui.",
        data=DailyTrackerOut.from_db(tracker).model_dump(),
    )


# ---------------------------------------------------------------------------
# GET /api/tracker/daily  —  Get tracker for a specific date (default today)
# ---------------------------------------------------------------------------
@router.get("/daily", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def get_daily_tracker(
    tanggal: date = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch the daily tracker entry for the given date.

    If ``tanggal`` is omitted, defaults to today.
    Response matches Flutter ActivityEntity fields.
    """
    uid         = current_user.id
    target_date = tanggal or date.today()

    tracker = (
        db.query(DailyTracker)
        .filter(
            DailyTracker.user_id == uid,
            DailyTracker.tanggal == target_date,
        )
        .first()
    )

    return ApiResponse(
        status="success",
        message="Data harian ditemukan." if tracker else "Belum ada data untuk tanggal ini.",
        data=DailyTrackerOut.from_db(tracker, target_date).model_dump(),
    )


# ---------------------------------------------------------------------------
# GET /api/tracker/weekly  —  Get last 7 days of tracking data
# ---------------------------------------------------------------------------
@router.get("/weekly", status_code=status.HTTP_200_OK)
def get_weekly_tracker(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the last 7 daily tracker entries for the current user.

    Response list items match Flutter ActivityEntity fields.
    """
    from datetime import timedelta

    uid      = current_user.id
    today    = date.today()
    week_ago = today - timedelta(days=6)

    trackers = (
        db.query(DailyTracker)
        .filter(
            DailyTracker.user_id == uid,
            DailyTracker.tanggal >= week_ago,
            DailyTracker.tanggal <= today,
        )
        .order_by(DailyTracker.tanggal.asc())
        .all()
    )

    data = [DailyTrackerOut.from_db(t).model_dump() for t in trackers]

    return ApiResponse(status="success", message="", data=data)