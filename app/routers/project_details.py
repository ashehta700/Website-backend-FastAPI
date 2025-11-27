# routers/project_details.py
from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.project_details import ProjectDetails
from app.models.users import User
from app.schemas.project_details import (
    ProjectDetailResponse,
    ProjectDetailCreate,
    ProjectDetailUpdate,
)
from app.utils.response import success_response, error_response
from app.database import get_db
from app.utils.utils import require_admin

router = APIRouter(prefix="/project-details", tags=["ProjectDetails"])


# ---------------- Public Endpoint ----------------
@router.get("/project/{project_id}")
def get_project_details(project_id: int, db: Session = Depends(get_db)):
    """
    Get all details for a specific project.
    Returns Attribute and AttributeAr as dicts.
    """
    details = (
        db.query(ProjectDetails)
        .filter(ProjectDetails.ProjectID == project_id, ProjectDetails.IsDeleted == False)
        .order_by(ProjectDetails.Year, ProjectDetails.Quarter)
        .all()
    )
    if not details:
        return error_response("No details for this project", "لا توجد تفاصيل لهذا المشروع")

    data = [ProjectDetailResponse.from_orm(d).dict() for d in details]
    return success_response(
        "Project details retrieved successfully",
        "تم جلب تفاصيل المشروع بنجاح",
        data
    )


# ---------------- Admin Endpoints ----------------
@router.post("/add/{project_id}")
def create_project_detail(
    project_id: int,
    payload: ProjectDetailCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new project detail for a specific project.
    Attribute / AttributeAr must be dicts (JSON objects).
    """
    new_detail = ProjectDetails(
        ProjectID=project_id,
        **payload.dict(exclude_unset=True),
        CreatedAt=datetime.utcnow(),
        CreatedByUserID=current_user.UserID,
    )
    db.add(new_detail)
    db.commit()
    db.refresh(new_detail)
    return success_response(
        "Project detail created successfully",
        "تم إنشاء تفاصيل المشروع بنجاح",
        ProjectDetailResponse.from_orm(new_detail).dict()
    )


@router.put("/{detail_id}")
def update_project_detail(
    detail_id: int,
    payload: ProjectDetailUpdate = Body(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Update one or more fields of a project detail.
    Partial update supported.
    """
    detail = db.query(ProjectDetails).filter(ProjectDetails.ProjectDetailID == detail_id).first()
    if not detail:
        return error_response("Project detail not found", "لم يتم العثور على تفاصيل المشروع")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(detail, field, value)

    detail.UpdatedAt = datetime.utcnow()
    detail.UpdatedByUserID = current_user.UserID
    db.commit()
    db.refresh(detail)
    return success_response(
        "Project detail updated successfully",
        "تم تحديث تفاصيل المشروع بنجاح",
        ProjectDetailResponse.from_orm(detail).dict()
    )


@router.delete("/{detail_id}")
def delete_project_detail(
    detail_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Soft delete a project detail.
    """
    detail = db.query(ProjectDetails).filter(ProjectDetails.ProjectDetailID == detail_id).first()
    if not detail:
        return error_response("Project detail not found", "لم يتم العثور على تفاصيل المشروع")

    detail.IsDeleted = True
    detail.UpdatedAt = datetime.utcnow()
    detail.UpdatedByUserID = current_user.UserID
    db.commit()
    return success_response(
        "Project detail deleted successfully",
        "تم حذف تفاصيل المشروع بنجاح"
    )


# ---------------- Optional: Get single detail by ID ----------------
@router.get("/{detail_id}")
def get_single_project_detail(
    detail_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get a single project detail by ID (admin only).
    """
    detail = (
        db.query(ProjectDetails)
        .filter(ProjectDetails.ProjectDetailID == detail_id, ProjectDetails.IsDeleted == False)
        .first()
    )
    if not detail:
        return error_response("Project detail not found", "لم يتم العثور على تفاصيل المشروع")

    return success_response(
        "Project detail retrieved successfully",
        "تم جلب تفاصيل المشروع بنجاح",
        ProjectDetailResponse.from_orm(detail).dict()
    )
