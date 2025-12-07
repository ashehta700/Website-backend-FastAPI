# routers/projects.py
from fastapi import APIRouter, Depends, Body
from sqlalchemy import func # Import the func module for coalesce
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.projects import Projects
from app.models.users import User
from app.schemas.projects import ProjectResponse, ProjectCreate, ProjectUpdate
from app.utils.response import success_response, error_response
from app.database import get_db
from app.utils.utils import require_admin

router = APIRouter(prefix="/projects", tags=["Projects"])


# ----------- Public Endpoint -----------
@router.get("/all")
def get_projects_home(db: Session = Depends(get_db)):
    projects = db.query(Projects).filter(func.coalesce(Projects.IsDeleted, False) == False).order_by(Projects.CreatedAt.desc()).all()
    if not projects:
        return error_response("No projects found", "لا توجد مشاريع")
    projects_data = [ProjectResponse.from_orm(p).dict() for p in projects]
    return success_response(
        "Projects retrieved successfully",
        "تم جلب المشاريع بنجاح",
        projects_data
    )


# ----------- Admin Endpoints -----------
@router.get("/admin")
def get_all_projects_admin(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    projects = db.query(Projects).order_by(Projects.CreatedAt.desc()).all()
    if not projects:
        return error_response("No projects found", "لا توجد مشاريع")
    projects_data = [ProjectResponse.from_orm(p).dict() for p in projects]
    return success_response(
        "Projects retrieved successfully",
        "تم جلب المشاريع بنجاح",
        projects_data
    )


@router.get("/{project_id}")
def get_project(project_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    project = db.query(Projects).filter(Projects.ProjectID == project_id).first()
    if not project:
        return error_response("Project not found", "المشروع غير موجود")
    project_data = ProjectResponse.from_orm(project).dict()
    return success_response(
        "Project retrieved successfully",
        "تم جلب المشروع بنجاح",
        project_data
    )


@router.post("/add")
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    new_project = Projects(
        **payload.dict(),
        CreatedAt=datetime.utcnow(),
        CreatedByUserID=current_user.UserID
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    project_data = ProjectResponse.from_orm(new_project).dict()
    return success_response(
        "Project created successfully",
        "تم إنشاء المشروع بنجاح",
        project_data
    )


@router.put("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate = Body(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    project = db.query(Projects).filter(Projects.ProjectID == project_id).first()
    if not project:
        return error_response("Project not found", "المشروع غير موجود")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(project, field, value)
    project.UpdatedAt = datetime.utcnow()
    project.UpdatedByUserID = current_user.UserID
    db.commit()
    db.refresh(project)
    project_data = ProjectResponse.from_orm(project).dict()
    return success_response(
        "Project updated successfully",
        "تم تحديث المشروع بنجاح",
        project_data
    )


@router.delete("/{project_id}")
def delete_project(project_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    project = db.query(Projects).filter(Projects.ProjectID == project_id).first()
    if not project:
        return error_response("Project not found", "المشروع غير موجود")
    
    project.IsDeleted = True
    project.UpdatedAt = datetime.utcnow()
    project.UpdatedByUserID = User.UserID
    db.commit()
    return success_response(
        "Project deleted successfully",
        "تم حذف المشروع بنجاح"
    )
