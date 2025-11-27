# routers/chatbot.py
from fastapi import APIRouter, Depends, Body, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.response import success_response, error_response
from app.routers.search import global_search  # reuse global search logic

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

FALLBACK_MESSAGE = {
    "en": "Sorry, I couldn’t find an exact answer to that. You can contact our team at <a href='https://ngd.com/contact' target='_blank'>Customer Support</a> or call +966-XXX-XXXX.",
    "ar": "عذرًا، لم أجد إجابة دقيقة على سؤالك. يمكنك التواصل مع <a href='https://ngd.com/contact' target='_blank'>خدمة العملاء</a> أو الاتصال على +966-XXX-XXXX."
}

@router.post("/ask")
def ask_chatbot(
    request: Request,
    user_question: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """Chatbot endpoint that returns clean and minimal HTML response."""

    # Detect if user question is Arabic
    is_arabic = any("\u0600" <= ch <= "\u06FF" for ch in user_question)

    # -------------------------
    # Run search
    # -------------------------
    try:
        results = global_search(db, user_question, request, skip=0, limit=3)
    except Exception as e:
        return error_response(
            message_en=f"Error occurred while searching: {str(e)}",
            message_ar="حدث خطأ أثناء عملية البحث.",
            error_code="INTERNAL_ERROR"
        )

    # -------------------------
    # Fallback if no results
    # -------------------------
    if not results:
        fallback_msg = FALLBACK_MESSAGE["ar"] if is_arabic else FALLBACK_MESSAGE["en"]
        return success_response(
            message_en="No relevant answers found.",
            message_ar="لم يتم العثور على إجابات مناسبة.",
            data={"message": fallback_msg}
        )

    # -------------------------
    # Build response cards
    # -------------------------
    intro = (
        "وجدت بعض النتائج التي قد تساعدك:"
        if is_arabic else
        "I found a few things that might help you:"
    )

    html_cards = []
    for r in results:
        title = r.get("title", "")
        description = (r.get("description") or "")[:120]

        image_html = (
            f"<img src='{r['image']}' alt='' width='50' height='50' "
            f"style='border-radius:6px;margin-right:8px;' />"
            if r.get("image") else ""
        )

        card = (
            f"<div style='display:flex;align-items:center;margin-bottom:8px;'>"
            f"{image_html}"
            f"<div><a href='{r['url']}' target='_blank' "
            f"style='color:#0077cc;font-weight:bold;text-decoration:none;'>{title}</a>"
            f"<br><small>{description}...</small></div></div>"
        )
        html_cards.append(card)

    html_response = f"<p>{intro}</p>{''.join(html_cards)}"

    # -------------------------
    # Final Success Response
    # -------------------------
    return success_response(
        message_en="Chatbot search results retrieved successfully.",
        message_ar="تم جلب نتائج بحث المساعد بنجاح.",
        data={"message": html_response}
    )
