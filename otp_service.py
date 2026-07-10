"""
otp_service.py — OTP Generation & Email Sending Service.

Menggunakan Firebase Admin SDK untuk membuat action link verifikasi email
dan mengirim email melalui SMTP (Gmail / relay).

Kode OTP 6 digit disimpan sementara di tabel `otp_requests` MySQL.
"""

import os
import random
import string
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Config (dari .env)
# ---------------------------------------------------------------------------
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")           # email pengirim
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")       # app password Gmail
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))


# ---------------------------------------------------------------------------
# Generate OTP
# ---------------------------------------------------------------------------
def generate_otp(length: int = 6) -> str:
    """Buat kode OTP numerik acak."""
    return "".join(random.choices(string.digits, k=length))


# ---------------------------------------------------------------------------
# Send OTP via SMTP
# ---------------------------------------------------------------------------
def send_otp_email(to_email: str, otp_code: str, user_name: str = "Pengguna") -> bool:
    """
    Kirim email berisi kode OTP ke alamat pengirim.
    Mengembalikan True jika berhasil, False jika gagal.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        # Mode development: print ke console saja
        print(f"[OTP DEV MODE] Kode OTP untuk {to_email}: {otp_code}")
        return True

    subject = "Kode Verifikasi PostureFit"
    html_body = _build_email_html(user_name, otp_code, OTP_EXPIRE_MINUTES)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"PostureFit <{SMTP_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        print(f"[OTP] Email terkirim ke {to_email}")
        return True
    except Exception as e:
        print(f"[OTP ERROR] Gagal kirim email ke {to_email}: {e}")
        return False


# ---------------------------------------------------------------------------
# HTML Email Template
# ---------------------------------------------------------------------------
def _build_email_html(name: str, otp: str, expire_minutes: int) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; }}
    .container {{ max-width: 520px; margin: 40px auto; background: white; border-radius: 16px;
                  box-shadow: 0 4px 24px rgba(0,0,0,0.08); overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #4CAF50, #2196F3); padding: 32px 24px; text-align: center; }}
    .header img {{ width: 60px; height: 60px; border-radius: 16px; }}
    .header h1 {{ color: white; margin: 12px 0 0; font-size: 24px; font-weight: 700; }}
    .body {{ padding: 32px 24px; }}
    .body p {{ color: #555; font-size: 15px; line-height: 1.6; margin: 0 0 16px; }}
    .otp-box {{ background: #f0f9f0; border: 2px dashed #4CAF50; border-radius: 12px;
                text-align: center; padding: 24px; margin: 24px 0; }}
    .otp-code {{ font-size: 40px; font-weight: 800; letter-spacing: 10px; color: #2e7d32;
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
      <h1>🏋️ PostureFit</h1>
    </div>
    <div class="body">
      <p>Halo <strong>{name}</strong>,</p>
      <p>Terima kasih telah mendaftar di <strong>PostureFit</strong>! Gunakan kode verifikasi di bawah ini untuk menyelesaikan proses pendaftaran akun Anda.</p>
      <div class="otp-box">
        <div class="otp-code">{otp}</div>
        <div class="expire">⏱ Berlaku selama {expire_minutes} menit</div>
      </div>
      <div class="warning">
        ⚠️ Jangan bagikan kode ini kepada siapa pun, termasuk tim PostureFit.
      </div>
      <p style="margin-top: 24px;">Jika Anda tidak merasa mendaftar, abaikan email ini.</p>
    </div>
    <div class="footer">
      &copy; 2026 PostureFit · Semua hak dilindungi<br>
      Jaga postur, jaga kesehatan 💪
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Welcome Email & Generic HTML Email
# ---------------------------------------------------------------------------
def send_html_email(to_email: str, subject: str, html_body: str) -> bool:
    """Kirim email HTML umum (seperti Welcome Email)."""
    if not SMTP_USER or not SMTP_PASSWORD:
        print(f"[DEV MODE] Email to {to_email} | Subject: {subject}")
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"PostureFit <{SMTP_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[SMTP ERROR] {e}")
        return False

def _build_welcome_email(name: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: sans-serif; line-height: 1.6; color: #333; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
    h2 {{ color: #4CAF50; }}
  </style>
</head>
<body>
  <div class="container">
    <h2>Selamat Datang di PostureFit, {name}! 🎉</h2>
    <p>Terima kasih telah bergabung bersama kami. Akun Anda berhasil dibuat dan nomor handphone Anda telah diverifikasi.</p>
    <p>Mari mulai perjalanan kebugaran Anda dan perbaiki postur tubuh demi masa depan yang lebih sehat!</p>
    <br>
    <p>Salam hangat,<br><b>Tim PostureFit</b></p>
  </div>
</body>
</html>
"""
