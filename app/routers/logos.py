from fastapi import APIRouter, Depends, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import Optional
import os
import shutil
from urllib.parse import quote
from datetime import datetime
from app.models.logos import Logo
from app.models.users import User
from app.schemas.logos import LogoCreate, LogoUpdate, LogoResponse, VALID_CATEGORIES
from app.utils.response import success_response, error_response
from app.database import get_db
from app.utils.utils import require_admin
from app.utils.paths import static_path

router = APIRouter(prefix="/logos", tags=["Logos"])


# Helper to format ImagePath URL
def format_logo(logo: Logo, request: Request) -> dict:
    data = LogoResponse.from_orm(logo).dict()
    if data.get("ImagePath") and data.get("Category"):
        imagename = quote(os.path.basename(data["ImagePath"]))
        data["ImagePath"] = f"{request.base_url}static/Logos/{data['Category'].lower()}/{imagename}"
    return data


# -----------------------
# Public endpoint: Get all logos
@router.get("/")
def get_logos(category: Optional[str] = None, request: Request = None, db: Session = Depends(get_db)):
    if category and category.lower() not in VALID_CATEGORIES:
        return error_response(
            message_en="Invalid category. Allowed values: partner, benefits",
            message_ar="فئة غير صالحة. القيم المسموح بها: partner, benefits",
            error_code="INVALID_CATEGORY"
        )

    query = db.query(Logo)
    if category:
        query = query.filter(Logo.Category.ilike(category))
    logos = query.order_by(Logo.CreatedAt.desc()).all()

    data = [format_logo(logo, request) for logo in logos]

    return success_response(
        message_en="Logos retrieved successfully",
        message_ar="تم جلب الشعارات بنجاح",
        data=data
    )


# -----------------------
# Admin: Create logo
@router.post("/admin/create")
def create_logo(
    NameEn: str = Form(...),
    NameAr: Optional[str] = Form(None),
    Link: str = Form(...),
    Category: str = Form(...),
    ImageFile: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    request: Request = None,
):
    if Category.lower() not in VALID_CATEGORIES:
        return error_response(
            message_en="Invalid category. Allowed values: partner, benefits",
            message_ar="فئة غير صالحة. القيم المسموح بها: partner, benefits",
            error_code="INVALID_CATEGORY"
        )

    image_path = None
    if ImageFile:
        folder = static_path("Logos", Category.lower(), ensure=True)
        image_path = f"{folder}/{ImageFile.filename}"
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(ImageFile.file, buffer)

    new_logo = Logo(
        NameEn=NameEn,
        NameAr=NameAr,
        Link=Link,
        Category=Category.lower(),
        ImagePath=image_path,
        CreatedAt=datetime.utcnow(),
        CreatedByUserID=current_user.UserID,
    )

    db.add(new_logo)
    db.commit()
    db.refresh(new_logo)

    data = format_logo(new_logo, request)

    return success_response(
        message_en="Logo created successfully",
        message_ar="تم إنشاء الشعار بنجاح",
        data=data
    )


# -----------------------
# Admin: Get logo by ID
@router.get("/admin/{logo_id}")
def get_logo(logo_id: int, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    logo = db.query(Logo).filter(Logo.LogoID == logo_id).first()
    if not logo:
        return error_response(
            message_en="Logo not found",
            message_ar="لم يتم العثور على الشعار",
            error_code="NOT_FOUND"
        )

    data = format_logo(logo, request)

    return success_response(
        message_en="Logo retrieved successfully",
        message_ar="تم جلب الشعار بنجاح",
        data=data
    )


# -----------------------
# Admin: Update logo
@router.put("/admin/{logo_id}")
def update_logo(
    logo_id: int,
    NameEn: Optional[str] = Form(None),
    NameAr: Optional[str] = Form(None),
    Link: Optional[str] = Form(None),
    Category: Optional[str] = Form(None),
    ImagePath: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    request: Request = None,
):
    logo = db.query(Logo).filter(Logo.LogoID == logo_id).first()
    if not logo:
        return error_response(
            message_en="Logo not found",
            message_ar="لم يتم العثور على الشعار",
            error_code="NOT_FOUND"
        )

    if Category and Category.lower() not in VALID_CATEGORIES:
        return error_response(
            message_en="Invalid category. Allowed values: partner, benefits",
            message_ar="فئة غير صالحة. القيم المسموح بها: partner, benefits",
            error_code="INVALID_CATEGORY"
        )

    # Update fields
    if NameEn is not None:
        logo.NameEn = NameEn
    if NameAr is not None:
        logo.NameAr = NameAr
    if Link is not None:
        logo.Link = Link
    if Category is not None:
        logo.Category = Category.lower()

    # Update image if provided
    if ImagePath:
        folder = static_path("Logos", logo.Category.lower(), ensure=True)
        if logo.ImagePath and os.path.exists(logo.ImagePath):
            os.remove(logo.ImagePath)

        new_path = f"{folder}/{ImagePath.filename}"
        with open(new_path, "wb") as buffer:
            shutil.copyfileobj(ImagePath.file, buffer)

        logo.ImagePath = new_path

    logo.UpdatedAt = datetime.utcnow()
    logo.UpdatedByUserID = current_user.UserID

    db.commit()
    db.refresh(logo)

    data = format_logo(logo, request)

    return success_response(
        message_en="Logo updated successfully",
        message_ar="تم تحديث الشعار بنجاح",
        data=data
    )


# -----------------------
# Admin: Delete logo
@router.delete("/admin/{logo_id}")
def delete_logo(logo_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    logo = db.query(Logo).filter(Logo.LogoID == logo_id).first()

    if not logo:
        return error_response(
            message_en="Logo not found",
            message_ar="لم يتم العثور على الشعار",
            error_code="NOT_FOUND"
        )

    db.delete(logo)
    db.commit()

    return success_response(
        message_en="Logo deleted successfully",
        message_ar="تم حذف الشعار بنجاح"
    )
