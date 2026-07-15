import logging
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import DailyWorkoutPlan, WorkoutTask, User
from schemas import ApiResponse
from auth import get_current_user

logger = logging.getLogger("posturfit")

router = APIRouter(prefix="/api/workout-plan", tags=["Workout Plan"])


class WorkoutTaskCreate(BaseModel):
    nama_latihan: str
    target_otot: Optional[str] = None
    set_reps: Optional[str] = None


class WorkoutPlanCreate(BaseModel):
    tanggal_rencana: date
    tema_latihan: Optional[str] = None
    target_kalori: Optional[int] = None
    estimasi_menit: Optional[int] = None
    tasks: List[WorkoutTaskCreate] = []


class WorkoutTaskOut(BaseModel):
    id: str
    nama_latihan: str
    target_otot: Optional[str] = None
    set_reps: Optional[str] = None
    is_completed: bool

    class Config:
        from_attributes = True


class WorkoutPlanOut(BaseModel):
    id: str
    tanggal_rencana: date
    tema_latihan: Optional[str] = None
    target_kalori: Optional[int] = None
    estimasi_menit: Optional[int] = None
    tasks: List[WorkoutTaskOut] = []

    class Config:
        from_attributes = True


@router.get("", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def get_workout_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    plans = (
        db.query(DailyWorkoutPlan)
        .filter(DailyWorkoutPlan.user_id == uid)
        .order_by(DailyWorkoutPlan.tanggal_rencana.desc())
        .all()
    )
    data = []
    for plan in plans:
        plan_out = WorkoutPlanOut(
            id=plan.id,
            tanggal_rencana=plan.tanggal_rencana,
            tema_latihan=plan.tema_latihan,
            target_kalori=plan.target_kalori,
            estimasi_menit=plan.estimasi_menit,
            tasks=[WorkoutTaskOut.model_validate(t) for t in plan.tasks],
        )
        data.append(plan_out.model_dump())

    return ApiResponse(
        status="success",
        message=f"{len(data)} rencana latihan ditemukan.",
        data=data,
    )


@router.get("/{plan_id}", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def get_workout_plan_detail(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    plan = (
        db.query(DailyWorkoutPlan)
        .filter(DailyWorkoutPlan.id == plan_id, DailyWorkoutPlan.user_id == uid)
        .first()
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rencana latihan tidak ditemukan.",
        )

    data = WorkoutPlanOut(
        id=plan.id,
        tanggal_rencana=plan.tanggal_rencana,
        tema_latihan=plan.tema_latihan,
        target_kalori=plan.target_kalori,
        estimasi_menit=plan.estimasi_menit,
        tasks=[WorkoutTaskOut.model_validate(t) for t in plan.tasks],
    ).model_dump()

    return ApiResponse(
        status="success",
        message="Detail rencana latihan ditemukan.",
        data=data,
    )


@router.post("", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_workout_plan(
    payload: WorkoutPlanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id

    try:
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User tidak ditemukan.",
            )

        plan = DailyWorkoutPlan(
            user_id=uid,
            tanggal_rencana=payload.tanggal_rencana,
            tema_latihan=payload.tema_latihan,
            target_kalori=payload.target_kalori,
            estimasi_menit=payload.estimasi_menit,
        )
        db.add(plan)
        db.flush()

        for task_data in payload.tasks:
            task = WorkoutTask(
                plan_id=plan.id,
                nama_latihan=task_data.nama_latihan,
                target_otot=task_data.target_otot,
                set_reps=task_data.set_reps,
            )
            db.add(task)

        db.commit()
        db.refresh(plan)

        data = WorkoutPlanOut(
            id=plan.id,
            tanggal_rencana=plan.tanggal_rencana,
            tema_latihan=plan.tema_latihan,
            target_kalori=plan.target_kalori,
            estimasi_menit=plan.estimasi_menit,
            tasks=[WorkoutTaskOut.model_validate(t) for t in plan.tasks],
        ).model_dump()

        return ApiResponse(
            status="success",
            message="Rencana latihan berhasil dibuat.",
            data=data,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[WorkoutPlan] Gagal buat rencana user %s: %s", uid, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal membuat rencana latihan. Silakan coba lagi.",
        )


@router.patch("/{plan_id}/tasks/{task_id}", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def update_task_status(
    plan_id: str,
    task_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id

    plan = (
        db.query(DailyWorkoutPlan)
        .filter(DailyWorkoutPlan.id == plan_id, DailyWorkoutPlan.user_id == uid)
        .first()
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rencana latihan tidak ditemukan.",
        )

    task = (
        db.query(WorkoutTask)
        .filter(WorkoutTask.id == task_id, WorkoutTask.plan_id == plan_id)
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tugas latihan tidak ditemukan.",
        )

    is_completed = payload.get("is_completed")
    if is_completed is not None:
        task.is_completed = is_completed
        db.commit()
        db.refresh(task)

    return ApiResponse(
        status="success",
        message="Status tugas berhasil diperbarui.",
        data=WorkoutTaskOut.model_validate(task).model_dump(),
    )


@router.delete("/{plan_id}", response_model=ApiResponse, status_code=status.HTTP_200_OK)
def delete_workout_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.id
    plan = (
        db.query(DailyWorkoutPlan)
        .filter(DailyWorkoutPlan.id == plan_id, DailyWorkoutPlan.user_id == uid)
        .first()
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rencana latihan tidak ditemukan.",
        )

    db.delete(plan)
    db.commit()

    return ApiResponse(
        status="success",
        message="Rencana latihan berhasil dihapus.",
    )
