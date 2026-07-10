"""
create_reset_otp_table.py — Script migrasi untuk membuat tabel password_reset_otps.

Jalankan sekali: python create_reset_otp_table.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base
from models import PasswordResetOtp  # noqa: F401 — import cukup agar tabel diregistrasi

def main():
    print("Membuat tabel 'password_reset_otps' (jika belum ada)...")
    # create_all hanya membuat tabel yang belum ada; tidak menghapus yang sudah ada.
    Base.metadata.create_all(bind=engine, tables=[PasswordResetOtp.__table__])
    print("✅ Tabel 'password_reset_otps' berhasil dibuat atau sudah ada.")

if __name__ == "__main__":
    main()
