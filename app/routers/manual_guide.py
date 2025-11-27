# routers/manual_guide.py

from fastapi import APIRouter, Depends, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import Optional
import shutil, os
from datetime import datetime
from urllib.parse import quote

from app.database import get_db
from app.models.manual_guide import ManualGuide
from app.schemas.manual_guide import ManualGuideResponse
from app.models.users import User
from app.utils.response import success_response, error_response
from app.utils.utils import require_admin
from app.utils.paths import static_path

router = APIRouter(prefix="/manual-guides", tags=["ManualGuides"])

UPLOAD_DIR = static_path("manual_guides", ensure=True)


# ----------------------------------------------------
# Helper: Format response with full static file URL
# ----------------------------------------------------
def format_guide(guide: ManualGuide, request: Request) -> dict:
    item = ManualGuideResponse.model_validate(guide).dict()

    if item.get("Path"):
        filename = quote(os.path.basename(item["Path"]))
        item["Path"] = f"{request.base_url}static/manual_guides/{filename}"

    return item


# ----------------------------------------------------
# Public GET – Anyone can access guides
# ----------------------------------------------------
@router.get("/")
def get_manual_guides(request: Request, db: Session = Depends(get_db)):
    guides = (
        db.query(ManualGuide)
        .filter(ManualGuide.IsDelete == False)
        .order_by(ManualGuide.ManualGuideID.desc())
        .all()
    )

    data = [format_guide(guide, request) for guide in guides]

    return success_response(
        "Manual guides retrieved successfully",
        "تم جلب الأدلة الإرشادية بنجاح",
        data
    )


# ----------------------------------------------------
# Admin – Create new manual guide
# ----------------------------------------------------
@router.post("/create")
def create_manual_guide(
    request: Request,
    NameEn: str = Form(...),
    NameAr: Optional[str] = Form(None),
    DescriptionEn: Optional[str] = Form(None),
    DescriptionAr: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    payload: User = Depends(require_admin)
):

    # --------------------------
    # Handle file upload safely
    # --------------------------
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_filename = f"{timestamp}_{file.filename.replace(' ', '_')}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # --------------------------
    # Create DB record
    # --------------------------
    guide = ManualGuide(
        NameEn=NameEn,
        NameAr=NameAr,
        DescriptionEn=DescriptionEn,
        DescriptionAr=DescriptionAr,
        Path=file_path,
        CreatedByUserID=payload.UserID,
    )

    db.add(guide)
    db.commit()
    db.refresh(guide)

    return success_response(
        "Manual guide created successfully",
        "تم إنشاء الدليل الإرشادي بنجاح",
        format_guide(guide, request)
    )


# ----------------------------------------------------
# Admin – Update manual guide
# ----------------------------------------------------
@router.put("/{manual_id}")
def update_manual_guide(
    request: Request,
    manual_id: int,
    NameEn: Optional[str] = Form(None),
    NameAr: Optional[str] = Form(None),
    DescriptionEn: Optional[str] = Form(None),
    DescriptionAr: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    payload: User = Depends(require_admin)
):

    manual = db.query(ManualGuide).filter(ManualGuide.ManualGuideID == manual_id).first()
    if not manual:
        return error_response(
            "Manual guide not found",
            "لم يتم العثور على الدليل الإرشادي",
            "404"
        )

    # Update fields
    if NameEn is not None: manual.NameEn = NameEn
    if NameAr is not None: manual.NameAr = NameAr
    if DescriptionEn is not None: manual.DescriptionEn = DescriptionEn
    if DescriptionAr is not None: manual.DescriptionAr = DescriptionAr

    # File update if provided
    if file:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        safe_filename = f"{timestamp}_{file.filename.replace(' ', '_')}"
        new_path = os.path.join(UPLOAD_DIR, safe_filename)

        with open(new_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        manual.Path = new_path

    manual.UpdatedAt = datetime.utcnow()
    manual.UpdatedByUserID = payload.UserID

    db.commit()
    db.refresh(manual)

    return success_response(
        "Manual guide updated successfully",
        "تم تحديث الدليل الإرشادي بنجاح",
        format_guide(manual, request)
    )


# ----------------------------------------------------
# Admin – Delete manual guide (soft delete)
# ----------------------------------------------------
@router.delete("/{guide_id}")
def delete_manual_guide(
    guide_id: int,
    db: Session = Depends(get_db),
    payload: User = Depends(require_admin)
):

    guide = db.query(ManualGuide).filter(
        ManualGuide.ManualGuideID == guide_id,
        ManualGuide.IsDelete == False
    ).first()

    if not guide:
        return error_response(
            "Manual guide not found",
            "لم يتم العثور على الدليل الإرشادي",
            "404"
        )

    guide.IsDelete = True
    guide.UpdatedAt = datetime.utcnow()
    guide.UpdatedByUserID = payload.UserID

    db.commit()

    return success_response(
        "Manual guide deleted successfully",
        "تم حذف الدليل الإرشادي بنجاح",
        None
    )
