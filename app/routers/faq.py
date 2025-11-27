from fastapi import APIRouter, Depends, status, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.models.faq import FAQ
from app.models.lookups import FAQCategory
from app.models.users import User
from app.schemas.faq import FAQResponse, FAQCreate, FAQUpdate
from app.schemas.lookups import FAQCategoryResponse
from app.utils.response import success_response, error_response
from app.database import get_db
from app.utils.utils import require_admin
from rapidfuzz import fuzz, process

router = APIRouter(prefix="/faq", tags=["FAQ"])

# ----------------------
# Public Endpoints
# ----------------------

@router.get("/search")
def search_faqs(
    query: str = Query(..., min_length=2, description="Search text for FAQ"),
    lang: str = Query("en", description="Language code: en or ar"),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Search FAQs by keyword (supports English & Arabic)
    Optionally filter by category
    Returns top 3 matching results ordered by similarity
    """

    faq_query = db.query(FAQ).filter(FAQ.IsDelete == False)
    if category_id:
        faq_query = faq_query.filter(FAQ.CategoryID == category_id)
    faqs = faq_query.all()

    if not faqs:
        return error_response("No FAQs found in the database.", "لا يوجد نتائج", error_code= "EMPTY_FAQ_LIST")

    # Select language
    if lang.lower() == "ar":
        faq_data = [
            {"id": f.FAQID, "question": f.QuestionAr or "", "answer": f.AnswerAr or ""}
            for f in faqs if f.QuestionAr
        ]
    else:
        faq_data = [
            {"id": f.FAQID, "question": f.QuestionEn or "", "answer": f.AnswerEn or ""}
            for f in faqs if f.QuestionEn
        ]

    if not faq_data:
        return error_response("No FAQs available in the selected language." ,"لا يوجد نتائج للغة التى اخترتها", error_code="NO_LANG_DATA")

    # Calculate similarity
    questions = [f["question"] for f in faq_data]
    matches = process.extract(query, questions, scorer=fuzz.token_sort_ratio, limit=10)

    results = []
    for text, score, idx in matches:
        if score >= 20:  # similarity threshold
            item = faq_data[idx]
            results.append({
                "FAQID": item["id"],
                "QuestionEn": item["question"] if lang == "en" else None,
                "QuestionAr": item["question"] if lang == "ar" else None,
                "AnswerEn": item["answer"] if lang == "en" else None,
                "AnswerAr": item["answer"] if lang == "ar" else None,
                "Score": round(score, 2)
            })

    if not results:
        # static chatbot fallback
        fallback = {
            "message": "Sorry, No FAQ matched",
            "contact": {
                "email": "support@example.com",
                "phone": "+966-123-456-789",
                "link": "https://yourwebsite.com/contact"
            }
        }
        return success_response("No FAQ matched.", "لا يوجد نتائج" ,data=fallback)

    # sort & return top 3
    results = sorted(results, key=lambda x: x["Score"], reverse=True)[:3]
    return success_response("Top matching FAQs retrieved successfully.","اعلى نتائج البحث" ,  results)


# ----------------------
# Get all categories
# ----------------------
@router.get("/categories")
def get_faq_categories(db: Session = Depends(get_db)):
    categories = (
        db.query(FAQCategory)
        .filter(FAQCategory.IsDelete == False)
        .order_by(FAQCategory.NameEn)
        .all()
    )

    if not categories:
        return error_response("No FAQ categories found.", "NO_CATEGORIES")

    return success_response("FAQ categories retrieved successfully.", data = categories)


# ----------------------
# Get all FAQs
# ----------------------
@router.get("/")
def get_faqs(category_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(FAQ).filter(FAQ.IsDelete == False)
    if category_id:
        query = query.filter(FAQ.CategoryID == category_id)
    faqs = query.order_by(FAQ.CreatedAt.desc()).all()

    if not faqs:
        return error_response("No FAQs found.",error_code="NO_FAQS")

    return success_response("FAQs retrieved successfully.", data = faqs)


# ----------------------
# Admin Endpoints: Categories
# ----------------------
@router.post("/admin/categories/create")
def create_faq_category(
    NameEn: str = Form(...),
    NameAr: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = FAQCategory(NameEn=NameEn, NameAr=NameAr, IsDelete=False)
    db.add(category)
    db.commit()
    db.refresh(category)
    return success_response("FAQ category created successfully.", data =  category)


@router.put("/admin/categories/{category_id}")
def update_faq_category(
    category_id: int,
    NameEn: Optional[str] = Form(None),
    NameAr: Optional[str] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = db.query(FAQCategory).filter(
        FAQCategory.CategoryID == category_id,
        FAQCategory.IsDelete == False
    ).first()
    if not category:
        return error_response("FAQ category not found.",error_code= "NOT_FOUND")

    if NameEn is not None:
        category.NameEn = NameEn
    if NameAr is not None:
        category.NameAr = NameAr

    db.commit()
    db.refresh(category)
    return success_response("FAQ category updated successfully.",data= category)


@router.delete("/admin/categories/{category_id}")
def delete_faq_category(
    category_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    category = db.query(FAQCategory).filter(
        FAQCategory.CategoryID == category_id,
        FAQCategory.IsDelete == False
    ).first()
    if not category:
        return error_response("FAQ category not found.",error_code= "NOT_FOUND")

    category.IsDelete = True
    db.commit()
    return success_response("FAQ category soft-deleted successfully.","تم الحذف بنجاح")


# ----------------------
# Admin Endpoints: FAQs
# ----------------------
@router.post("/admin/create")
def create_faq(
    QuestionEn: str = Form(...),
    QuestionAr: Optional[str] = Form(None),
    AnswerEn: Optional[str] = Form(None),
    AnswerAr: Optional[str] = Form(None),
    CategoryID: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if CategoryID:
        category = db.query(FAQCategory).filter(
            FAQCategory.CategoryID == CategoryID,
            FAQCategory.IsDelete == False
        ).first()
        if not category:
            return error_response("FAQ category not found.",error_code= "INVALID_CATEGORY")

    faq = FAQ(
        QuestionEn=QuestionEn,
        QuestionAr=QuestionAr,
        AnswerEn=AnswerEn,
        AnswerAr=AnswerAr,
        CategoryID=CategoryID,
        CreatedAt=datetime.utcnow(),
        CreatedByUserID=current_user.UserID,
        IsDelete=False
    )
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return success_response("FAQ created successfully.", data= faq)


@router.get("/admin/{faq_id}")
def get_faq(
    faq_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    faq = db.query(FAQ).filter(FAQ.FAQID == faq_id, FAQ.IsDelete == False).first()
    if not faq:
        return error_response("FAQ not found.",error_code= "NOT_FOUND")
    return success_response("FAQ retrieved successfully.",data= faq)


@router.put("/admin/{faq_id}")
def update_faq(
    faq_id: int,
    QuestionEn: Optional[str] = Form(None),
    QuestionAr: Optional[str] = Form(None),
    AnswerEn: Optional[str] = Form(None),
    AnswerAr: Optional[str] = Form(None),
    CategoryID: Optional[int] = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    faq = db.query(FAQ).filter(FAQ.FAQID == faq_id, FAQ.IsDelete == False).first()
    if not faq:
        return error_response("FAQ not found.", error_code="NOT_FOUND")

    if CategoryID:
        category = db.query(FAQCategory).filter(
            FAQCategory.CategoryID == CategoryID,
            FAQCategory.IsDelete == False
        ).first()
        if not category:
            return error_response("FAQ category not found.", error_code="INVALID_CATEGORY")

    if QuestionEn is not None:
        faq.QuestionEn = QuestionEn
    if QuestionAr is not None:
        faq.QuestionAr = QuestionAr
    if AnswerEn is not None:
        faq.AnswerEn = AnswerEn
    if AnswerAr is not None:
        faq.AnswerAr = AnswerAr
    if CategoryID is not None:
        faq.CategoryID = CategoryID

    faq.UpdatedAt = datetime.utcnow()
    faq.UpdatedByUserID = current_user.UserID

    db.commit()
    db.refresh(faq)
    return success_response("FAQ updated successfully.", data=faq)


@router.delete("/admin/{faq_id}")
def delete_faq(
    faq_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    faq = db.query(FAQ).filter(FAQ.FAQID == faq_id, FAQ.IsDelete == False).first()
    if not faq:
        return error_response("FAQ not found.",error_code= "NOT_FOUND")

    faq.IsDelete = True
    db.commit()
    return success_response("FAQ soft-deleted successfully.")
