import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging
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


def send_push_notification(
    token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """Kirim push notifikasi ke satu device via FCM."""
    try:
        app = _get_app()
        if app is None:
            print("[FCM] Service account not configured, skipping push.")
            return False

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
        )
        response = messaging.send(message, app=app)
        print(f"[FCM] Sent to {token[:20]}...: {response}")
        return True
    except messaging.UnregisteredError:
        print(f"[FCM] Token {token[:20]}... is no longer registered.")
        return False
    except Exception as e:
        print(f"[FCM] Error sending to {token[:20]}...: {e}")
        return False


def send_push_to_user(
    db_session,
    user_id: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
):
    """Kirim push notifikasi ke SEMUA device milik user tertentu."""
    from models import FcmToken

    tokens = (
        db_session.query(FcmToken)
        .filter(FcmToken.user_id == user_id)
        .all()
    )

    for fcm in tokens:
        send_push_notification(fcm.token, title, body, data)



