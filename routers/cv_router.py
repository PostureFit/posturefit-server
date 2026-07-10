import json
import os
import uuid
import mimetypes
from datetime import datetime
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from database import get_db
from models import User, CvAssessment
from schemas import (
    VitalityAssessmentRequest,
    AssessmentResponse,
    AssessmentResult,
    AssessmentHistoryItem,
    ImageAnalysisResponse,
    ApiResponse,
)
from auth import get_current_user
from fitness_analysis import calculate_bmi, calculate_whtr
from saw_engine import calculate_saw
from pose_detector import analyze_pose, draw_pose_skeleton
from llm_service import generate_recommendation as llm_recommendation

router = APIRouter(prefix="/api/assessment", tags=["Vitality Assessment"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


# ---------------------------------------------------------------------------
# POST /api/assessment/analyze-image — MediaPipe Pose detection
# ---------------------------------------------------------------------------
@router.post(
    "/analyze-image",
    response_model=ImageAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_image(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipe file {file.content_type} tidak didukung. Gunakan JPG, PNG, atau WebP.",
        )

    contents = await file.read()
    file_size = len(contents)
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File gambar kosong.")
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File terlalu besar. Maksimal 5MB.")

    image_bytes = contents

    result = analyze_pose(image_bytes)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    scan_dir = "static/scans"
    os.makedirs(scan_dir, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"scan_{uuid.uuid4().hex[:8]}_{int(datetime.utcnow().timestamp())}.{ext}"
    filepath = os.path.join(scan_dir, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    image_url = f"/static/scans/{filename}"

    # Generate annotated image with skeleton
    annotated_image_url = ""
    if result.get("landmarks") and result.get("connections"):
        annotated_filename = filename.replace(f".{ext}", f"_annotated.{ext}")
        annotated_filepath = os.path.join(scan_dir, annotated_filename)
        draw_pose_skeleton(
            image_bytes,
            result["landmarks"],
            result["connections"],
            annotated_filepath,
        )
        annotated_image_url = f"/static/scans/{annotated_filename}"

    return ImageAnalysisResponse(
        status="success",
        wsr=result["wsr"],
        shoulder_balance=result["shoulder_balance"],
        posture_score=result["posture_score"],
        landmarks=result["landmarks"],
        connections=result["connections"],
        img_width=result["img_width"],
        img_height=result["img_height"],
        image_url=image_url,
        annotated_image_url=annotated_image_url,
    )


# ---------------------------------------------------------------------------
# POST /api/assessment/generate
# ---------------------------------------------------------------------------
@router.post(
    "/generate",
    response_model=AssessmentResponse,
    status_code=status.HTTP_200_OK,
)
def generate_recommendation(
    payload: VitalityAssessmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User tidak ditemukan. Silakan login terlebih dahulu.",
        )

    bmi  = calculate_bmi(payload.berat_kg, payload.tinggi_cm)
    whtr = calculate_whtr(payload.lingkar_perut_cm, payload.tinggi_cm)

    wsr_val = payload.wsr or 0.0

    kategori_tubuh, rekomendasi_teks, saw_scores = calculate_saw(
        bmi=bmi,
        whtr=whtr,
        umur=payload.umur,
        lingkar_perut_cm=payload.lingkar_perut_cm,
        wsr=wsr_val,
    )

    user.umur             = payload.umur
    user.tinggi_cm        = payload.tinggi_cm
    user.berat_kg         = payload.berat_kg
    user.lingkar_perut_cm = payload.lingkar_perut_cm
    user.bmi_terkini      = bmi
    user.fokus_utama      = kategori_tubuh
    if payload.fokus_pilihan:
        user.fokus_pilihan = payload.fokus_pilihan

    lingkungan = payload.lingkungan or "Rumah"
    analisis_llm = llm_recommendation(
        kategori=kategori_tubuh,
        bmi=bmi,
        wsr=wsr_val,
        posture_score=payload.posture_score or 50.0,
        shoulder_balance=payload.shoulder_balance or 0.0,
        fokus=payload.fokus_pilihan or "Pertahankan",
        lingkungan=lingkungan,
    )

    # Generate annotated_image_url from image_url
    def _annotated_url(url):
        if not url:
            return ""
        base, ext = os.path.splitext(url)
        return f"{base}_annotated{ext}"

    new_scan = CvAssessment(
        user_id=uid,
        image_url=payload.image_url or "",
        tinggi_cm=payload.tinggi_cm,
        berat_kg=payload.berat_kg,
        lingkar_perut_cm=payload.lingkar_perut_cm,
        umur=payload.umur,
        bmi_kalkulasi=bmi,
        kategori_tubuh=kategori_tubuh,
        rekomendasi=rekomendasi_teks,
        saw_scores=json.dumps(saw_scores),
        wsr=wsr_val if wsr_val > 0 else None,
        posture_score=payload.posture_score,
        shoulder_balance=payload.shoulder_balance,
        analisis_llm=json.dumps(analisis_llm) if analisis_llm else None,
        annotated_image_url=_annotated_url(payload.image_url),
    )
    db.add(new_scan)
    db.commit()
    db.refresh(new_scan)

    return AssessmentResponse(
        data=AssessmentResult(
            bmi=bmi,
            kategori_tubuh=kategori_tubuh,
            rekomendasi=rekomendasi_teks,
            saw_scores=saw_scores,
            wsr=wsr_val,
            posture_score=payload.posture_score,
            analisis_llm=analisis_llm,
            image_url=payload.image_url or None,
        )
    )


# ---------------------------------------------------------------------------
# GET /api/assessment/history
# ---------------------------------------------------------------------------
@router.get("/history", status_code=status.HTTP_200_OK)
def get_assessment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id

    assessments = (
        db.query(CvAssessment)
        .filter(CvAssessment.user_id == uid)
        .order_by(CvAssessment.tanggal_scan.desc())
        .all()
    )

    results = [
        AssessmentHistoryItem(
            id=a.id,
            tanggal_scan=a.tanggal_scan.isoformat() if a.tanggal_scan else None,
            image_url=a.image_url,
            tinggi_cm=float(a.tinggi_cm) if a.tinggi_cm else None,
            berat_kg=float(a.berat_kg) if a.berat_kg else None,
            bmi_kalkulasi=float(a.bmi_kalkulasi) if a.bmi_kalkulasi else None,
            kategori_tubuh=a.kategori_tubuh,
            rekomendasi=a.rekomendasi,
        ).model_dump()
        for a in assessments
    ]

    return ApiResponse(status="success", message="", data=results)


# ---------------------------------------------------------------------------
# GET /api/assessment/latest
# ---------------------------------------------------------------------------
@router.get("/latest", status_code=status.HTTP_200_OK)
def get_latest_assessment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id

    latest = (
        db.query(CvAssessment)
        .filter(CvAssessment.user_id == uid)
        .order_by(CvAssessment.tanggal_scan.desc())
        .first()
    )

    if not latest:
        return ApiResponse(
            status="success",
            message="Belum ada hasil assessment.",
            data=None,
        )

    return ApiResponse(
        status="success",
        message="",
        data=AssessmentHistoryItem(
            id=latest.id,
            tanggal_scan=latest.tanggal_scan.isoformat() if latest.tanggal_scan else None,
            image_url=latest.image_url,
            tinggi_cm=float(latest.tinggi_cm) if latest.tinggi_cm else None,
            berat_kg=float(latest.berat_kg) if latest.berat_kg else None,
            bmi_kalkulasi=float(latest.bmi_kalkulasi) if latest.bmi_kalkulasi else None,
            kategori_tubuh=latest.kategori_tubuh,
            rekomendasi=latest.rekomendasi,
        ).model_dump(),
    )