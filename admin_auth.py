import uuid
# pyrefly: ignore [missing-import]
from sqladmin.authentication import AuthenticationBackend
# pyrefly: ignore [missing-import]
from starlette.requests import Request
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext
# pyrefly: ignore [missing-import]
from fastapi import HTTPException

from database import SessionLocal
from models import AdminUser
from recaptcha import verify_recaptcha

# Bcrypt context untuk verifikasi password
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token yang disimpan di session sebagai tanda sudah login
_SESSION_TOKEN = "pf_admin_authenticated"

# Boot token — dibuat baru setiap server start/restart.
# Cookie dari sesi sebelumnya otomatis invalid karena boot_token tidak cocok.
_BOOT_TOKEN = str(uuid.uuid4())


class AdminAuthBackend(AuthenticationBackend):
    """Session-based authentication menggunakan tabel admin_users di database."""

    async def login(self, request: Request) -> bool:
        """Dipanggil saat POST /admin/login — validasi username & password."""
        form = await request.form()
        username = form.get("username", "").strip()
        password = form.get("password", "")

        if not username or not password:
            return False

        # Verifikasi reCAPTCHA
        captcha_token = form.get("g-recaptcha-response", "")
        try:
            await verify_recaptcha(captcha_token)
        except HTTPException:
            return False

        db = SessionLocal()
        try:
            admin = (
                db.query(AdminUser)
                .filter(
                    AdminUser.username == username,
                    AdminUser.is_active == True,
                )
                .first()
            )

            # MySQL default collation bersifat case-insensitive (admin == Admin).
            # Lakukan perbandingan eksakta di Python agar case-sensitive.
            if admin and admin.username == username and _pwd_context.verify(password, admin.password_hash):
                # Simpan token, boot_token, & username ke session
                request.session["token"]          = _SESSION_TOKEN
                request.session["boot_token"]     = _BOOT_TOKEN
                request.session["admin_username"] = admin.username
                return True

        finally:
            db.close()

        return False

    async def logout(self, request: Request) -> bool:
        """Dipanggil saat GET /admin/logout — hapus session."""
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Dipanggil setiap request admin — periksa token & boot_token session."""
        token      = request.session.get("token")
        boot_token = request.session.get("boot_token")
        # Kedua token harus cocok: auth token DAN boot token sesi ini
        return token == _SESSION_TOKEN and boot_token == _BOOT_TOKEN
