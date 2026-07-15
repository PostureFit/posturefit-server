import logging
from datetime import datetime, timedelta

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
import os
import shutil
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

logger = logging.getLogger("posturfit")

from database import get_db
from models import User, OtpRequest, PasswordResetOtp, FcmToken, LoginLog
from auth import hash_password, verify_password, create_access_token, get_current_user
from otp_service import generate_otp, hash_otp, send_otp_email, OTP_EXPIRE_MINUTES, send_html_email
from rate_limit import limiter
from recaptcha import verify_recaptcha
from schemas import (
    ApiResponse, UserOut, ProfileUpdateRequest,
    LoginRequest, GoogleLoginRequest, RegisterRequest, Token,
    SendOtpRequest, VerifyOtpRequest, ResendOtpRequest,
    ForgotPasswordSendOtpRequest, ForgotPasswordVerifyOtpRequest, ForgotPasswordResetRequest,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /api/auth/send-otp — Langkah 1 Register: Kirim kode OTP ke email
# ---------------------------------------------------------------------------
@router.post("/send-otp", response_model=ApiResponse, status_code=status.HTTP_200_OK)
@limiter.limit("3/10minutes")
async def send_otp(request: Request, payload: SendOtpRequest, db: Session = Depends(get_db)):
    await verify_recaptcha(payload.captcha_token)
    # Cek apakah email sudah terdaftar sebagai akun aktif
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah terdaftar. Silakan login.",
        )

    # Hapus OTP lama yang belum digunakan untuk email ini
    db.query(OtpRequest).filter(
        OtpRequest.email == payload.email,
        OtpRequest.is_used == False
    ).delete()
    db.commit()

    # Buat OTP baru
    otp_code  = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)

    otp_record = OtpRequest(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        otp_code=hash_otp(otp_code),
        is_used=False,
        expires_at=expires_at,
    )
    db.add(otp_record)
    db.commit()

    # Kirim email OTP
    sent = send_otp_email(
        to_email=payload.email,
        otp_code=otp_code,
        user_name=payload.name,
    )

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengirim email verifikasi. Coba lagi.",
        )

    return ApiResponse(
        status="success",
        message=f"Kode OTP telah dikirim ke {payload.email}. Berlaku {OTP_EXPIRE_MINUTES} menit.",
        data={"email": payload.email, "expires_minutes": OTP_EXPIRE_MINUTES},
    )


# ---------------------------------------------------------------------------
# POST /api/auth/verify-otp — Langkah 2 Register: Verifikasi OTP & buat akun
# ---------------------------------------------------------------------------
@router.post("/verify-otp", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/10minutes")
def verify_otp(request: Request, payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    """
    Langkah 2 registrasi: Verifikasi kode OTP.
    Jika valid → akun User dibuat → JWT token dikembalikan (langsung login).
    """
    otp_record = (
        db.query(OtpRequest)
        .filter(
            OtpRequest.email == payload.email,
            OtpRequest.is_used == False,
        )
        .order_by(OtpRequest.created_at.desc())
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP tidak ditemukan. Silakan daftar ulang.",
        )

    if datetime.utcnow() > otp_record.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kode OTP sudah kadaluarsa. Silakan minta ulang.",
        )

    if otp_record.otp_code != hash_otp(payload.otp_code.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kode OTP tidak valid.",
        )

    # Tandai OTP sebagai sudah digunakan
    otp_record.is_used = True
    db.commit()

    # Cek apakah email sudah terdaftar (race condition guard)
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        access_token = create_access_token(data={"sub": existing_user.id})
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=UserOut.from_db(existing_user),
        )

    # Buat akun User baru
    new_user = User(
        nama_lengkap=otp_record.name,
        email=otp_record.email,
        phone_number=payload.phone_number or "-",
        password_hash=otp_record.password_hash,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Kirim email selamat datang
    from otp_service import _build_welcome_email, send_html_email
    try:
        html_body = _build_welcome_email(otp_record.name)
        send_html_email(otp_record.email, "Selamat Datang di PostureFit!", html_body)
    except Exception as e:
        logger.error("Failed to send welcome email: %s", e)

    # Buat JWT token langsung — user tidak perlu login manual lagi
    access_token = create_access_token(data={"sub": new_user.id})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.from_db(new_user),
    )


# ---------------------------------------------------------------------------
# POST /api/auth/resend-otp — Kirim ulang OTP
# ---------------------------------------------------------------------------
@router.post("/resend-otp", response_model=ApiResponse, status_code=status.HTTP_200_OK)
@limiter.limit("3/10minutes")
async def resend_otp(request: Request, payload: ResendOtpRequest, db: Session = Depends(get_db)):
    await verify_recaptcha(payload.captcha_token)
    """Kirim ulang OTP ke email yang sama (untuk kasus email tidak masuk)."""
    # Ambil data OTP terakhir yang belum digunakan
    old_otp = (
        db.query(OtpRequest)
        .filter(OtpRequest.email == payload.email, OtpRequest.is_used == False)
        .order_by(OtpRequest.created_at.desc())
        .first()
    )

    if not old_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak ada permintaan registrasi aktif untuk email ini. Silakan daftar ulang.",
        )

    # Buat OTP baru & perbarui record lama
    new_otp_code = generate_otp()
    old_otp.otp_code   = hash_otp(new_otp_code)
    old_otp.expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    db.commit()

    sent = send_otp_email(
        to_email=payload.email,
        otp_code=new_otp_code,
        user_name=old_otp.name or "Pengguna",
    )

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengirim ulang email. Coba lagi.",
        )

    return ApiResponse(
        status="success",
        message=f"Kode OTP baru telah dikirim ke {payload.email}.",
        data={"email": payload.email, "expires_minutes": OTP_EXPIRE_MINUTES},
    )


def _record_login(db: Session, user: User, provider: str, request: Request = None):
    """Catat login ke tabel LoginLog + update kolom user."""
    user.auth_provider = provider
    user.last_login_at = datetime.utcnow()

    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")

    log = LoginLog(
        user_id=user.id,
        provider=provider,
        ip_address=ip or "",
        user_agent=ua or "",
    )
    db.add(log)
    db.commit()


# ---------------------------------------------------------------------------
# POST /api/auth/login — Login with email/password
# ---------------------------------------------------------------------------
@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
@limiter.limit("5/10minutes")
async def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Login and get an access token."""
    await verify_recaptcha(payload.captcha_token)

    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah.",
        )

    access_token = create_access_token(data={"sub": user.id})
    _record_login(db, user, "email", request)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.from_db(user)
    )


# ---------------------------------------------------------------------------
# POST /api/auth/google — Login/Register with Google
# ---------------------------------------------------------------------------
@router.post("/google", response_model=Token, status_code=status.HTTP_200_OK)
async def google_login(payload: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Endpoint untuk autentikasi via Google dengan Firebase ID token.
    Backend verifikasi token ke Firebase Admin SDK, lalu buat/login user.
    """
    from firebase_auth import verify_google_token

    decoded = verify_google_token(payload.id_token)
    if not decoded:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Google tidak valid. Silakan coba login ulang.",
        )

    email = decoded["email"]
    name = decoded["name"]
    picture_url = decoded.get("picture")

    user = db.query(User).filter(User.email == email).first()

    if not user:
        import secrets
        random_password = secrets.token_urlsafe(16)

        user = User(
            nama_lengkap=name,
            email=email,
            phone_number="-",
            password_hash=hash_password(random_password),
            foto_profil=picture_url,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        from otp_service import _build_welcome_email, send_html_email
        try:
            html_body = _build_welcome_email(user.nama_lengkap)
            send_html_email(user.email, "Selamat Datang di PostureFit (Google Sign In)!", html_body)
        except Exception as e:
            logger.error("Failed to send welcome email: %s", e)
    else:
        if user.foto_profil != picture_url:
            user.foto_profil = picture_url
            db.commit()

    access_token = create_access_token(data={"sub": user.id})
    _record_login(db, user, "google", request)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.from_db(user)
    )


@router.post("/fcm-token", status_code=status.HTTP_200_OK)
async def update_fcm_token(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Simpan atau update FCM token untuk push notifikasi."""
    fcm_token = payload.get("fcm_token", "").strip()
    if not fcm_token:
        raise HTTPException(status_code=400, detail="fcm_token tidak boleh kosong.")

    existing = db.query(FcmToken).filter(
        FcmToken.user_id == current_user.id,
        FcmToken.token == fcm_token,
    ).first()

    if existing:
        existing.updated_at = datetime.utcnow()
    else:
        new_token = FcmToken(
            user_id=current_user.id,
            token=fcm_token,
        )
        db.add(new_token)

    db.commit()
    return {"status": "success", "message": "FCM token berhasil disimpan."}


# ---------------------------------------------------------------------------
# GET /api/auth/me — Fetch current user profile
# ---------------------------------------------------------------------------
@router.get("/me", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return ApiResponse(
        status="success",
        message="Data profil berhasil diambil.",
        data=UserOut.from_db(current_user).model_dump(),
    )


# ---------------------------------------------------------------------------
# PUT /api/auth/profile — Update user profile
# ---------------------------------------------------------------------------
@router.put("/profile", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile data."""
    if payload.name is not None:
        current_user.nama_lengkap = payload.name.strip()
    if payload.age is not None:
        current_user.umur = payload.age
    if payload.height is not None:
        current_user.tinggi_cm = payload.height
    if payload.weight is not None:
        current_user.berat_kg = payload.weight
    if payload.gender is not None:
        current_user.gender = payload.gender

    # Recalculate BMI
    h = float(current_user.tinggi_cm) if current_user.tinggi_cm else 0
    w = float(current_user.berat_kg) if current_user.berat_kg else 0
    if h > 0 and w > 0:
        current_user.bmi_terkini = round(w / ((h / 100) ** 2), 1)

    db.commit()
    db.refresh(current_user)

    return ApiResponse(
        status="success",
        message="Profil berhasil diperbarui.",
        data=UserOut.from_db(current_user).model_dump(),
    )


# ---------------------------------------------------------------------------
# POST /api/auth/profile-picture — Upload profile picture
# ---------------------------------------------------------------------------
@router.post("/profile-picture", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload or update profile picture."""
    upload_dir = "static/profiles"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_ext = file.filename.split(".")[-1]
    filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}.{file_ext}"
    file_path = os.path.join(upload_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    image_url = f"/static/profiles/{filename}"
    
    current_user.foto_profil = image_url
    db.commit()
    db.refresh(current_user)
    
    return ApiResponse(
        status="success",
        message="Foto profil berhasil diperbarui.",
        data=UserOut.from_db(current_user).model_dump(),
    )


# ---------------------------------------------------------------------------
# DELETE /api/auth/account — Hapus akun & seluruh data pengguna
# ---------------------------------------------------------------------------
@router.delete("/account", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hapus akun pengguna beserta seluruh data terkait (CASCADE akan menghapus semua)."""
    uid = current_user.id
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Akun tidak ditemukan.",
        )
    db.delete(user)
    db.commit()
    return ApiResponse(
        status="success",
        message="Akun berhasil dihapus.",
    )


# ---------------------------------------------------------------------------
# POST /api/auth/forgot-password/send-otp — Kirim OTP reset password
# ---------------------------------------------------------------------------
@router.post("/forgot-password/send-otp", response_model=ApiResponse, status_code=status.HTTP_200_OK)
@limiter.limit("3/10minutes")
async def forgot_password_send_otp(request: Request, payload: ForgotPasswordSendOtpRequest, db: Session = Depends(get_db)):
    """
    Langkah 1 lupa password: kirim OTP ke email yang sudah terdaftar.
    Jika email tidak terdaftar → tolak (agar tidak bocorkan informasi: tampilkan pesan netral).
    """
    await verify_recaptcha(payload.captcha_token)
    # Cek apakah email terdaftar
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        # Kembalikan pesan yang sama agar tidak bocorkan info akun
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email tidak terdaftar. Silakan periksa kembali email Anda.",
        )

    # Hapus OTP reset yang belum digunakan sebelumnya
    db.query(PasswordResetOtp).filter(
        PasswordResetOtp.email == payload.email,
        PasswordResetOtp.is_used == False,
    ).delete()
    db.commit()

    # Buat OTP baru
    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)

    reset_otp = PasswordResetOtp(
        email=payload.email,
        otp_code=hash_otp(otp_code),
        is_used=False,
        is_verified=False,
        expires_at=expires_at,
    )
    db.add(reset_otp)
    db.commit()

    # Kirim email OTP dengan template reset password
    html_body = _build_reset_otp_email(user.nama_lengkap, otp_code, OTP_EXPIRE_MINUTES)
    sent = send_html_email(payload.email, "Reset Password PostureFit", html_body)

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengirim email. Coba lagi.",
        )

    return ApiResponse(
        status="success",
        message=f"Kode OTP reset password telah dikirim ke {payload.email}. Berlaku {OTP_EXPIRE_MINUTES} menit.",
        data={"email": payload.email, "expires_minutes": OTP_EXPIRE_MINUTES},
    )


# ---------------------------------------------------------------------------
# POST /api/auth/forgot-password/verify-otp — Verifikasi OTP reset password
# ---------------------------------------------------------------------------
@router.post("/forgot-password/verify-otp", response_model=ApiResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/10minutes")
def forgot_password_verify_otp(request: Request, payload: ForgotPasswordVerifyOtpRequest, db: Session = Depends(get_db)):
    """
    Langkah 2 lupa password: verifikasi kode OTP.
    Jika valid → tandai is_verified=True → user dapat lanjut ganti password.
    """
    reset_otp = (
        db.query(PasswordResetOtp)
        .filter(
            PasswordResetOtp.email == payload.email,
            PasswordResetOtp.is_used == False,
        )
        .order_by(PasswordResetOtp.created_at.desc())
        .first()
    )

    if not reset_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP tidak ditemukan. Silakan minta kode baru.",
        )

    if datetime.utcnow() > reset_otp.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kode OTP sudah kadaluarsa. Silakan minta kode baru.",
        )

    if reset_otp.otp_code != hash_otp(payload.otp_code.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kode OTP tidak valid.",
        )

    # Tandai OTP telah terverifikasi (belum digunakan, karena masih perlu reset password)
    reset_otp.is_verified = True
    db.commit()

    return ApiResponse(
        status="success",
        message="OTP berhasil diverifikasi. Silakan buat password baru.",
        data={"email": payload.email},
    )


# ---------------------------------------------------------------------------
# POST /api/auth/forgot-password/reset — Ganti password setelah OTP terverifikasi
# ---------------------------------------------------------------------------
@router.post("/forgot-password/reset", response_model=ApiResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/10minutes")
def forgot_password_reset(request: Request, payload: ForgotPasswordResetRequest, db: Session = Depends(get_db)):
    """
    Langkah 3 lupa password: ganti password setelah OTP terverifikasi.
    Memvalidasi bahwa OTP sudah diverifikasi sebelum diizinkan ganti password.
    """
    # Cek OTP yang sudah terverifikasi
    reset_otp = (
        db.query(PasswordResetOtp)
        .filter(
            PasswordResetOtp.email == payload.email,
            PasswordResetOtp.is_verified == True,
            PasswordResetOtp.is_used == False,
        )
        .order_by(PasswordResetOtp.created_at.desc())
        .first()
    )

    if not reset_otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sesi reset password tidak valid. Silakan ulangi proses dari awal.",
        )

    if datetime.utcnow() > reset_otp.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sesi reset password telah kadaluarsa. Silakan ulangi proses.",
        )

    # Cari user
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Akun tidak ditemukan.",
        )

    # Update password
    user.password_hash = hash_password(payload.new_password)

    # Tandai OTP sebagai sudah digunakan
    reset_otp.is_used = True

    db.commit()

    return ApiResponse(
        status="success",
        message="Password berhasil diubah. Silakan login dengan password baru Anda.",
        data={"email": payload.email},
    )


# ---------------------------------------------------------------------------
# Helper: Template Email OTP Reset Password
# ---------------------------------------------------------------------------
def _build_reset_otp_email(name: str, otp: str, expire_minutes: int) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
    .container {{ max-width: 520px; margin: 40px auto; background: white; border-radius: 16px;
                  box-shadow: 0 4px 24px rgba(0,0,0,0.08); overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #FF6B6B, #FF8E53); padding: 32px 24px; text-align: center; }}
    .header h1 {{ color: white; margin: 12px 0 0; font-size: 24px; font-weight: 700; }}
    .body {{ padding: 32px 24px; }}
    .body p {{ color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 16px; }}
    .otp-box {{ background: #fff5f5; border: 2px dashed #FF6B6B; border-radius: 12px;
                text-align: center; padding: 24px; margin: 24px 0; }}
    .otp-code {{ font-size: 40px; font-weight: 800; letter-spacing: 10px; color: #c62828;
                  font-family: 'Courier New', monospace; }}
    .expire {{ color: #999; font-size: 13px; margin-top: 8px; }}
    .footer {{ background: #fafafa; padding: 20px 24px; text-align: center; color: #bbb; font-size: 12px; }}
    .warning {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 12px 16px;
                border-radius: 4px; color: #795548; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🔐 PostureFit</h1>
    </div>
    <div class="body">
      <p>Halo <strong>{name}</strong>,</p>
      <p>Kami menerima permintaan untuk <strong>mereset password</strong> akun PostureFit Anda. Gunakan kode OTP di bawah ini untuk melanjutkan proses.</p>
      <div class="otp-box">
        <div class="otp-code">{otp}</div>
        <div class="expire">⏱ Berlaku selama {expire_minutes} menit</div>
      </div>
      <div class="warning">
        ⚠️ Jangan bagikan kode ini kepada siapa pun. Jika Anda tidak meminta reset password, abaikan email ini dan password Anda tidak akan berubah.
      </div>
    </div>
    <div class="footer">
      &copy; 2026 PostureFit · Semua hak dilindungi<br>
      Jaga postur, jaga kesehatan 💪
    </div>
  </div>
</body>
</html>
"""
