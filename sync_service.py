"""
sync_service.py — Layanan sinkronisasi data edukasi dari MongoDB Atlas → MySQL.

Alur:
  1. Terhubung ke MongoDB Atlas (database scraper_fit, koleksi edukasi_olahraga).
  2. Mengambil dokumen VALID dari MongoDB dengan filter ketat:
     - Judul tidak kosong (minimal 5 karakter)
     - Memiliki ringkasan / konten deskriptif
     - Kategori termasuk dalam daftar kategori yang diizinkan
     - Gambar memiliki URL yang valid (opsional, fallback ke placeholder)
  3. Membersihkan (clean) setiap field sebelum disimpan ke MySQL.
  4. Menyimpan/memperbarui (upsert) dokumen ke tabel 'education_articles' di MySQL.
  5. Dokumen yang sudah ada (berdasarkan mongo_id) akan diperbarui, bukan diduplikasi.
"""

import os
import re
import json
import logging
from datetime import datetime
from urllib.parse import urlparse

# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database import SessionLocal
from models import EducationArticle, User, Notification, NotificationPreference
from fcm_service import send_push_to_user

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Koneksi MongoDB
# ---------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "") or ""
_HAS_MONGO = bool(MONGO_URI)
if not _HAS_MONGO:
    logger.warning("[SyncService] MONGO_URI tidak diatur — sinkronisasi MongoDB dilewati.")


_mongo_client = None


def _get_mongo_client() -> AsyncIOMotorClient:
    global _mongo_client
    if not _HAS_MONGO:
        raise RuntimeError("MONGO_URI tidak diatur — koneksi MongoDB tidak tersedia.")
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(MONGO_URI)
    return _mongo_client


# ---------------------------------------------------------------------------
# Konstanta Filter & Normalisasi
# ---------------------------------------------------------------------------

# Kategori yang diizinkan masuk ke MySQL (case-insensitive matching)
ALLOWED_CATEGORIES = {
    "postur",
    "kebugaran",
    "olahraga",
    "nutrisi",
    "gizi",
    "kesehatan",
    "workout",
    "latihan",
    "ergonomi",
    "tidur",
    "hidrasi",
    "umum",
}

# Mapping normalisasi kategori: nilai mentah → nilai standar
CATEGORY_NORMALIZE = {
    "fitness":      "kebugaran",
    "exercise":     "olahraga",
    "sport":        "olahraga",
    "sport fitness":"kebugaran",
    "nutrition":    "nutrisi",
    "diet":         "nutrisi",
    "health":       "kesehatan",
    "sleep":        "tidur",
    "hydration":    "hidrasi",
    "posture":      "postur",
    "ergonomics":   "ergonomi",
    "general":      "umum",
}

# Panjang minimum field wajib
MIN_JUDUL_LENGTH      = 5
MIN_RINGKASAN_LENGTH  = 20

# Gambar placeholder jika URL tidak valid
PLACEHOLDER_IMAGE = ""


# ---------------------------------------------------------------------------
# Helper: Validasi & Pembersihan
# ---------------------------------------------------------------------------

def _clean_text(value, default: str = "") -> str:
    """Bersihkan whitespace berlebih dan karakter tidak terlihat dari string."""
    if not value or not isinstance(value, str):
        return default
    # Hapus karakter kontrol (kecuali newline)
    cleaned = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", value)
    # Normalkan spasi berlebih
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    return cleaned


def _normalize_category(raw_kategori) -> str:
    """
    Normalkan kategori ke salah satu nilai standar.
    Jika tidak dikenal, kembalikan 'umum'.
    """
    if not raw_kategori or not isinstance(raw_kategori, str):
        return "umum"

    lower = raw_kategori.strip().lower()

    # Cek mapping eksplisit dulu
    if lower in CATEGORY_NORMALIZE:
        return CATEGORY_NORMALIZE[lower]

    # Cek apakah sudah dalam daftar allowed langsung
    if lower in ALLOWED_CATEGORIES:
        return lower

    # Coba partial match (misal "olahraga rutin" → "olahraga")
    for allowed in ALLOWED_CATEGORIES:
        if allowed in lower:
            return allowed

    return "umum"


def _is_valid_url(url: str) -> bool:
    """Kembalikan True jika url adalah URL HTTP/HTTPS yang valid secara format."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _clean_image_url(raw_url) -> str:
    """Validasi URL gambar; kembalikan URL asli jika valid, kosong jika tidak."""
    url = _clean_text(raw_url)
    if _is_valid_url(url):
        return url
    return PLACEHOLDER_IMAGE


def _clean_tips(raw_tips) -> str:
    """
    Parsing dan bersihkan field 'tips'.
    Hanya simpan tips yang berupa string non-kosong.
    Kembalikan JSON string (list of str).
    """
    tips_list = []

    if isinstance(raw_tips, list):
        for item in raw_tips:
            item_clean = _clean_text(item)
            if item_clean:
                tips_list.append(item_clean)
    elif isinstance(raw_tips, str):
        # Coba parse sebagai JSON
        try:
            parsed = json.loads(raw_tips)
            if isinstance(parsed, list):
                for item in parsed:
                    item_clean = _clean_text(item)
                    if item_clean:
                        tips_list.append(item_clean)
            elif isinstance(parsed, str):
                clean = _clean_text(parsed)
                if clean:
                    tips_list.append(clean)
        except json.JSONDecodeError:
            # Bukan JSON, anggap sebagai satu tip
            clean = _clean_text(raw_tips)
            if clean:
                tips_list.append(clean)

    return json.dumps(tips_list, ensure_ascii=False)


def _parse_updated_at(raw) -> datetime:
    """Parse field updated_at ke objek datetime; fallback ke utcnow()."""
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
    return datetime.utcnow()


def _is_valid_document(doc: dict) -> tuple[bool, str]:
    """
    Validasi apakah dokumen MongoDB layak dimasukkan ke MySQL.

    Return:
        (True, "")              → dokumen valid
        (False, "alasan skip") → dokumen dilewati
    """
    # 1. Harus memiliki id
    if not doc.get("id"):
        return False, "tidak ada field 'id'"

    # 2. Judul harus ada dan cukup panjang
    judul = _clean_text(doc.get("judul", ""))
    if len(judul) < MIN_JUDUL_LENGTH:
        return False, f"judul terlalu pendek: '{judul}'"

    # 3. Ringkasan harus ada dan informatif
    ringkasan = _clean_text(doc.get("ringkasan", ""))
    if len(ringkasan) < MIN_RINGKASAN_LENGTH:
        return False, f"ringkasan terlalu pendek atau kosong: '{ringkasan[:30]}...'"

    # 4. Tidak boleh duplikat judul yang persis sama dalam satu batch
    # (Ditangani di level caller dengan set tracking)

    return True, ""


# ---------------------------------------------------------------------------
# Fungsi Utama: Sinkronisasi MongoDB → MySQL
# ---------------------------------------------------------------------------
async def sync_education_from_mongo() -> dict:
    """
    Tarik artikel VALID dari MongoDB Atlas lalu simpan ke MySQL.
    Dokumen difilter, dibersihkan, dan dinormalisasi sebelum disimpan.

    Return dict berisi statistik hasil sinkronisasi.
    """
    if not _HAS_MONGO:
        return {"status": "skipped", "message": "MONGO_URI tidak diatur, sinkronisasi dilewati.", "synced_at": ""}
    client = _get_mongo_client()
    collection = client.scraper_fit.edukasi_olahraga

    added    = 0
    updated  = 0
    skipped  = 0
    errors   = 0
    rejected = 0  # dokumen yang gagal validasi

    seen_juduls: set[str] = set()  # tracking judul agar tidak duplikat dalam batch

    db: Session = SessionLocal()
    try:
        # ── Query ke MongoDB: ambil hanya dokumen yang memiliki judul & ringkasan ──
        mongo_filter = {
            "judul":     {"$exists": True, "$ne": "", "$ne": None},
            "ringkasan": {"$exists": True, "$ne": "", "$ne": None},
        }

        cursor = collection.find(mongo_filter).sort("updated_at", -1)

        async for doc in cursor:
            try:
                # ── Validasi dokumen ──────────────────────────────────────────
                valid, reason = _is_valid_document(doc)
                if not valid:
                    logger.debug(f"[SyncService] Dokumen dilewati — {reason}")
                    rejected += 1
                    continue

                mongo_id = str(doc["id"])

                # ── Bersihkan & normalkan semua field ─────────────────────────
                judul     = _clean_text(doc.get("judul", ""), default="Tanpa Judul")
                ringkasan = _clean_text(doc.get("ringkasan", ""), default="")
                gambar    = _clean_image_url(doc.get("gambar"))
                kategori  = _normalize_category(doc.get("kategori"))
                sumber    = _clean_text(doc.get("sumber", ""), default="Scraper_Fit")
                tips_str  = _clean_tips(doc.get("tips", []))
                link      = _clean_text(doc.get("link_direct", doc.get("link", "")))
                updated_at = _parse_updated_at(doc.get("updated_at"))

                # ── Cek duplikat judul dalam batch yang sedang diproses ───────
                judul_key = judul.lower().strip()
                if judul_key in seen_juduls:
                    logger.debug(f"[SyncService] Skip duplikat judul: '{judul}'")
                    skipped += 1
                    continue
                seen_juduls.add(judul_key)

                # ── Upsert ke MySQL ───────────────────────────────────────────
                existing = db.query(EducationArticle).filter(
                    EducationArticle.id == mongo_id
                ).first()

                if existing:
                    existing.judul       = judul
                    existing.ringkasan   = ringkasan
                    existing.gambar      = gambar
                    existing.kategori    = kategori
                    existing.sumber      = sumber
                    existing.tips        = tips_str
                    existing.link_direct = link
                    existing.updated_at  = updated_at
                    updated += 1
                else:
                    article = EducationArticle(
                        id          = mongo_id,
                        judul       = judul,
                        ringkasan   = ringkasan,
                        gambar      = gambar,
                        kategori    = kategori,
                        sumber      = sumber,
                        tips        = tips_str,
                        link_direct = link,
                        updated_at  = updated_at,
                    )
                    db.add(article)
                    added += 1

                    # Notifikasi artikel baru — hanya untuk user yang mengaktifkan education
                    users = db.query(User.id).all()
                    for u in users:
                        pref = db.query(NotificationPreference).filter(
                            NotificationPreference.user_id == u[0]
                        ).first()
                        if pref is None or pref.education_enabled:
                            notif = Notification(
                                user_id=u[0],
                                title=f"Artikel Baru: {judul}",
                                message=ringkasan[:100] + ("..." if len(ringkasan) > 100 else ""),
                                type="education",
                            )
                            db.add(notif)
                            send_push_to_user(db, u[0], notif.title, notif.message)

            except Exception as e:
                logger.error(f"[SyncService] Gagal memproses dokumen: {e}", exc_info=True)
                errors += 1
                continue

        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"[SyncService] Error koneksi MongoDB: {e}", exc_info=True)
        raise e
    finally:
        db.close()

    result = {
        "status":          "success",
        "added":           added,
        "updated":         updated,
        "skipped":         skipped,
        "rejected":        rejected,   # dokumen gagal validasi
        "errors":          errors,
        "total_processed": added + updated + skipped + rejected,
        "synced_at":       datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    logger.info(f"[SyncService] Sinkronisasi selesai: {result}")
    return result
