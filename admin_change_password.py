import os
from pathlib import Path

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Request, Form
# pyrefly: ignore [missing-import]
from fastapi.responses import HTMLResponse, RedirectResponse
# pyrefly: ignore [missing-import]
from fastapi.templating import Jinja2Templates
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext

from database import SessionLocal
from models import AdminUser
from admin_auth import _SESSION_TOKEN, _BOOT_TOKEN

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# pyrefly: ignore [missing-import]
import sqladmin

# Gunakan path absolut agar template ditemukan apapun working directory-nya
_BASE_DIR  = Path(__file__).resolve().parent
sqladmin_tpl_dir = Path(sqladmin.__file__).parent / "templates"
templates  = Jinja2Templates(directory=[str(_BASE_DIR / "templates"), str(sqladmin_tpl_dir)])

# Tambahkan mock get_flashed_messages agar layout.html yang meng-include flash.html tidak error
def get_flashed_messages(request: Request):
    return []
templates.env.globals["get_flashed_messages"] = get_flashed_messages

router     = APIRouter()


def _is_authenticated(request: Request) -> bool:
    """Cek session yang sama seperti AdminAuthBackend.authenticate()."""
    return (
        request.session.get("token")      == _SESSION_TOKEN and
        request.session.get("boot_token") == _BOOT_TOKEN
    )


@router.get("/admin-cp/profile", response_class=HTMLResponse, include_in_schema=False)
async def admin_profile_page(request: Request):
    """Tampilkan profil admin."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    username = request.session.get("admin_username", "")
    db = SessionLocal()
    try:
        db_admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        
        # Mock objek `admin` bawaan SQLAdmin yang dibutuhkan oleh base.html (untuk title & favicon)
        class MockSQLAdmin:
            title = "PostureFit Admin"
            favicon_url = None
            
        return templates.TemplateResponse(
            request=request,
            name="sqladmin/profile.html",
            context={"admin": MockSQLAdmin(), "current_admin": db_admin, "title": "Profil Saya"},
        )
    finally:
        db.close()


@router.get("/admin-cp/education-analytics", response_class=HTMLResponse, include_in_schema=False)
async def education_analytics_page(request: Request):
    """Tampilkan halaman analitik artikel edukasi dengan Chart.js."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    class MockSQLAdmin:
        title = "PostureFit Admin"
        favicon_url = None

    return templates.TemplateResponse(
        request=request,
        name="sqladmin/education_analytics.html",
        context={"admin": MockSQLAdmin(), "title": "Analitik Edukasi"},
    )


@router.get("/admin-cp/change-password", response_class=HTMLResponse, include_in_schema=False)
async def change_password_page(request: Request):
    """Tampilkan form ganti password."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    username = request.session.get("admin_username", "")
    return templates.TemplateResponse(
        request=request,
        name="sqladmin/change_password.html",
        context={"username": username, "error": None, "success": None},
    )


@router.post("/admin-cp/change-password", response_class=HTMLResponse, include_in_schema=False)
async def change_password_action(
    request: Request,
    current_password:  str = Form(...),
    new_password:      str = Form(...),
    confirm_password:  str = Form(...),
):
    """Proses ganti password admin."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/admin/login", status_code=302)

    username = request.session.get("admin_username", "")

    def render(error=None, success=None):
        return templates.TemplateResponse(
            request=request,
            name="sqladmin/change_password.html",
            context={"username": username, "error": error, "success": success},
        )

    # Validasi input
    if not current_password or not new_password or not confirm_password:
        return render(error="Semua field wajib diisi.")

    if new_password != confirm_password:
        return render(error="Password baru dan konfirmasi tidak cocok.")

    if len(new_password) < 8:
        return render(error="Password baru minimal 8 karakter.")

    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if not admin:
            return render(error="Akun admin tidak ditemukan.")

        if not _pwd_context.verify(current_password, admin.password_hash):
            return render(error="Password saat ini tidak benar.")

        admin.password_hash = _pwd_context.hash(new_password)
        db.commit()
    finally:
        db.close()

    return render(success="Password berhasil diubah!")
