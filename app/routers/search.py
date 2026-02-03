# routers/search.py

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import null, or_, func
from typing import Optional, List
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
import os
router = APIRouter(prefix="/search", tags=["Global Search"])


# ==========================================
# DB Session
# ==========================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# Helpers
# ==========================================

def build_image_url(image_path: Optional[str]):
    if not image_path:
        return None
    relative_path = normalize_static_subpath(image_path)
    base_url = os.getenv("BASE_URL")
    encoded = quote(relative_path, safe="/")
    return f"{base_url}/static/{encoded}"


def highlight_keywords(text: str, keywords: List[str]) -> str:
    if not text:
        return ""
    for kw in keywords:
        escaped_kw = re.escape(kw)
        text = re.sub(rf"({escaped_kw})", r"<mark>\1</mark>", text, flags=re.IGNORECASE)
    return text


def extract_keywords(query: str) -> List[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF ]+", " ", query).lower()
    words = cleaned.split()
    stopwords = set(["i", "need", "the", "to", "for", "من", "الى", "عن"])
    return [w for w in words if w not in stopwords and len(w) > 2]


def build_search_filter(columns, keywords):
    conditions = []
    for col in columns:
        for kw in keywords:
            conditions.append(col.ilike(f"%{kw}%"))
    return or_(*conditions)


def get_primary_key(model):
    """Return the primary key column of any model."""
    return list(model.__table__.primary_key.columns)[0]


# ==========================================
# GLOBAL SEARCH LOGIC
# ==========================================
def global_search(db: Session, query: str, request: Request, skip=0, limit=10):

    keywords = extract_keywords(query)
    if not keywords:
        keywords = [query.lower()]

    results = []

    def add(model_name, category, url, en_title, ar_title, en_desc, ar_desc, image):
        results.append({
            "model": model_name,
            "category": category,
            "url": url,
            "title_en": highlight_keywords(en_title or "", keywords),
            "title_ar": highlight_keywords(ar_title or "", keywords),
            "description_en": highlight_keywords(en_desc or "", keywords),
            "description_ar": highlight_keywords(ar_desc or "", keywords),
            "image": build_image_url(request, image)
        })

    # ============================
    # Search FAQ
    # ============================
    faq_cols = [
        FAQ.QuestionEn, FAQ.AnswerEn,
        FAQ.QuestionAr, FAQ.AnswerAr
    ]

    faq_items = (
        db.query(FAQ)
        .filter(
            FAQ.IsDelete == 0,
            build_search_filter(faq_cols, keywords)
        )
        .order_by(FAQ.FAQID.desc())      # 🔥 MSSQL FIX
        .offset(skip)
        .limit(limit)
        .all()
    )

    for i in faq_items:
        add("FAQ", "FAQ", f"/faq/{i.FAQID}",
            i.QuestionEn, i.QuestionAr, i.AnswerEn, i.AnswerAr, None)

    # ============================
    # DatasetInfo
    # ============================
    dataset_cols = [
        DatasetInfo.Name, DatasetInfo.Title,
        DatasetInfo.NameAr, DatasetInfo.TitleAr,
        DatasetInfo.description, DatasetInfo.descriptionAr,
        DatasetInfo.Keywords
    ]

    dataset_items = (
        db.query(DatasetInfo)
        .filter(
            DatasetInfo.IsDeleted == 0,
            build_search_filter(dataset_cols, keywords)
        )
        .order_by(DatasetInfo.DatasetID.desc())   # 🔥 MSSQL FIX
        .offset(skip)
        .limit(limit)
        .all()
    )

    for d in dataset_items:
        add("DatasetInfo", "Metadata", f"/datasets/{d.DatasetID}",
            d.Name, d.NameAr, d.description, d.descriptionAr, d.img)

    # ============================
    # MetadataInfo
    # ============================
    meta_cols = [
        MetadataInfo.Name, MetadataInfo.Title,
        MetadataInfo.NameAr, MetadataInfo.TitleAr,
        MetadataInfo.description, MetadataInfo.descriptionAr
    ]

    meta_items = (
        db.query(MetadataInfo)
        .filter(
            MetadataInfo.IsDeleted == 0,
            build_search_filter(meta_cols, keywords)
        )
        .order_by(MetadataInfo.MetadataID.desc())   # 🔥 MSSQL FIX
        .offset(skip)
        .limit(limit)
        .all()
    )

    for m in meta_items:
        add("MetadataInfo", "Metadata", f"/metadata/{m.MetadataID}",
            m.Name, m.NameAr, m.description, m.descriptionAr ,image = None)

    # ============================
    # GENERIC SEARCH MODEL FUNCTION
    # ============================
    def search_model(model, cols, id_name, url_path, image_field):
        pk = get_primary_key(model)

        items = (
            db.query(model)
            .filter(
                func.coalesce(
                    model.IsDeleted if hasattr(model, "IsDeleted") else 0, 0
                ) == 0,
                build_search_filter(cols, keywords)
            )
            .order_by(pk.desc())    # 🔥 MSSQL FIX
            .offset(skip)
            .limit(limit)
            .all()
        )

        for i in items:
            add(
                model.__name__,
                model.__name__,
                f"{url_path}/{getattr(i, id_name)}",
                getattr(i, "TitleEn", None) or getattr(i, "NameEn", None),
                getattr(i, "TitleAr", None) or getattr(i, "NameAr", None),
                getattr(i, "DescriptionEn", None),
                getattr(i, "DescriptionAr", None),
                getattr(i, image_field, None) if image_field else None
            )

    # ============================
    # Apply to all other tables
    # ============================
    search_model(
        News,
        [News.TitleEn, News.DescriptionEn, News.TitleAr, News.DescriptionAr],
        "NewsID", "/news", "ImagePath"
    )

    search_model(
        Product,
        [Product.NameEn, Product.DescriptionEn, Product.NameAr, Product.DescriptionAr],
        "ProductID", "/products", "ImagePath"
    )

    search_model(
        Projects,
        [Projects.NameEn, Projects.DescriptionEn, Projects.NameAr, Projects.DescriptionAr],
        "ProjectID", "/projects", "ImagePath"
    )

    search_model(
        ProjectDetails,
        [ProjectDetails.ServiceName, ProjectDetails.ServiceDescription],
        "ProjectDetailID", "/project-details", "ImageUrl"
    )

    search_model(
        ManualGuide,
        [ManualGuide.NameEn, ManualGuide.DescriptionEn, ManualGuide.NameAr, ManualGuide.DescriptionAr],
        "ManualGuideID", "/manual-guides", "ImageUrl"
    )

    search_model(
        Video,
        [Video.TitleEn, Video.DescriptionEn, Video.TitleAr, Video.DescriptionAr],
        "VideoID", "/videos", "ImagePath"
    )

    return results


# ==========================================
# Search Endpoint
# ==========================================
@router.get("/")
def search(
    request: Request,
    query: str = Query(...),
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    try:
        if not query.strip():
            return error_response("Query cannot be empty.", "الاستعلام فارغ.")

        skip = (page - 1) * limit
        results = global_search(db, query, request, skip, limit)

        if not results:
            return error_response("No results found.", "لا توجد نتائج.", "NOT_FOUND")

        return success_response(
            "Success",
            "تم بنجاح",
            {
                "page": page,
                "limit": limit,
                "count": len(results),
                "results": results
            }
        )

    except Exception as e:
        print("ERROR:", e)
        return error_response("Internal error", "خطأ داخلي", "INTERNAL_ERROR")
