import os, shutil
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from urllib.parse import quote
from app.database import get_db
from app.models.videos import Video
from app.models.users import User
from app.auth.jwt_bearer import JWTBearer
from app.utils.response import success_response, error_response
from app.utils.utils import get_current_user , require_admin
from app.utils.paths import static_path, static_file_paths, normalize_static_subpath

router = APIRouter(prefix="/videos", tags=["Videos"])

# ---------- Helpers ----------


def build_image_url(request: Request, image_path: Optional[str]) -> Optional[str]:
    relative_path = normalize_static_subpath(image_path) if image_path else ""
    if not relative_path:
        return None
    base_url = str(request.base_url).rstrip("/")
    encoded = quote(relative_path, safe="/")
    return f"{base_url}/static/{encoded}"


# ---------- Public ----------
@router.get("/")
def list_videos(request: Request, db: Session = Depends(get_db)):
    videos = db.query(Video).filter(Video.IsDeleted == False ).all()  # only active videos
    data = []
    for v in videos:
        data.append({
            "VideoID": v.VideoID,
            "TitleEn": v.TitleEn,
            "TitleAr": v.TitleAr,
            "DescriptionEn": v.DescriptionEn,
            "DescriptionAr": v.DescriptionAr,
            "Link": v.Link,
            "ImagePath": build_image_url(request, v.ImagePath),
            "CreatedAt": v.CreatedAt,
            "UpdatedAt": v.UpdatedAt,
        })
    return success_response("Videos fetched successfully", data={"videos": data})

# ---------- Admin CRUD ----------
@router.post("/")
def create_video(
    request: Request,
    TitleEn: str = Form(...),
    Link: str = Form(...),
    TitleAr: Optional[str] = Form(None),
    DescriptionEn: Optional[str] = Form(None),
    DescriptionAr: Optional[str] = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin)
):
    image_path = None
    if image:
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{image.filename}"
        save_path, image_path = static_file_paths(filename, "videos")

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    else:
        image_path = None

    new_video = Video(
        TitleEn=TitleEn,
        TitleAr=TitleAr,
        DescriptionEn=DescriptionEn,
        DescriptionAr=DescriptionAr,
        Link=Link,
        ImagePath=image_path,
        CreatedByUserID=user.UserID,
        IsDeleted=False  # default active
    )
    db.add(new_video)
    db.commit()     
    db.refresh(new_video)

    data = {
        "VideoID": new_video.VideoID,
        "TitleEn": new_video.TitleEn,
        "TitleAr": new_video.TitleAr,
        "DescriptionEn": new_video.DescriptionEn,
        "DescriptionAr": new_video.DescriptionAr,
        "Link": new_video.Link,
        "ImagePath": build_image_url(request, new_video.ImagePath),
        "CreatedAt": new_video.CreatedAt,
    }
    return success_response("Video created successfully", "تم انشاء الفيديو بنجاح" , data)


@router.put("/{video_id}")
def update_video(
    video_id: int,
    request: Request,
    TitleEn: Optional[str] = Form(None),
    Link: Optional[str] = Form(None),
    TitleAr: Optional[str] = Form(None),
    DescriptionEn: Optional[str] = Form(None),
    DescriptionAr: Optional[str] = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin)
):
    db_video = db.query(Video).filter(Video.VideoID == video_id).first()
    if not db_video:
        return error_response("Video not found",error_code= "VIDEO_NOT_FOUND")

    # --- Update text fields if provided ---
    if TitleEn: db_video.TitleEn = TitleEn
    if TitleAr: db_video.TitleAr = TitleAr
    if DescriptionEn: db_video.DescriptionEn = DescriptionEn
    if DescriptionAr: db_video.DescriptionAr = DescriptionAr
    if Link: db_video.Link = Link

    # --- Handle image upload ---
    if image:
        # 1️⃣ Optional: delete old image if exists
        if db_video.ImagePath:
            old_relative_path = normalize_static_subpath(db_video.ImagePath)
            old_path = static_path(old_relative_path) if old_relative_path else None
            if old_path and os.path.exists(old_path):
                os.remove(old_path)

        # 2️⃣ Save new image
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{image.filename}"
        save_path, relative_path = static_file_paths(filename, "videos")
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # 3️⃣ Update the database field
        db_video.ImagePath = relative_path

    # --- Update audit fields ---
    db_video.UpdatedAt = datetime.utcnow()
    db_video.UpdatedByUserID = user.UserID

    db.commit()
    db.refresh(db_video)

    # --- Prepare response ---
    data = {
        "VideoID": db_video.VideoID,
        "TitleEn": db_video.TitleEn,
        "TitleAr": db_video.TitleAr,
        "DescriptionEn": db_video.DescriptionEn,
        "DescriptionAr": db_video.DescriptionAr,
        "Link": db_video.Link,
        "ImagePath": build_image_url(request, db_video.ImagePath),
        "CreatedAt": db_video.CreatedAt,
        "UpdatedAt": db_video.UpdatedAt,
    }

    return success_response("Video updated successfully","تم التعديل بنجاح" , data)


@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    db_video = db.query(Video).filter(Video.VideoID == video_id, Video.IsDeleted == False).first()
    if not db_video:
        return error_response("Video not found", error_code="VIDEO_NOT_FOUND")

    # Soft delete instead of removing
    db_video.IsDeleted = True
    db_video.UpdatedAt = datetime.utcnow()
    db_video.UpdatedByUserID = user.UserID

    db.commit()

    return success_response("Video deleted successfully", "تم الحذف بنجاح" , {"video_id": video_id, "soft_deleted": True})
