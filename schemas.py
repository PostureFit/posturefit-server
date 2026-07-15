"""
schemas.py — Pydantic models aligned with Flutter frontend field names.

Field naming convention follows what Flutter expects in JSON responses.
"""

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, Any, List
from datetime import date, datetime
import re


# ====================================================================
# Generic API Response Wrapper
# ====================================================================
class ApiResponse(BaseModel):
    status: str = "success"
    message: str = ""
    data: Optional[Any] = None


# ====================================================================
# Auth — Request & Response
# ====================================================================
def _validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password minimal 8 karakter")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password harus mengandung huruf BESAR")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password harus mengandung huruf kecil")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password harus mengandung angka")
    return password


class RegisterRequest(BaseModel):
    name: str = Field(..., example="Budi Santoso")
    email: EmailStr
    phone_number: Optional[str] = Field(None, example="+6281234567890")
    password: str = Field(..., min_length=8)

    _validate_password = field_validator("password")(_validate_password)

class LoginRequest(BaseModel):
    email:    str
    password: str
    captcha_token: str = ""

class GoogleLoginRequest(BaseModel):
    """Request dari frontend Flutter — Firebase ID token dari Google Sign-In."""
    id_token: str

class SendOtpRequest(BaseModel):
    """Request kirim OTP ke email baru sebelum akun dibuat."""
    name:     str = Field(..., min_length=2)
    email:    str
    password: str = Field(..., min_length=8)
    captcha_token: str = ""

    _validate_password = field_validator("password")(_validate_password)

class VerifyOtpRequest(BaseModel):
    """Request verifikasi OTP dan finalisasi pembuatan akun."""
    email:    str
    otp_code: str = Field(..., min_length=4, max_length=10)
    phone_number: Optional[str] = Field("-", max_length=20)

class ResendOtpRequest(BaseModel):
    """Request kirim ulang OTP."""
    email: str
    captcha_token: str = ""

class ForgotPasswordSendOtpRequest(BaseModel):
    """Request kirim OTP untuk lupa password (email harus sudah terdaftar)."""
    email: str
    captcha_token: str = ""

class ForgotPasswordVerifyOtpRequest(BaseModel):
    """Request verifikasi OTP untuk lupa password."""
    email: str
    otp_code: str = Field(..., min_length=4, max_length=10)

class ForgotPasswordResetRequest(BaseModel):
    """Request ganti password setelah OTP terverifikasi."""
    email: str
    new_password: str = Field(..., min_length=8)

    _validate_password = field_validator("new_password")(_validate_password)

# ====================================================================
# User  —  Fields match Flutter UserModel.fromJson & ProfileController
# ====================================================================
class UserOut(BaseModel):
    """
    Maps backend DB columns → Flutter frontend field names:
        nama_lengkap  → name
        tinggi_cm     → height
        berat_kg      → weight
        bmi_terkini   → bmi
        fokus_utama   → goal
        umur          → age
    """
    id:      str
    name:    str                    # ← nama_lengkap
    email:   str
    height:  Optional[float] = None # ← tinggi_cm
    weight:  Optional[float] = None # ← berat_kg
    bmi:     Optional[float] = None # ← bmi_terkini
    goal:    Optional[str]  = None  # ← fokus_utama (hasil SAW: Obesitas/Normal/Kurus/Skinnyfat)
    fokus_pilihan: Optional[str] = None  # ← pilihan user: Defisit Kalori/Surplus Kalori/Pertahankan
    age:     Optional[int]  = None  # ← umur
    gender:  Optional[str]  = None
    profile_picture: Optional[str] = None # ← foto_profil
    lingkar_perut_cm: Optional[float] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_db(cls, user) -> "UserOut":
        """Build UserOut from a SQLAlchemy User instance."""
        return cls(
            id=user.id,
            name=user.nama_lengkap,
            email=user.email,
            height=float(user.tinggi_cm) if user.tinggi_cm is not None else None,
            weight=float(user.berat_kg) if user.berat_kg is not None else None,
            bmi=float(user.bmi_terkini) if user.bmi_terkini is not None else None,
            goal=user.fokus_utama,
            fokus_pilihan=getattr(user, 'fokus_pilihan', None),
            age=user.umur,
            gender=user.gender,
            profile_picture=getattr(user, 'foto_profil', None),
            lingkar_perut_cm=float(user.lingkar_perut_cm) if user.lingkar_perut_cm is not None else None,
            created_at=user.created_at,
        )

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type:   str
    user:         UserOut


# ====================================================================
# Profile Update  —  PUT /api/auth/profile
# ====================================================================
class ProfileUpdateRequest(BaseModel):
    """Request body for updating user profile from EditProfileController."""
    name:   Optional[str]   = Field(None, min_length=2, max_length=100)
    age:    Optional[int]   = Field(None, ge=5, le=120)
    height: Optional[float] = Field(None, gt=0, le=300)
    weight: Optional[float] = Field(None, gt=0, le=500)
    gender: Optional[str]   = None


# ====================================================================
# Image Analysis (MediaPipe Pose)
# ====================================================================
class ImageAnalysisResponse(BaseModel):
    status:             str   = "success"
    wsr:                float = 0.0
    shoulder_balance:   float = 0.0
    posture_score:      float = 0.0
    landmarks:          list  = []
    connections:        list  = []
    img_width:          int   = 0
    img_height:         int   = 0
    image_url:          str   = ""   # path ke file scan asli
    annotated_image_url: str = ""   # path ke file scan + landmark


# ====================================================================
# CV / Assessment
# ====================================================================
class VitalityAssessmentRequest(BaseModel):
    """
    One-shot payload from the Flutter result_view (scan form).
    Matches fields sent by ResultController.onAnalysis():
      tinggi        → tinggi_cm
      berat         → berat_kg
      umur          → umur
      lingkar       → lingkar_perut_cm
      fokus_pilihan → pilihan fokus user (disimpan terpisah dari SAW result)
    """
    image_url:         str            = ""
    umur:              int            = Field(..., ge=1, le=120)
    tinggi_cm:         float          = Field(..., gt=0, alias="tinggi")
    berat_kg:          float          = Field(..., gt=0, alias="berat")
    lingkar_perut_cm:  float          = Field(..., gt=0, alias="lingkar")
    fokus_pilihan:     Optional[str]  = None  # Defisit Kalori / Surplus Kalori / Pertahankan
    wsr:               Optional[float] = None  # dari MediaPipe Pose (foto)
    posture_score:     Optional[float] = None  # dari MediaPipe Pose (foto)
    shoulder_balance:  Optional[float] = None  # dari MediaPipe Pose (foto)
    lingkungan:        Optional[str]  = None   # Rumah / GYM / Calisthenics

    class Config:
        populate_by_name = True


class AssessmentResult(BaseModel):
    bmi:            float
    kategori_tubuh: str                  # Kurus / Normal / Gemuk / Obesitas
    rekomendasi:    str
    saw_scores:     Optional[dict] = None
    wsr:            Optional[float] = None
    posture_score:  Optional[float] = None
    analisis_llm:   Optional[dict]  = None  # dari Gemini LLM
    image_url:      Optional[str]  = None   # foto scan asli


class AssessmentResponse(BaseModel):
    status:  str = "success"
    message: str = "Analisis selesai. Rekomendasi telah dibuat."
    data:    AssessmentResult


class AssessmentHistoryItem(BaseModel):
    id:              str
    tanggal_scan:    Optional[str]   = None
    image_url:       Optional[str]   = None
    tinggi_cm:       Optional[float] = None
    berat_kg:        Optional[float] = None
    bmi_kalkulasi:   Optional[float] = None
    kategori_tubuh:  Optional[str]   = None
    rekomendasi:     Optional[str]   = None


# ====================================================================
# Daily Tracker  —  Aligned with Flutter ActivityEntity
# ====================================================================
class DailyTrackerUpdate(BaseModel):
    """
    Create or update daily tracker.
    All metric fields optional → partial update support.
    Matches ActivityEntity fields Flutter expects.
    """
    tanggal:             date
    hidrasi_ml:          Optional[int]   = Field(None, ge=0)         # hydrationCurrent
    hydration_target_ml: Optional[int]   = Field(None, ge=0)         # hydrationTarget
    tidur_jam:           Optional[float] = Field(None, ge=0, le=24)  # sleepDuration
    olahraga:            Optional[int]   = Field(None, ge=0, le=100) # olahraga %
    nutrisi:             Optional[int]   = Field(None, ge=0, le=100) # nutrisi %
    tidur_persen:        Optional[int]   = Field(None, ge=0, le=100) # tidur %
    skor_aktivitas:      Optional[int]   = Field(None, ge=0, le=100) # activityScore


class DailyTrackerOut(BaseModel):
    """
    Response aligned with Flutter ActivityEntity:
        olahraga        (int 0-100)
        nutrisi         (int 0-100)
        tidur           (int 0-100)
        sleepDuration   (double jam)
        hydrationCurrent(double ml)
        hydrationTarget (double ml)
        activityScore   (int 0-100)
    """
    tanggal:           date
    olahraga:          int   = 0       # → ActivityEntity.olahraga
    nutrisi:           int   = 0       # → ActivityEntity.nutrisi
    tidur:             int   = 0       # → ActivityEntity.tidur (%)
    sleep_duration:    float = 0.0     # → ActivityEntity.sleepDuration
    hydration_current: float = 0.0     # → ActivityEntity.hydrationCurrent
    hydration_target:  float = 2000.0  # → ActivityEntity.hydrationTarget
    activity_score:    int   = 0       # → ActivityEntity.activityScore

    @classmethod
    def from_db(cls, tracker, target_date: date = None) -> "DailyTrackerOut":
        if tracker is None:
            return cls(tanggal=target_date or date.today())
        return cls(
            tanggal=tracker.tanggal,
            olahraga=tracker.olahraga or 0,
            nutrisi=tracker.nutrisi or 0,
            tidur=tracker.tidur_persen or 0,
            sleep_duration=float(tracker.tidur_jam or 0),
            hydration_current=float(tracker.hidrasi_ml or 0),
            hydration_target=float(tracker.hydration_target_ml or 2000),
            activity_score=tracker.skor_aktivitas or 0,
        )

    class Config:
        from_attributes = True


# ====================================================================
# Home / Dashboard
# ====================================================================
class HomeSummary(BaseModel):
    user:             UserOut
    indikator_harian: DailyTrackerOut


class HomeResponse(BaseModel):
    status: str = "success"
    data:   HomeSummary


# ====================================================================
# Workout Log  —  Aligned with Flutter WorkoutLogController
# ====================================================================
class WorkoutLogCreate(BaseModel):
    title:    str
    category: Optional[str]  = None
    duration: Optional[str]  = None   # e.g. "15 menit"
    calories: Optional[str]  = None   # e.g. "85 kcal"
    image:    Optional[str]  = None


class WorkoutLogOut(BaseModel):
    id:        str
    title:     str
    category:  Optional[str]  = None
    duration:  Optional[str]  = None
    calories:  Optional[str]  = None
    image:     Optional[str]  = None
    date:      Optional[str]  = None  # formatted date string → frontend: date

    @classmethod
    def from_db(cls, log) -> "WorkoutLogOut":
        return cls(
            id=log.id,
            title=log.title,
            category=log.category,
            duration=log.duration,
            calories=log.calories,
            image=log.image,
            date=log.logged_at.strftime("%d %b, %H:%M") if log.logged_at else None,
        )

    class Config:
        from_attributes = True


# ====================================================================
# Education  —  Aligned with Flutter EducationController.EducationItem.fromJson
# ====================================================================
class EducationOut(BaseModel):
    """
    Fields match EducationItem.fromJson keys Flutter expects:
        judul       / title
        ringkasan   / summary
        gambar      / image_url
        kategori
        sumber
        updated_at
        tips        (list)
        link_direct
    """
    id:          str
    judul:       str                        # → title
    ringkasan:   Optional[str]  = None      # → summary
    gambar:      Optional[str]  = None      # → imageUrl
    kategori:    Optional[str]  = "umum"
    sumber:      Optional[str]  = "Unknown"
    updated_at:  Optional[str]  = None
    tips:        List[str]      = []
    link_direct: Optional[str]  = None

    @classmethod
    def from_db(cls, article) -> "EducationOut":
        import json as _json
        tips_list: List[str] = []
        if article.tips:
            try:
                tips_list = _json.loads(article.tips)
            except Exception:
                tips_list = []
        return cls(
            id=article.id,
            judul=article.judul,
            ringkasan=article.ringkasan,
            gambar=article.gambar,
            kategori=article.kategori or "umum",
            sumber=article.sumber or "Unknown",
            updated_at=article.updated_at.strftime("%Y-%m-%d") if article.updated_at else None,
            tips=tips_list,
            link_direct=article.link_direct,
        )

    class Config:
        from_attributes = True


# ====================================================================
# Notification  —  Aligned with Flutter NotificationController
# ====================================================================
class NotificationOut(BaseModel):
    """
    Fields match Flutter NotificationItem:
        id, title, message, time, type, isRead, createdAt
    """
    id:         str
    title:      str
    message:    str
    time:       Optional[str]  = None   # formatted relative time (compat lama)
    created_at: Optional[str]  = None   # ISO 8601 UTC — untuk hitung ulang di Flutter
    type:       Optional[str]  = "system"
    is_read:    bool           = False   # → frontend: isRead

    @classmethod
    def from_db(cls, notif) -> "NotificationOut":
        from datetime import timezone, timedelta
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib)

        created_at_iso: Optional[str] = None
        if notif.created_at is None:
            time_str = ""
        else:
            # notif.created_at dari MySQL tersimpan di waktu lokal (WIB) tanpa tzinfo
            # Jadikan dia aware terhadap WIB
            created_wib = notif.created_at.replace(tzinfo=wib)
            
            diff = now - created_wib
            total_seconds = int(diff.total_seconds())
            
            if total_seconds < 60:
                time_str = "Baru saja"
            elif total_seconds < 3600:
                menit = total_seconds // 60
                time_str = f"{menit} menit lalu"
            elif total_seconds < 86400:
                jam = total_seconds // 3600
                time_str = f"{jam} jam lalu"
            elif diff.days == 1:
                time_str = "Kemarin"
            else:
                time_str = f"{diff.days} hari lalu"

            # Kirim timestamp UTC sebenarnya ke Flutter (konversi WIB -> UTC)
            created_at_iso = created_wib.astimezone(timezone.utc).isoformat()

        return cls(
            id=notif.id,
            title=notif.title,
            message=notif.message,
            time=time_str,
            created_at=created_at_iso,
            type=notif.type,
            is_read=notif.is_read,
        )

    class Config:
        from_attributes = True


# ====================================================================
# Progress Report
# ====================================================================
class ProgressDataPoint(BaseModel):
    tanggal:        str
    activity_score: int = 0
    olahraga:       int = 0
    nutrisi:        int = 0
    tidur:          int = 0


class ProgressResponse(BaseModel):
    status: str = "success"
    period: str
    data:   List[ProgressDataPoint]