# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from sqlalchemy import func
from markupsafe import Markup
from database import get_db
# pyrefly: ignore [missing-import]
from sqladmin import ModelView
from sync_service import sync_education_from_mongo
from models import (
    User, CvAssessment, DailyTracker,
    DailyWorkoutPlan, WorkoutTask,
    WorkoutLog, EducationArticle, Notification, AdminUser, FcmToken, LoginLog, NotificationPreference,
)


def _render_image(url):
    if not url:
        return Markup('<span style="color:#94a3b8;">Tidak ada</span>')
    return Markup(
        '<a href="{}" target="_blank">'
        '<img src="{}" '
        'style="max-width:80px;max-height:60px;border-radius:6px;object-fit:cover;'
        'border:1px solid #e2e8f0;" '
        'onerror="this.style.display=\'none\'" />'
        '</a>'.format(url, url)
    )


class UserAdmin(ModelView, model=User):
    column_list = [
        User.id,
        User.nama_lengkap,
        User.email,
        User.auth_provider,
        User.last_login_at,
        User.gender,
        User.umur,
        User.tinggi_cm,
        User.berat_kg,
        User.lingkar_perut_cm,
        User.bmi_terkini,
        User.fokus_utama,
        User.created_at,
    ]
    column_searchable_list = [User.nama_lengkap, User.email]
    column_sortable_list   = [User.created_at, User.bmi_terkini, User.last_login_at]
    column_default_sort    = ("created_at", True)
    column_labels = {
        "auth_provider": "Provider",
        "last_login_at": "Terakhir Login",
    }
    name        = "Data Pengguna"
    name_plural = "Data Pengguna"
    icon        = "fa-solid fa-users"


class CvAssessmentAdmin(ModelView, model=CvAssessment):
    column_list = [
        CvAssessment.id,
        CvAssessment.user_id,
        CvAssessment.kategori_tubuh,
        CvAssessment.bmi_kalkulasi,
        CvAssessment.wsr,
        CvAssessment.posture_score,
        CvAssessment.shoulder_balance,
        CvAssessment.rekomendasi,
        CvAssessment.tanggal_scan,
        CvAssessment.image_url,
        CvAssessment.annotated_image_url,
    ]
    column_searchable_list = [CvAssessment.kategori_tubuh]
    column_sortable_list   = [CvAssessment.tanggal_scan, CvAssessment.bmi_kalkulasi]
    column_default_sort    = ("tanggal_scan", True)
    column_formatters = {
        "image_url": lambda m, a: _render_image(m.image_url),
        "annotated_image_url": lambda m, a: _render_image(m.annotated_image_url),
    }
    column_labels = {
        "image_url":            "Foto",
        "annotated_image_url":  "Foto + Landmark",
        "wsr":                  "WSR",
        "posture_score":        "Posture",
        "shoulder_balance":     "Shoulder",
    }
    name        = "Hasil Scan CV"
    name_plural = "Hasil Scan CV"
    icon        = "fa-solid fa-camera"


class DailyTrackerAdmin(ModelView, model=DailyTracker):
    column_list = [
        DailyTracker.id,
        DailyTracker.user_id,
        DailyTracker.tanggal,
        DailyTracker.olahraga,
        DailyTracker.nutrisi,
        DailyTracker.tidur_persen,
        DailyTracker.hidrasi_ml,
        DailyTracker.hydration_target_ml,
        DailyTracker.tidur_jam,
        DailyTracker.skor_aktivitas,
    ]
    column_sortable_list = [DailyTracker.tanggal, DailyTracker.skor_aktivitas]
    column_default_sort  = ("tanggal", True)
    name        = "Aktivitas Harian"
    name_plural = "Aktivitas Harian"
    icon        = "fa-solid fa-chart-line"


class DailyWorkoutPlanAdmin(ModelView, model=DailyWorkoutPlan):
    column_list = [
        DailyWorkoutPlan.id,
        DailyWorkoutPlan.user_id,
        DailyWorkoutPlan.tanggal_rencana,
        DailyWorkoutPlan.tema_latihan,
        DailyWorkoutPlan.target_kalori,
        DailyWorkoutPlan.estimasi_menit,
    ]
    name        = "Rencana Latihan"
    name_plural = "Rencana Latihan"
    icon        = "fa-solid fa-dumbbell"


class WorkoutTaskAdmin(ModelView, model=WorkoutTask):
    column_list = [
        WorkoutTask.id,
        WorkoutTask.plan_id,
        WorkoutTask.nama_latihan,
        WorkoutTask.target_otot,
        WorkoutTask.set_reps,
        WorkoutTask.is_completed,
    ]
    name        = "Detail Latihan"
    name_plural = "Detail Latihan"
    icon        = "fa-solid fa-list-check"


class WorkoutLogAdmin(ModelView, model=WorkoutLog):
    column_list = [
        WorkoutLog.id,
        WorkoutLog.user_id,
        WorkoutLog.title,
        WorkoutLog.category,
        WorkoutLog.duration,
        WorkoutLog.calories,
        WorkoutLog.logged_at,
    ]
    column_searchable_list = [WorkoutLog.title, WorkoutLog.category]
    column_sortable_list   = [WorkoutLog.logged_at]
    column_default_sort    = ("logged_at", True)
    name        = "Riwayat Workout"
    name_plural = "Riwayat Workout"
    icon        = "fa-solid fa-person-running"


class EducationArticleAdmin(ModelView, model=EducationArticle):
    column_list = [
        EducationArticle.id,
        EducationArticle.judul,
        EducationArticle.kategori,
        EducationArticle.sumber,
        EducationArticle.updated_at,
    ]
    column_searchable_list = [EducationArticle.judul, EducationArticle.kategori]
    column_sortable_list   = [EducationArticle.updated_at]
    column_default_sort    = ("updated_at", True)
    name        = "Artikel Edukasi"
    name_plural = "Artikel Edukasi"
    icon        = "fa-solid fa-book"


class NotificationAdmin(ModelView, model=Notification):
    # ── Tabel daftar notifikasi ──────────────────────────────────────────────
    column_list = [
        Notification.id,
        Notification.user_id,
        Notification.title,
        Notification.type,
        Notification.is_read,
        Notification.created_at,
    ]
    column_searchable_list = [Notification.title, Notification.type]
    column_sortable_list   = [Notification.created_at]
    column_default_sort    = ("created_at", True)

    # ── Hanya lihat daftar — tidak bisa buat/edit via admin ──────────────────
    can_create = False
    can_edit   = False
    can_delete = True

    name        = "Notifikasi"
    name_plural = "Notifikasi"
    icon        = "fa-solid fa-bell"


class AdminUserAdmin(ModelView, model=AdminUser):
    # Sembunyikan password_hash dari tampilan & form
    column_list = [
        AdminUser.id,
        AdminUser.username,
        AdminUser.email,
        AdminUser.is_active,
        AdminUser.created_at,
        "change_password",
    ]
    column_searchable_list  = [AdminUser.username, AdminUser.email]
    column_sortable_list    = [AdminUser.created_at, AdminUser.username]
    column_default_sort     = ("created_at", True)
    form_excluded_columns   = ["password_hash"]   # jangan tampilkan hash password
    can_create              = False                # buat admin via create_admin.py
    can_edit                = True                 # bisa toggle is_active
    can_delete              = True
    name        = "Admin Users"
    name_plural = "Admin Users"
    icon        = "fa-solid fa-user-shield"

    # Kolom virtual: tombol ganti password
    column_formatters = {
        "change_password": lambda m, a: Markup(
            '<a href="/admin-cp/change-password" '
            'style="display:inline-flex;align-items:center;gap:5px;'
            'padding:4px 11px;border-radius:6px;font-size:12px;font-weight:600;'
            'color:#fff;background:linear-gradient(135deg,#6366f1,#4f46e5);'
            'text-decoration:none;white-space:nowrap;'
            'box-shadow:0 1px 4px rgba(99,102,241,.4);'
            'transition:opacity .18s;" '
            'onmouseover="this.style.opacity=\'0.85\'" '
            'onmouseout="this.style.opacity=\'1\'">'
            '🔑 Ganti Password'
            '</a>'
        ),
    }
    column_labels = {"change_password": "Password"}


class FcmTokenAdmin(ModelView, model=FcmToken):
    column_list = [
        FcmToken.id,
        FcmToken.user_id,
        FcmToken.token,
        FcmToken.created_at,
        FcmToken.updated_at,
    ]
    column_searchable_list = [FcmToken.token]
    column_sortable_list   = [FcmToken.created_at]
    column_default_sort    = ("created_at", True)
    can_create = False
    can_edit   = False
    name        = "FCM Token"
    name_plural = "FCM Token"
    icon        = "fa-solid fa-bell"


class NotificationPreferenceAdmin(ModelView, model=NotificationPreference):
    column_list = [
        NotificationPreference.id,
        NotificationPreference.user_id,
        NotificationPreference.workout_enabled,
        NotificationPreference.education_enabled,
        NotificationPreference.posture_enabled,
        NotificationPreference.system_enabled,
        NotificationPreference.updated_at,
    ]
    column_searchable_list = [NotificationPreference.user_id]
    column_sortable_list   = [NotificationPreference.updated_at]
    column_default_sort    = ("updated_at", True)
    can_create = False
    can_edit   = True
    can_delete = True
    name        = "Pref Notifikasi"
    name_plural = "Pref Notifikasi"
    icon        = "fa-solid fa-sliders"


class LoginLogAdmin(ModelView, model=LoginLog):
    column_list = [
        LoginLog.id,
        LoginLog.user_id,
        LoginLog.provider,
        LoginLog.ip_address,
        LoginLog.created_at,
    ]
    column_searchable_list = [LoginLog.provider, LoginLog.ip_address]
    column_sortable_list   = [LoginLog.created_at]
    column_default_sort    = ("created_at", True)
    can_create = False
    can_edit   = False
    can_delete = True
    name        = "Log Login"
    name_plural = "Log Login"
    icon        = "fa-solid fa-right-to-bracket"


# ---------------------------------------------------------------------------
# Admin Dashboard Stats API
# ---------------------------------------------------------------------------
admin_api_router = APIRouter(prefix="/admin-api", tags=["Admin API"])


@admin_api_router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    total_users          = db.query(User).count()
    total_scans          = db.query(CvAssessment).count()
    total_plans          = db.query(DailyWorkoutPlan).count()
    total_workout_logs   = db.query(WorkoutLog).count()
    total_articles       = db.query(EducationArticle).count()
    total_notifications  = db.query(Notification).count()

    categories = (
        db.query(CvAssessment.kategori_tubuh, func.count(CvAssessment.id))
        .group_by(CvAssessment.kategori_tubuh)
        .all()
    )
    cat_data = {(c[0] if c[0] else "Belum Diketahui"): c[1] for c in categories}

    # Registrations per day (last 7 days), ordered ascending for the chart
    regs = (
        db.query(func.date(User.created_at), func.count(User.id))
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at).desc())
        .limit(7)
        .all()
    )
    reg_data = {str(r[0]): r[1] for r in reversed(regs)}

    avg_bmi = db.query(func.avg(User.bmi_terkini)).scalar() or 0

    # ── Education analytics ───────────────────────────────────────────────
    edu_by_category_rows = (
        db.query(EducationArticle.kategori, func.count(EducationArticle.id))
        .group_by(EducationArticle.kategori)
        .all()
    )
    edu_by_category = {r[0] or "lainnya": r[1] for r in edu_by_category_rows}

    edu_sync_rows = (
        db.query(func.date(EducationArticle.updated_at), func.count(EducationArticle.id))
        .group_by(func.date(EducationArticle.updated_at))
        .order_by(func.date(EducationArticle.updated_at).desc())
        .limit(7)
        .all()
    )
    edu_sync_timeline = {str(r[0]): r[1] for r in reversed(edu_sync_rows)}

    edu_source_rows = (
        db.query(EducationArticle.sumber, func.count(EducationArticle.id))
        .group_by(EducationArticle.sumber)
        .order_by(func.count(EducationArticle.id).desc())
        .limit(10)
        .all()
    )
    edu_by_source = {r[0] or "tidak diketahui": r[1] for r in edu_source_rows}

    top_sources = [r[0] for r in edu_source_rows]
    edu_source_category_rows = (
        db.query(EducationArticle.sumber, EducationArticle.kategori, func.count(EducationArticle.id))
        .filter(EducationArticle.sumber.in_(top_sources))
        .group_by(EducationArticle.sumber, EducationArticle.kategori)
        .all()
    )
    edu_source_category = {}
    for src, cat, cnt in edu_source_category_rows:
        src = src or "tidak diketahui"
        cat = cat or "lainnya"
        if src not in edu_source_category:
            edu_source_category[src] = {}
        edu_source_category[src][cat] = cnt

    edu_top_articles_rows = (
        db.query(EducationArticle.judul, EducationArticle.kategori, EducationArticle.updated_at)
        .order_by(EducationArticle.updated_at.desc())
        .limit(5)
        .all()
    )
    edu_top_articles = [
        {"judul": r[0], "kategori": r[1] or "", "updated": str(r[2]) if r[2] else ""}
        for r in edu_top_articles_rows
    ]

    google_users  = db.query(User).filter(User.auth_provider == "google").count()
    email_users   = db.query(User).filter(User.auth_provider == "email").count()
    unknown_users = db.query(User).filter(User.auth_provider == None).count()

    from datetime import date, timedelta
    today     = date.today()
    week_ago  = today - timedelta(days=7)
    login_today = db.query(LoginLog).filter(
        func.date(LoginLog.created_at) == today
    ).count()
    login_7days = db.query(LoginLog).filter(
        func.date(LoginLog.created_at) >= week_ago
    ).count()

    return {
        "total_users":          total_users,
        "total_scans":          total_scans,
        "total_plans":          total_plans,
        "total_workout_logs":   total_workout_logs,
        "total_articles":       total_articles,
        "total_notifications":  total_notifications,
        "kategori_tubuh":       cat_data,
        "registrations":        reg_data,
        "avg_bmi":              round(float(avg_bmi), 2),
        "users_by_provider":    {"google": google_users, "email": email_users, "unknown": unknown_users},
        "login_today":          login_today,
        "login_7days":          login_7days,
        "edu_by_category":      edu_by_category,
        "edu_sync_timeline":    edu_sync_timeline,
        "edu_by_source":        edu_by_source,
        "edu_source_category":  edu_source_category,
        "edu_top_articles":     edu_top_articles,
    }


@admin_api_router.post("/sync-education")
async def admin_sync_education():
    """
    Endpoint trigger sinkronisasi manual MongoDB → MySQL.
    Dipanggil dari tombol di Admin Dashboard.
    """
    try:
        result = await sync_education_from_mongo()
        return {
            "status": "success",
            "message": f"Sinkronisasi selesai! {result['added']} artikel baru, {result['updated']} diperbarui.",
            "detail": result,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Sinkronisasi gagal: {str(e)}",
        }


