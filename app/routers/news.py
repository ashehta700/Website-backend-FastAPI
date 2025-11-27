# routers/news.py

from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from urllib.parse import quote
import os, shutil

from app.database import get_db
from app.models.news import News
from app.models.users import User
from app.schemas.news import NewsResponse
from app.utils.response import success_response, error_response
from app.utils.utils import require_admin
from app.utils.paths import static_path

router = APIRouter(prefix="/news", tags=["News"])

NEWS_IMAGES_DIR = static_path("News", "images", ensure=True)
NEWS_VIDEOS_DIR = static_path("News", "videos", ensure=True)


# -------------------------
# Helper: format NewsResponse with URLs
# -------------------------
def format_news(news: News, request: Request) -> dict:
    item = NewsResponse.from_orm(news).dict()
    base_url = str(request.base_url).rstrip("/")
    if item.get("ImagePath"):
        item["ImagePath"] = f"{base_url}/static/News/images/{quote(os.path.basename(item['ImagePath']))}"
    if item.get("VideoPath"):
        item["VideoPath"] = f"{base_url}/static/News/videos/{quote(os.path.basename(item['VideoPath']))}"
    return item


# -------------------------
# Public Endpoints
# -------------------------
@router.get("/slider")
def get_news_slider(request: Request, db: Session = Depends(get_db)):
    news_list = db.query(News).filter(News.Is_slide == True, News.Is_delete != True).order_by(News.CreatedAt.desc()).limit(4).all()
    data = [format_news(n, request) for n in news_list]
    return success_response(
        "Slider news retrieved successfully",
        "تم جلب أخبار السلايدر بنجاح",
        data
    )


@router.get("/all")
def get_all_news(request: Request, db: Session = Depends(get_db)):
    news_list = db.query(News).filter(News.Is_delete != True).order_by(News.CreatedAt.desc()).all()
    data = [format_news(n, request) for n in news_list]
    return success_response(
        "All news retrieved successfully",
        "تم جلب جميع الأخبار بنجاح",
        data
    )


@router.get("/{news_id}")
def get_news_details(news_id: int, request: Request, db: Session = Depends(get_db)):
    news = db.query(News).filter(News.NewsID == news_id, News.Is_delete != True).first()
    if not news:
        return error_response("News not found", "لم يتم العثور على الخبر")

    news.Read_count = (news.Read_count or 0) + 1
    db.commit()
    db.refresh(news)

    data = format_news(news, request)
    return success_response(
        "News details retrieved successfully",
        "تم جلب تفاصيل الخبر بنجاح",
        data
    )


# -------------------------
# Admin Endpoints
# -------------------------
@router.post("/admin/create")
def create_news(
    TitleEn: str = Form(...),
    TitleAr: str = Form(...),
    DescriptionEn: Optional[str] = Form(None),
    DescriptionAr: Optional[str] = Form(None),
    Is_slide: Optional[bool] = Form(False),
    ImagePath: Optional[UploadFile] = File(None),
    VideoPath: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    request: Request = None
):
    image_path = None
    video_path = None

    if ImagePath:
        image_path = os.path.join(NEWS_IMAGES_DIR, ImagePath.filename)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(ImagePath.file, buffer)

    if VideoPath:
        video_path = os.path.join(NEWS_VIDEOS_DIR, VideoPath.filename)
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(VideoPath.file, buffer)

    new_news = News(
        TitleEn=TitleEn,
        TitleAr=TitleAr,
        DescriptionEn=DescriptionEn,
        DescriptionAr=DescriptionAr,
        ImagePath=image_path,
        VideoPath=video_path,
        CreatedAt=datetime.utcnow(),
        CreatedByUserID=current_user.UserID,
        Is_slide=Is_slide,
        Is_delete=False,
        Read_count=0
    )

    db.add(new_news)
    db.commit()
    db.refresh(new_news)

    data = format_news(new_news, request)
    return success_response(
        "News created successfully",
        "تم إنشاء الخبر بنجاح",
        data
    )


@router.put("/admin/{news_id}")
def update_news(
    news_id: int,
    TitleEn: Optional[str] = Form(None),
    TitleAr: Optional[str] = Form(None),
    DescriptionEn: Optional[str] = Form(None),
    DescriptionAr: Optional[str] = Form(None),
    Is_slide: Optional[bool] = Form(None),
    ImagePath: Optional[UploadFile] = File(None),
    VideoPath: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    request: Request = None
):
    news = db.query(News).filter(News.NewsID == news_id, News.Is_delete != True).first()
    if not news:
        return error_response("News not found", "لم يتم العثور على الخبر")

    if TitleEn is not None: news.TitleEn = TitleEn
    if TitleAr is not None: news.TitleAr = TitleAr
    if DescriptionEn is not None: news.DescriptionEn = DescriptionEn
    if DescriptionAr is not None: news.DescriptionAr = DescriptionAr
    if Is_slide is not None: news.Is_slide = Is_slide

    if ImagePath:
        if news.ImagePath and os.path.exists(news.ImagePath):
            os.remove(news.ImagePath)
        image_path = os.path.join(NEWS_IMAGES_DIR, ImagePath.filename)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(ImagePath.file, buffer)
        news.ImagePath = image_path

    if VideoPath:
        if news.VideoPath and os.path.exists(news.VideoPath):
            os.remove(news.VideoPath)
        video_path = os.path.join(NEWS_VIDEOS_DIR, VideoPath.filename)
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(VideoPath.file, buffer)
        news.VideoPath = video_path

    news.UpdatedAt = datetime.utcnow()
    news.UpdatedByUserID = current_user.UserID

    db.commit()
    db.refresh(news)

    data = format_news(news, request)
    return success_response(
        "News updated successfully",
        "تم تحديث الخبر بنجاح",
        data
    )


@router.delete("/admin/{news_id}")
def delete_news(news_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    news = db.query(News).filter(News.NewsID == news_id, News.Is_delete != True).first()
    if not news:
        return error_response("News not found", "لم يتم العثور على الخبر")

    news.Is_delete = True
    news.UpdatedAt = datetime.utcnow()
    news.UpdatedByUserID = current_user.UserID

    db.commit()
    return success_response(
        "News soft-deleted successfully",
        "تم حذف الخبر بنجاح"
    )
