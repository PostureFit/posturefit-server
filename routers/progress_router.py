# pyrefly: ignore [missing-import]
from models import User
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from datetime import date, timedelta
from typing import Optional

from database import get_db
from models import DailyTracker
from schemas import ProgressResponse, ProgressDataPoint, ApiResponse
from auth import get_current_user

router = APIRouter(prefix="/api/progress", tags=["Progress Report"])


# ---------------------------------------------------------------------------
# GET /api/progress  —  Chart data for ProgressReportController
# ---------------------------------------------------------------------------
@router.get("", response_model=ProgressResponse, status_code=status.HTTP_200_OK)
def get_progress(
    period: Optional[str] = "Mingguan",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    uid   = current_user.id
    today = date.today()

    if period == "Harian":
        data = _get_daily_points(uid, db, today, days=7)
    elif period == "Bulanan":
        data = _get_monthly_points(uid, db, today, months=6)
    else:  # Mingguan (default)
        data = _get_weekly_points(uid, db, today, weeks=4)

    return ProgressResponse(period=period, data=data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_daily_points(uid: str, db: Session, today: date, days: int):
    """One data point per day for the last ``days`` days."""
    start = today - timedelta(days=days - 1)

    trackers = (
        db.query(DailyTracker)
        .filter(
            DailyTracker.user_id == uid,
            DailyTracker.tanggal >= start,
            DailyTracker.tanggal <= today,
        )
        .order_by(DailyTracker.tanggal.asc())
        .all()
    )

    tracker_map = {t.tanggal: t for t in trackers}
    points = []
    for i in range(days):
        d = start + timedelta(days=i)
        t = tracker_map.get(d)
        points.append(ProgressDataPoint(
            tanggal=d.strftime("%d %b"),
            activity_score=t.skor_aktivitas or 0 if t else 0,
            olahraga=t.olahraga or 0 if t else 0,
            nutrisi=t.nutrisi or 0 if t else 0,
            tidur=t.tidur_persen or 0 if t else 0,
        ))
    return points


def _get_weekly_points(uid: str, db: Session, today: date, weeks: int):
    """One data point per week (average of 7 days) for ``weeks`` weeks."""
    points = []
    for w in range(weeks - 1, -1, -1):
        week_end   = today - timedelta(days=w * 7)
        week_start = week_end - timedelta(days=6)

        trackers = (
            db.query(DailyTracker)
            .filter(
                DailyTracker.user_id == uid,
                DailyTracker.tanggal >= week_start,
                DailyTracker.tanggal <= week_end,
            )
            .all()
        )

        def avg(vals):
            filtered = [v for v in vals if v is not None]
            return int(sum(filtered) / len(filtered)) if filtered else 0

        points.append(ProgressDataPoint(
            tanggal=week_start.strftime("%d %b"),
            activity_score=avg([t.skor_aktivitas for t in trackers]),
            olahraga=avg([t.olahraga for t in trackers]),
            nutrisi=avg([t.nutrisi for t in trackers]),
            tidur=avg([t.tidur_persen for t in trackers]),
        ))
    return points


def _get_monthly_points(uid: str, db: Session, today: date, months: int):
    """One data point per month (average) for ``months`` months."""
    points = []
    for m in range(months - 1, -1, -1):
        # Approximate month as 30 days back
        month_end   = today - timedelta(days=m * 30)
        month_start = month_end - timedelta(days=29)

        trackers = (
            db.query(DailyTracker)
            .filter(
                DailyTracker.user_id == uid,
                DailyTracker.tanggal >= month_start,
                DailyTracker.tanggal <= month_end,
            )
            .all()
        )

        def avg(vals):
            filtered = [v for v in vals if v is not None]
            return int(sum(filtered) / len(filtered)) if filtered else 0

        points.append(ProgressDataPoint(
            tanggal=month_end.strftime("%b %Y"),
            activity_score=avg([t.skor_aktivitas for t in trackers]),
            olahraga=avg([t.olahraga for t in trackers]),
            nutrisi=avg([t.nutrisi for t in trackers]),
            tidur=avg([t.tidur_persen for t in trackers]),
        ))
    return points
