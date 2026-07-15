# pyrefly: ignore [missing-import]
import logging
from fastapi import APIRouter, Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database import get_db
from models import Notification, User, NotificationPreference
from schemas import NotificationOut, ApiResponse
from auth import get_current_user
from fcm_service import send_push_to_user

logger = logging.getLogger("posturfit")

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# ---------------------------------------------------------------------------
# GET /api/notifications  —  Get all notifications for current user
# ---------------------------------------------------------------------------
@router.get("", status_code=status.HTTP_200_OK)
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    uid = current_user.id

    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == uid)
        .order_by(Notification.created_at.desc())
        .all()
    )

    data = [NotificationOut.from_db(n).model_dump() for n in notifications]

    # If no notifications in DB, return welcome notification as seed
    if not data:
        data = _get_seed_notifications()

    unread_count = sum(1 for n in data if not n.get("is_read", False))

    return ApiResponse(
        status="success",
        message="",
        data={
            "unread_count": unread_count,
            "notifications": data,
        },
    )


# ---------------------------------------------------------------------------
# PATCH /api/notifications/{notif_id}/read  —  Mark as read
# ---------------------------------------------------------------------------
@router.patch("/{notif_id}/read", status_code=status.HTTP_200_OK)
def mark_as_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    uid = current_user.id

    notif = (
        db.query(Notification)
        .filter(Notification.id == notif_id, Notification.user_id == uid)
        .first()
    )

    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notifikasi tidak ditemukan.",
        )

    notif.is_read = True
    db.commit()

    return ApiResponse(status="success", message="Notifikasi ditandai sudah dibaca.")


# ---------------------------------------------------------------------------
# PATCH /api/notifications/read-all  —  Mark all as read
# ---------------------------------------------------------------------------
@router.patch("/read-all", status_code=status.HTTP_200_OK)
def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications for the current user as read."""
    uid = current_user.id

    db.query(Notification).filter(
        Notification.user_id == uid,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()

    return ApiResponse(status="success", message="Semua notifikasi telah dibaca.")


# ---------------------------------------------------------------------------
# POST /api/notifications  —  Create a notification (internal/admin use)
# ---------------------------------------------------------------------------
@router.post("", status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a notification for the current user."""
    uid = current_user.id

    notif = Notification(
        user_id=uid,
        title=payload.get("title", ""),
        message=payload.get("message", ""),
        type=payload.get("type", "system"),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    try:
        send_push_to_user(db, uid, notif.title, notif.message)
    except Exception as e:
        logger.error("Gagal kirim push notifikasi ke user %s: %s", uid, e)

    return ApiResponse(
        status="success",
        message="Notifikasi berhasil dibuat.",
        data=NotificationOut.from_db(notif).model_dump(),
    )


# ---------------------------------------------------------------------------
# GET /api/notifications/preferences  —  Get user notification preferences
# ---------------------------------------------------------------------------
@router.get("/preferences", status_code=status.HTTP_200_OK)
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    pref = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == uid
    ).first()

    if not pref:
        pref = NotificationPreference(user_id=uid)
        db.add(pref)
        db.commit()
        db.refresh(pref)

    return {
        "status": "success",
        "data": {
            "workout_enabled": pref.workout_enabled,
            "education_enabled": pref.education_enabled,
            "posture_enabled": pref.posture_enabled,
            "system_enabled": pref.system_enabled,
        },
    }


# ---------------------------------------------------------------------------
# PATCH /api/notifications/preferences  —  Update user notification preferences
# ---------------------------------------------------------------------------
@router.patch("/preferences", status_code=status.HTTP_200_OK)
def update_preferences(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    pref = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == uid
    ).first()

    if not pref:
        pref = NotificationPreference(user_id=uid)
        db.add(pref)

    if "workout_enabled" in payload:
        pref.workout_enabled = bool(payload["workout_enabled"])
    if "education_enabled" in payload:
        pref.education_enabled = bool(payload["education_enabled"])
    if "posture_enabled" in payload:
        pref.posture_enabled = bool(payload["posture_enabled"])
    if "system_enabled" in payload:
        pref.system_enabled = bool(payload["system_enabled"])

    db.commit()

    return {
        "status": "success",
        "message": "Preferensi notifikasi berhasil diperbarui.",
        "data": {
            "workout_enabled": pref.workout_enabled,
            "education_enabled": pref.education_enabled,
            "posture_enabled": pref.posture_enabled,
            "system_enabled": pref.system_enabled,
        },
    }


# ---------------------------------------------------------------------------
# Seed notifications — when DB has no data yet
# ---------------------------------------------------------------------------
def _get_seed_notifications():
    """Static welcome notification matching Flutter NotificationItem format."""
    return [
        {
            "id": "seed-1",
            "title": "Selamat Datang di PostureFit!",
            "message": "Mulai perjalanan kebugaran Anda. Coba scan postur hari ini untuk mendapatkan rekomendasi personal.",
            "time": "Baru saja",
            "type": "system",
            "is_read": False,
        },
        {
            "id": "seed-2",
            "title": "Cek Postur Hari Ini",
            "message": "Jangan lupa lakukan scan postur harian Anda untuk memantau perkembangan.",
            "time": "Hari ini",
            "type": "posture",
            "is_read": False,
        },
    ]
