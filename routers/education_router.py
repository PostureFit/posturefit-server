"""
education_router.py — /api/education endpoints.

Alur data:
  MongoDB Atlas (Scraper Riqo)
       ↓  [sync_service — otomatis + manual]
   MySQL database (education_articles)
       ↓
   Endpoint ini (/api/education)
       ↓
   Aplikasi Flutter

Filter yang tersedia:
  ?kategori=postur          → filter satu kategori
  ?search=kata_kunci        → pencarian judul & ringkasan
  ?limit=10&offset=0        → pagination
"""

import json
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Query, status
# pyrefly: ignore [missing-import]
from sqlalchemy import or_
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import EducationArticle, User
from schemas import EducationOut, ApiResponse
from auth import get_current_user
from sync_service import sync_education_from_mongo, ALLOWED_CATEGORIES

router = APIRouter(prefix="/api/education", tags=["Education"])


# ---------------------------------------------------------------------------
# GET /api/education  —  Baca dari MySQL (sudah disinkronisasi dari MongoDB)
# ---------------------------------------------------------------------------
@router.get("", status_code=status.HTTP_200_OK)
def get_education_list(
    kategori: Optional[str] = Query(None, description="Filter kategori (postur, kebugaran, nutrisi, dll.)"),
    search:   Optional[str] = Query(None, description="Cari berdasarkan judul atau ringkasan"),
    limit:    int           = Query(20,  ge=1, le=100, description="Jumlah artikel per halaman"),
    offset:   int           = Query(0,   ge=0,         description="Mulai dari artikel ke-n"),
    db: Session = Depends(get_db),
):
    """
    Mengembalikan daftar artikel edukasi dari MySQL untuk Flutter.
    Data MySQL sudah disinkronisasi secara berkala dari MongoDB Atlas.

    Filter opsional:
    - `?kategori=postur`           → hanya artikel postur
    - `?search=ergonomis`          → cari kata dalam judul / ringkasan
    - `?limit=10&offset=0`         → pagination
    """
    query = db.query(EducationArticle)

    # ── Filter: Kategori ──────────────────────────────────────────────────
    if kategori:
        kategori_lower = kategori.strip().lower()
        query = query.filter(EducationArticle.kategori == kategori_lower)

    # ── Filter: Pencarian teks bebas (judul + ringkasan) ─────────────────
    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(
                EducationArticle.judul.ilike(keyword),
                EducationArticle.ringkasan.ilike(keyword),
            )
        )

    # ── Hitung total sebelum pagination ───────────────────────────────────
    total = query.count()

    # ── Urutan + Pagination ───────────────────────────────────────────────
    articles = (
        query
        .order_by(EducationArticle.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not articles:
        return ApiResponse(
            status="success",
            message=(
                "Tidak ada artikel yang cocok dengan filter."
                if (kategori or search)
                else "Belum ada data. Coba lakukan sinkronisasi terlebih dahulu di /api/education/sync."
            ),
            data={
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": [],
            },
        )

    data = [EducationOut.from_db(a).model_dump() for a in articles]
    return ApiResponse(
        status="success",
        message="",
        data={
            "total":  total,
            "limit":  limit,
            "offset": offset,
            "items":  data,
        },
    )


# ---------------------------------------------------------------------------
# GET /api/education/categories  —  Daftar kategori yang tersedia
# ---------------------------------------------------------------------------
@router.get("/categories", status_code=status.HTTP_200_OK)
def get_available_categories(db: Session = Depends(get_db)):
    """
    Mengembalikan daftar kategori yang benar-benar ada di database MySQL,
    beserta jumlah artikel per kategori.
    """
    # pyrefly: ignore [missing-import]
    from sqlalchemy import func

    results = (
        db.query(EducationArticle.kategori, func.count(EducationArticle.id).label("jumlah"))
        .group_by(EducationArticle.kategori)
        .order_by(func.count(EducationArticle.id).desc())
        .all()
    )

    categories = [
        {"kategori": row.kategori or "umum", "jumlah": row.jumlah}
        for row in results
    ]

    return ApiResponse(
        status="success",
        message=f"{len(categories)} kategori ditemukan.",
        data={
            "allowed_categories": sorted(ALLOWED_CATEGORIES),
            "available": categories,
        },
    )


# ---------------------------------------------------------------------------
# GET /api/education/{article_id}  —  Detail satu artikel
# ---------------------------------------------------------------------------
@router.get("/{article_id}", status_code=status.HTTP_200_OK)
def get_education_detail(
    article_id: str,
    db: Session = Depends(get_db),
):
    """Mengembalikan satu artikel edukasi berdasarkan ID."""
    article = db.query(EducationArticle).filter(EducationArticle.id == article_id).first()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artikel tidak ditemukan.",
        )

    return ApiResponse(
        status="success",
        message="",
        data=EducationOut.from_db(article).model_dump(),
    )


# ---------------------------------------------------------------------------
# POST /api/education/sync  —  Sinkronisasi manual MongoDB → MySQL
# ---------------------------------------------------------------------------
@router.post("/sync", status_code=status.HTTP_200_OK)
async def manual_sync(
    current_user: User = Depends(get_current_user),
):
    """
    Trigger sinkronisasi manual: Tarik data terbaru dari MongoDB Atlas
    dan simpan ke MySQL. Hanya bisa diakses oleh pengguna yang sudah login.

    Proses:
    1. Ambil dokumen dari MongoDB dengan filter ketat (ada judul & ringkasan)
    2. Bersihkan dan normalkan setiap field
    3. Upsert ke MySQL (tambah baru / perbarui yang sudah ada)

    Response berisi statistik:
    - added:    artikel baru yang ditambahkan
    - updated:  artikel yang diperbarui
    - skipped:  dilewati karena duplikat judul dalam batch
    - rejected: dibuang karena tidak lolos validasi (judul/ringkasan terlalu pendek, dll.)
    - errors:   gagal karena exception tak terduga
    """
    try:
        result = await sync_education_from_mongo()
        return ApiResponse(
            status="success",
            message=(
                f"Sinkronisasi berhasil! "
                f"{result['added']} artikel baru, "
                f"{result['updated']} diperbarui, "
                f"{result['rejected']} ditolak (tidak memenuhi syarat), "
                f"{result['skipped']} dilewati (duplikat)."
            ),
            data=result,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sinkronisasi gagal: {str(e)}",
        )
