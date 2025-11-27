from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_ ,func
from typing import Optional
from urllib.parse import quote
from app.database import SessionLocal
from app.models.faq import FAQ
from app.models.metadata import DatasetInfo, MetadataInfo
from app.models.news import News
from app.models.products import Product
from app.models.projects import Projects
from app.models.project_details import ProjectDetails
from app.models.manual_guide import ManualGuide
from app.models.videos import Video
from app.utils.response import success_response, error_response
from app.utils.paths import normalize_static_subpath
import re

router = APIRouter(prefix="/search", tags=["Global Search"])


def build_image_url(request: Request, image_path: Optional[str]) -> Optional[str]:
    relative_path = normalize_static_subpath(image_path) if image_path else ""
    if not relative_path:
        return None
    base_url = str(request.base_url).rstrip("/")
    encoded = quote(relative_path, safe="/")
    return f"{base_url}/static/{encoded}"


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Utility for keyword highlighting ---
def highlight_text(text: str, keyword: str) -> str:
    if not text:
        return ""
    escaped_keyword = re.escape(keyword)
    pattern = re.compile(f"({escaped_keyword})", re.IGNORECASE)
    return pattern.sub(r"<mark>\1</mark>", text)


# --- Core search logic ---
def global_search(db: Session, search_term: str, request: Request, skip: int = 0, limit: int = 10):
    results = []

    def add_result(model_name, category, url, title_en, title_ar, description_en, description_ar, image=None):
        results.append({
            "model": model_name,
            "category": category,
            "url": url,
            "title_en": highlight_text(title_en or "", search_term),
            "title_ar": highlight_text(title_ar or "", search_term),
            "description_en": highlight_text(description_en or "", search_term),
            "description_ar": highlight_text(description_ar or "", search_term),
            "image": build_image_url(request, image)
        })

    # --- FAQ ---
    faq_results = db.query(FAQ).filter(
        FAQ.IsDelete == 0,  # <-- only active
        or_(
            FAQ.QuestionEn.ilike(f"%{search_term}%"),
            FAQ.AnswerEn.ilike(f"%{search_term}%"),
            FAQ.QuestionAr.ilike(f"%{search_term}%"),
            FAQ.AnswerAr.ilike(f"%{search_term}%")
        )
    ).order_by(FAQ.FAQID).limit(limit).offset(skip).all()
    for faq in faq_results:
        add_result("FAQ", "FAQ", f"/faq/{faq.FAQID}", faq.QuestionEn, faq.QuestionAr, faq.AnswerEn, faq.AnswerAr)

    # --- DatasetInfo ---
    dataset_results = db.query(DatasetInfo).filter(
        DatasetInfo.IsDeleted==0,
        or_(
            DatasetInfo.Name.ilike(f"%{search_term}%"),
            DatasetInfo.Title.ilike(f"%{search_term}%"),
            DatasetInfo.NameAr.ilike(f"%{search_term}%"),
            DatasetInfo.TitleAr.ilike(f"%{search_term}%"),
            DatasetInfo.description.ilike(f"%{search_term}%"),
            DatasetInfo.descriptionAr.ilike(f"%{search_term}%"),
            DatasetInfo.Keywords.ilike(f"%{search_term}%")
        )
    ).order_by(DatasetInfo.DatasetID).limit(limit).offset(skip).all()
    for dataset in dataset_results:
        add_result("DatasetInfo", "Metadata", f"/datasets/{dataset.DatasetID}",
                   dataset.Name, dataset.NameAr, dataset.description, dataset.descriptionAr,
                   image=getattr(dataset, "img", None))

    # --- MetadataInfo ---
    metadata_results = db.query(MetadataInfo).filter(
        MetadataInfo.IsDeleted==0,
        or_(
            MetadataInfo.Name.ilike(f"%{search_term}%"),
            MetadataInfo.Title.ilike(f"%{search_term}%"),
            MetadataInfo.NameAr.ilike(f"%{search_term}%"),
            MetadataInfo.TitleAr.ilike(f"%{search_term}%"),
            MetadataInfo.description.ilike(f"%{search_term}%"),
            MetadataInfo.descriptionAr.ilike(f"%{search_term}%")
        )
    ).order_by(MetadataInfo.MetadataID).limit(limit).offset(skip).all()
    for meta in metadata_results:
        add_result("MetadataInfo", "Metadata", f"/metadata/{meta.MetadataID}",
                   meta.Name, meta.NameAr, meta.description, meta.descriptionAr,
                   image=getattr(meta, "ImageUrl", None))

    # --- News ---
    news_results = db.query(News).filter(
        News.Is_delete==0,
        or_(
            News.TitleEn.ilike(f"%{search_term}%"),
            News.DescriptionEn.ilike(f"%{search_term}%"),
            News.TitleAr.ilike(f"%{search_term}%"),
            News.DescriptionAr.ilike(f"%{search_term}%")
        )
    ).order_by(News.NewsID).limit(limit).offset(skip).all()
    for news in news_results:
        add_result("News", "News", f"/news/{news.NewsID}",
                   news.TitleEn, news.TitleAr, news.DescriptionEn, news.DescriptionAr,
                   image=getattr(news, "ImagePath", None))

    # --- Products ---
    product_results = db.query(Product).filter(
        Product.IsDeleted ==0,
        or_(
            Product.NameEn.ilike(f"%{search_term}%"),
            Product.DescriptionEn.ilike(f"%{search_term}%"),
            Product.NameAr.ilike(f"%{search_term}%"),
            Product.DescriptionAr.ilike(f"%{search_term}%")
        )
    ).order_by(Product.ProductID).limit(limit).offset(skip).all()
    for product in product_results:
        add_result("Product", "Products", f"/products/{product.ProductID}",
                   product.NameEn, product.NameAr, product.DescriptionEn, product.DescriptionAr,
                   image=getattr(product, "ImagePath", None))

    # --- Projects ---
    project_results = db.query(Projects).filter(
        func.coalesce(Projects.IsDeleted, 0) == 0,
        or_(
            Projects.NameEn.ilike(f"%{search_term}%"),
            Projects.DescriptionEn.ilike(f"%{search_term}%"),
            Projects.NameAr.ilike(f"%{search_term}%"),
            Projects.DescriptionAr.ilike(f"%{search_term}%")
        )
    ).order_by(Projects.ProjectID).limit(limit).offset(skip).all()
    for project in project_results:
        add_result("Project", "Projects", f"/projects/{project.ProjectID}",
                   project.NameEn, project.NameAr, project.DescriptionEn, project.DescriptionAr,
                   image=getattr(project, "ImagePath", None))

    # --- ProjectDetails ---
    project_detail_results = db.query(ProjectDetails).filter(
        ProjectDetails.IsDeleted == 0,
        or_(
            ProjectDetails.ServiceName.ilike(f"%{search_term}%"),
            ProjectDetails.ServiceDescription.ilike(f"%{search_term}%"),
            ProjectDetails.ServiceName.ilike(f"%{search_term}%"),
            ProjectDetails.ServiceDescriptionAr.ilike(f"%{search_term}%")
        )
    ).order_by(ProjectDetails.ProjectDetailID).limit(limit).offset(skip).all()
    for detail in project_detail_results:
        add_result("ProjectDetail", "ProjectDetails", f"/project-details/{detail.ProjectDetailID}",
                   detail.ServiceName, detail.ServiceName, detail.ServiceDescription, detail.ServiceDescriptionAr,
                   image=getattr(detail, "ImageUrl", None))

    # --- ManualGuide ---
    manual_guide_results = db.query(ManualGuide).filter(
        ManualGuide.IsDelete ==0,
        or_(
            ManualGuide.NameEn.ilike(f"%{search_term}%"),
            ManualGuide.DescriptionEn.ilike(f"%{search_term}%"),
            ManualGuide.NameAr.ilike(f"%{search_term}%"),
            ManualGuide.DescriptionAr.ilike(f"%{search_term}%")
        )
    ).order_by(ManualGuide.ManualGuideID).limit(limit).offset(skip).all()
    for guide in manual_guide_results:
        add_result("ManualGuide", "ManualGuide", f"/manual-guides/{guide.ManualGuideID}",
                   guide.NameEn, guide.NameAr, guide.DescriptionEn, guide.DescriptionAr,
                   image=getattr(guide, "ImageUrl", None))

    # --- Videos ---
    video_results = db.query(Video).filter(
        Video.IsDeleted==0,
        or_(
            Video.TitleEn.ilike(f"%{search_term}%"),
            Video.DescriptionEn.ilike(f"%{search_term}%"),
            Video.TitleAr.ilike(f"%{search_term}%"),
            Video.DescriptionAr.ilike(f"%{search_term}%")
        )
    ).order_by(Video.VideoID).limit(limit).offset(skip).all()
    for video in video_results:
        add_result("Video", "Videos", f"/videos/{video.VideoID}",
                   video.TitleEn, video.TitleAr, video.DescriptionEn, video.DescriptionAr,
                   image=getattr(video, "ImagePath", None))

    return results


# --- Global Search Endpoint with Pagination ---
@router.get("/")
def search(
    request: Request,
    query: str = Query(..., description="Search term"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    try:
        query = query.strip()
        if not query:
            return error_response("Search query cannot be empty.", "EMPTY_QUERY")

        skip = (page - 1) * limit
        search_results = global_search(db, query, request, skip, limit)

        if not search_results:
            return error_response(
                "No results found for your query.",
                "لم يتم العثور على نتائج للبحث الخاص بك.",
                "NOT_FOUND"
            )

        response_data = {
            "page": page,
            "limit": limit,
            "count": len(search_results),
            "results": search_results
        }

        return success_response(
            "Search results retrieved successfully.",
            "تم جلب نتائج البحث بنجاح.",
            response_data
        )

    except Exception as e:
        print("Error in search:", str(e))
        return error_response(
            "An error occurred while processing your request.",
            "حدث خطأ أثناء معالجة طلبك.",
            "INTERNAL_ERROR"
        )
