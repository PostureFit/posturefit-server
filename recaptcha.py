import httpx
import os
from fastapi import HTTPException, status

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def verify_recaptcha(captcha_token: str, required: bool = False) -> bool:
    # Flutter mobile tidak menggunakan CAPTCHA, skip verifikasi jika token kosong
    if not captcha_token or not captcha_token.strip():
        if required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verifikasi CAPTCHA gagal. Silakan coba lagi.",
            )
        return True

    secret_key = os.getenv("RECAPTCHA_SECRET_KEY", "")

    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="reCAPTCHA tidak dikonfigurasi. Hubungi administrator.",
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            RECAPTCHA_VERIFY_URL,
            data={"secret": secret_key, "response": captcha_token},
        )
        result = resp.json()

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verifikasi CAPTCHA gagal. Silakan coba lagi.",
        )
    return True
