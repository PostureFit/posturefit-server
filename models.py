import uuid
from datetime import datetime

# pyrefly: ignore [missing-import]
from sqlalchemy import (
    Column, String, Integer, DateTime, Date, Text,
    ForeignKey, Boolean, UniqueConstraint, DECIMAL, BigInteger
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import relationship
# pyrefly: ignore [missing-import]
from sqlalchemy.sql import func

from database import Base


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _generate_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True, default=_generate_uuid)
    # → frontend: name
    nama_lengkap = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    # → frontend: phone
    phone_number = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    # Laki-laki / Perempuan
    gender = Column(String(20), nullable=True)
    # → frontend: goal (hasil SAW engine: Obesitas/Normal/Kurus/Skinnyfat)
    fokus_utama = Column(String(50), nullable=True)
    # → frontend: fokus_pilihan (pilihan user: Defisit Kalori/Surplus Kalori/Pertahankan)
    fokus_pilihan = Column(String(50), nullable=True)
    # → frontend: profilePicture
    foto_profil = Column(String(500), nullable=True)
    umur = Column(Integer, nullable=True)                 # → frontend: age
    # → frontend: height
    tinggi_cm = Column(DECIMAL(5, 2), nullable=True)
    # → frontend: weight
    berat_kg = Column(DECIMAL(5, 2), nullable=True)
    lingkar_perut_cm = Column(DECIMAL(5, 2), nullable=True)
    # → frontend: bmi
    bmi_terkini = Column(DECIMAL(4, 2), nullable=True)
    auth_provider = Column(String(20), nullable=True)  # "email" / "google"
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())


    # Relationships
    assessments = relationship(
        "CvAssessment",     back_populates="user", cascade="all, delete-orphan")
    trackers = relationship(
        "DailyTracker",     back_populates="user", cascade="all, delete-orphan")
    workout_plans = relationship(
        "DailyWorkoutPlan", back_populates="user", cascade="all, delete-orphan")
    workout_logs = relationship(
        "WorkoutLog",       back_populates="user", cascade="all, delete-orphan")
    notifications = relationship(
        "Notification",     back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# CvAssessment
# ---------------------------------------------------------------------------
class CvAssessment(Base):
    __tablename__ = "cv_assessments"

    id = Column(String(50), primary_key=True, default=_generate_uuid)
    user_id = Column(String(50), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    tanggal_scan = Column(DateTime, default=func.now())
    image_url = Column(String(500), nullable=True)
    tinggi_cm = Column(DECIMAL(5, 2), nullable=True)
    berat_kg = Column(DECIMAL(5, 2), nullable=True)
    lingkar_perut_cm = Column(DECIMAL(5, 2), nullable=True)
    umur = Column(Integer, nullable=True)
    bmi_kalkulasi = Column(DECIMAL(4, 2), nullable=True)
    kategori_tubuh = Column(String(50), nullable=True)
    # ← BARU: teks rekomendasi SAW
    rekomendasi = Column(Text, nullable=True)
    # ← BARU: JSON string skor SAW
    saw_scores = Column(Text, nullable=True)
    # ← BARU: MediaPipe Pose analysis
    wsr = Column(DECIMAL(5, 3), nullable=True)
    posture_score = Column(DECIMAL(5, 2), nullable=True)
    shoulder_balance = Column(DECIMAL(5, 3), nullable=True)
    # ← BARU: JSON string hasil LLM (analisis + rekomendasi)
    analisis_llm = Column(Text, nullable=True)
    # ← BARU: path ke file scan + landmark (annotated)
    annotated_image_url = Column(String(500), nullable=True)

    # Relationships
    user = relationship("User", back_populates="assessments")


# ---------------------------------------------------------------------------
# DailyTracker  —  Aligned with Flutter ActivityEntity
# ---------------------------------------------------------------------------
class DailyTracker(Base):
    __tablename__ = "daily_trackers"

    id = Column(String(50), primary_key=True, default=_generate_uuid)
    user_id = Column(String(50), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    tanggal = Column(Date, nullable=False)
    # Hidration
    hidrasi_ml = Column(Integer, nullable=True,
                        default=0)   # → hydrationCurrent
    hydration_target_ml = Column(
        Integer, nullable=True, default=2000)  # → hydrationTarget
    # Sleep
    tidur_jam = Column(DECIMAL(4, 2), nullable=True,
                       default=0)  # → sleepDuration
    # Activity percentages (0-100)
    olahraga = Column(Integer, nullable=True, default=0)   # → olahraga (%)
    nutrisi = Column(Integer, nullable=True, default=0)   # → nutrisi (%)
    tidur_persen = Column(Integer, nullable=True, default=0)   # → tidur (%)
    # → activityScore (0-100)
    skor_aktivitas = Column(Integer, nullable=True, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "tanggal", name="uq_user_tanggal"),
    )

    # Relationships
    user = relationship("User", back_populates="trackers")


# ---------------------------------------------------------------------------
# DailyWorkoutPlan
# ---------------------------------------------------------------------------
class DailyWorkoutPlan(Base):
    __tablename__ = "daily_workout_plans"

    id = Column(String(50), primary_key=True, default=_generate_uuid)
    user_id = Column(String(50), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    tanggal_rencana = Column(Date, nullable=False)
    tema_latihan = Column(String(150), nullable=True)
    target_kalori = Column(Integer, nullable=True)
    estimasi_menit = Column(Integer, nullable=True)

    # Relationships
    user = relationship("User", back_populates="workout_plans")
    tasks = relationship("WorkoutTask", back_populates="plan",
                         cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# WorkoutTask
# ---------------------------------------------------------------------------
class WorkoutTask(Base):
    __tablename__ = "workout_tasks"

    id = Column(String(50), primary_key=True, default=_generate_uuid)
    plan_id = Column(String(50), ForeignKey(
        "daily_workout_plans.id", ondelete="CASCADE"), nullable=False)
    nama_latihan = Column(String(100), nullable=False)
    target_otot = Column(String(100), nullable=True)
    set_reps = Column(String(50), nullable=True)
    is_completed = Column(Boolean, default=False)

    # Relationships
    plan = relationship("DailyWorkoutPlan", back_populates="tasks")


# ---------------------------------------------------------------------------
# WorkoutLog  —  Riwayat sesi workout yang diselesaikan
# Fields aligned with Flutter WorkoutLogController
# ---------------------------------------------------------------------------
class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id = Column(String(50), primary_key=True, default=_generate_uuid)
    user_id = Column(String(50), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(150), nullable=False)       # → frontend: title
    category = Column(String(100), nullable=True)        # → frontend: category
    # → frontend: duration (e.g. "15 menit")
    duration = Column(String(50), nullable=True)
    # → frontend: calories (e.g. "85 kcal")
    calories = Column(String(50), nullable=True)
    # → frontend: image (URL/asset path)
    image = Column(String(500), nullable=True)
    logged_at = Column(DateTime, default=func.now())  # → frontend: date

    # Relationships
    user = relationship("User", back_populates="workout_logs")


# ---------------------------------------------------------------------------
# EducationArticle  —  Artikel edukasi postur & kebugaran
# Fields aligned with Flutter EducationController / EducationItem.fromJson
# ---------------------------------------------------------------------------
class EducationArticle(Base):
    __tablename__ = "education_articles"

    id = Column(String(50), primary_key=True, default=_generate_uuid)
    # → frontend: judul / title
    judul = Column(String(255), nullable=False)
    # → frontend: ringkasan / summary
    ringkasan = Column(Text, nullable=True)
    # → frontend: gambar / image_url
    gambar = Column(String(500), nullable=True)
    kategori = Column(String(100), nullable=True)        # → frontend: kategori
    sumber = Column(String(150), nullable=True)        # → frontend: sumber
    # JSON array string → frontend: tips
    tips = Column(Text, nullable=True)
    # → frontend: link_direct
    link_direct = Column(String(500), nullable=True)
    # → frontend: updated_at
    updated_at = Column(DateTime, default=func.now())


# ---------------------------------------------------------------------------
# Notification  —  Notifikasi per-user
# Fields aligned with Flutter NotificationController / NotificationItem
# ---------------------------------------------------------------------------
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(50), primary_key=True, default=_generate_uuid)
    user_id = Column(String(50), ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)        # → frontend: title
    message = Column(Text, nullable=False)               # → frontend: message
    # posture/workout/education/system
    type = Column(String(50), nullable=True)
    is_read = Column(Boolean, default=False)             # → frontend: isRead
    created_at = Column(DateTime, default=func.now())  # → frontend: time

    # Relationships
    user = relationship("User", back_populates="notifications")


# ---------------------------------------------------------------------------
# NotificationPreference  —  Preferensi notifikasi per user
# User bisa pilih jenis notif yang ingin diterima
# ---------------------------------------------------------------------------
class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    workout_enabled = Column(Boolean, default=True)      # notif rekomendasi latihan
    education_enabled = Column(Boolean, default=True)    # notif artikel baru
    posture_enabled = Column(Boolean, default=True)      # notif pengingat scan postur
    system_enabled = Column(Boolean, default=True)       # notif sistem penting
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", backref="notification_preferences")


# ---------------------------------------------------------------------------
# AdminUser  —  Akun admin untuk dashboard backend
# Password di-hash dengan bcrypt, dikelola via script create_admin.py
# ---------------------------------------------------------------------------
class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# OtpRequest  —  Penyimpanan OTP sementara untuk verifikasi email saat register
# OTP akan dihapus setelah berhasil diverifikasi atau kadaluarsa
# ---------------------------------------------------------------------------
class OtpRequest(Base):
    __tablename__ = "otp_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), nullable=False, index=True)
    name = Column(String(100), nullable=True)
    # password sudah di-hash
    password_hash = Column(String(255), nullable=True)
    otp_code = Column(String(10), nullable=False)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# FcmToken  —  Device token untuk Firebase Cloud Messaging (push notif)
# ---------------------------------------------------------------------------
class FcmToken(Base):
    __tablename__ = "fcm_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", backref="fcm_tokens")


# ---------------------------------------------------------------------------
# LoginLog  —  Riwayat login user
# ---------------------------------------------------------------------------
class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(20), nullable=False)  # "email" / "google"
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", backref="login_logs")


# ---------------------------------------------------------------------------
# PasswordResetOtp  —  OTP khusus untuk reset password (lupa password)
# Dipisah dari otp_requests agar tidak konflik dengan alur registrasi
# ---------------------------------------------------------------------------
class PasswordResetOtp(Base):
    __tablename__ = "password_reset_otps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), nullable=False, index=True)
    otp_code = Column(String(10), nullable=False)
    is_used = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)  # True setelah OTP diverifikasi, sebelum password diganti
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

