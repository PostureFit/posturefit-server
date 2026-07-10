import os
from typing import Optional

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from dotenv import load_dotenv

load_dotenv()

_firebase_app = None


def _get_app():
    global _firebase_app
    if _firebase_app is None:
        try:
            _firebase_app = firebase_admin.get_app()
        except ValueError:
            cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
            if cred_path and os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def verify_google_token(id_token: str) -> Optional[dict]:
    try:
        app = _get_app()
        if app is None:
            print("[Firebase] Service account not configured, cannot verify token.")
            return None

        decoded = firebase_auth.verify_id_token(id_token, app=app)

        return {
            "uid": decoded.get("uid", ""),
            "email": decoded.get("email", ""),
            "name": decoded.get("name", ""),
            "picture": decoded.get("picture"),
        }
    except Exception as e:
        print(f"[Firebase] Token verification failed: {e}")
        return None