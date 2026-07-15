import logging

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database import get_db
from models import WorkoutLog, User
from schemas import WorkoutLogCreate, WorkoutLogOut, ApiResponse
from auth import get_current_user

logger = logging.getLogger("posturfit")

router = APIRouter(prefix="/api/workout-log", tags=["Workout Log"])


# ---------------------------------------------------------------------------
# GET /api/workout-log  —  Get all workout logs for current user
# ---------------------------------------------------------------------------
@router.get("", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def get_workout_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return workout history for the authenticated user, newest first.

    Response matches Flutter WorkoutLogController format:
        title, category, duration, calories, date, image
    """
    uid = current_user.id

    logs = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.user_id == uid)
        .order_by(WorkoutLog.logged_at.desc())
        .all()
    )

    data = [WorkoutLogOut.from_db(log).model_dump() for log in logs]

    return ApiResponse(
        status="success",
        message=f"{len(data)} sesi latihan ditemukan.",
        data=data,
    )


# ---------------------------------------------------------------------------
# POST /api/workout-log  —  Add a new workout log entry
# ---------------------------------------------------------------------------
@router.post("", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def add_workout_log(
    payload: WorkoutLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a completed workout session.

    Accepts Flutter WorkoutLogController fields:
        title, category, duration, calories, image
    """
    uid = current_user.id

    try:
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User tidak ditemukan.",
            )

        new_log = WorkoutLog(
            user_id=uid,
            title=payload.title,
            category=payload.category,
            duration=payload.duration,
            calories=payload.calories,
            image=payload.image,
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)

        return ApiResponse(
            status="success",
            message="Sesi latihan berhasil dicatat.",
            data=WorkoutLogOut.from_db(new_log).model_dump(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[WorkoutLog] Gagal mencatat sesi user %s: %s", uid, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mencatat sesi latihan. Silakan coba lagi.",
        )


# ---------------------------------------------------------------------------
# DELETE /api/workout-log/{log_id}  —  Delete a workout log entry
# ---------------------------------------------------------------------------
@router.delete("/{log_id}", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def delete_workout_log(
    log_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a workout log entry."""
    uid = current_user.id

    log = (
        db.query(WorkoutLog)
        .filter(WorkoutLog.id == log_id, WorkoutLog.user_id == uid)
        .first()
    )

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log tidak ditemukan.",
        )

    db.delete(log)
    db.commit()

    return ApiResponse(status="success", message="Log latihan dihapus.")
