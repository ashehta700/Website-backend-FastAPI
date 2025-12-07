from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from sqlalchemy import func , or_
from datetime import datetime
from typing import Optional, List
from app.models.users import User
from app.models.survey import UsersFeedbackQuestion, QuestionChoice, UsersFeedbackAnswer , Vote
from app.schemas.survey import BulkAnswerRequest
from app.auth.jwt_bearer import JWTBearer
from app.utils.response import success_response, error_response
from sqlalchemy.orm import Session, joinedload 
from app.database import get_db
from app.utils.utils import clean_text , _resolve_identity  
from app.utils.utils import get_current_user ,require_admin



router = APIRouter(prefix="/survey", tags=["Survey"])





# -------------------------------
# 1) POST  Data For Vote Question on home Page 
# -------------------------------
def _resolve_identity(request: Request, token_payload: dict):
    """
    Helper: resolve identity from JWT or request cookies
    """
    user_id = None
    visitor_id = None

    if token_payload and "user_id" in token_payload:
        user_id = token_payload["user_id"]

    # If user is not authenticated, try to get visitor_id from cookies or headers
    if not user_id:
        visitor_id = request.cookies.get("visitor_id") or request.headers.get("X-Visitor-Id")

    return user_id, visitor_id




@router.post("/vote")
def submit_vote(
    Answer: str = Body(..., embed=True),
    SubAnswer: str = Body(None, embed=True),
    request: Request = None,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(JWTBearer(auto_error=False))
):
    """
    Submit a user or visitor vote.
    - Prevents duplicate voting.
    - Stores "No" votes with optional SubAnswer.
    """
    user_id, visitor_id = _resolve_identity(request, token_payload)

    # ✅ Validate input
    if Answer not in ["Yes", "No"]:
        return error_response("Answer must be 'Yes' or 'No'.", error_code= "INVALID_ANSWER")

    if not user_id and not visitor_id:
        return error_response("Either UserId or VisitorId is required.",error_code= "NO_IDENTITY")

    # ✅ Check if user or visitor already voted
    # existing_vote = (
    #     db.query(Vote)
    #     .filter(
    #         (Vote.UserId == user_id) if user_id else (Vote.VisitorId == visitor_id)
    #     )
    #     .first()
    # )

    # if existing_vote:
    #     # Return existing info — no new vote created
    #     return success_response("User has already voted before.", data={
    #         "AlreadyVoted": True,
    #         "Id": existing_vote.Id,
    #         "Answer": existing_vote.Answer,
    #         "SubAnswer": existing_vote.SubAnswer,
    #         "CreatedAt": existing_vote.CreatedAt,
    #     })

    # ✅ Create new vote
    vote = Vote(
        UserId=user_id if user_id else None,
        VisitorId=visitor_id if visitor_id else None,
        Answer=Answer,
        SubAnswer=SubAnswer if Answer == "No" else None,
        CreatedAt=datetime.utcnow()
    )

    db.add(vote)
    db.commit()
    db.refresh(vote)

    return success_response("Vote submitted successfully.","تم التصويت بنجاح", data={
        "AlreadyVoted": False,
        "Id": vote.Id,
        "Answer": vote.Answer,
        "SubAnswer": vote.SubAnswer,
        "UserId": vote.UserId,
        "VisitorId": vote.VisitorId,
        "CreatedAt": vote.CreatedAt,
    })


# -------------------------------
# 2) Get All Statistics for Vote Question on Home Page 
# -------------------------------
@router.get("/vote/stats")
def get_vote_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Vote.Id)).scalar() or 0
    yes_count = db.query(func.count(Vote.Id)).filter(Vote.Answer == "Yes").scalar() or 0
    no_count = db.query(func.count(Vote.Id)).filter(Vote.Answer == "No").scalar() or 0

    percentage_yes = round((yes_count / total) * 100, 2) if total > 0 else 0
    percentage_no = round((no_count / total) * 100, 2) if total > 0 else 0

    return success_response("Vote statistics", data={
        "total_votes": total,
        "yes_votes": yes_count,
        "no_votes": no_count,
        "yes_percentage": percentage_yes,
        "no_percentage": percentage_no
    })







# -------------------------------
# 3) GET all survey questions - Grouped by Category
# -------------------------------
@router.get("/questions")
def get_questions(db: Session = Depends(get_db)):
    # Fetch all questions where IsDeleted is False or NULL
    questions = (
        db.query(UsersFeedbackQuestion)
        .filter(or_(UsersFeedbackQuestion.IsDeleted == False, UsersFeedbackQuestion.IsDeleted == None))
        .options(
            joinedload(UsersFeedbackQuestion.category),
            joinedload(UsersFeedbackQuestion.type),
            joinedload(UsersFeedbackQuestion.choices),
        )
        .all()
    )

    # Group by category
    categories_dict = {}
    for q in questions:
        category_key = q.category.Id if q.category else "Uncategorized"

        if category_key not in categories_dict:
            categories_dict[category_key] = {
                "CategoryId": q.category.Id if q.category else None,
                "Category_en": q.category.Category if q.category else "Uncategorized",
                "Category_ar": q.category.Category_Ar if q.category else "غير مصنف",
                "Questions": []
            }

        question_data = {
            "Id": q.Id,
            "MainQuestion_en": clean_text(q.MainQuestion),
            "MainQuestion_ar": clean_text(q.MainQuestion_Ar),
            "Type": {
                "Id": q.type.Id if q.type else None,
                "Type_en": q.type.TypeOfQuestion if q.type else None,
            } if q.type else None,
        }

        # Only add choices if they exist
        choices = [
            {
                "ChoiceId": c.Id,
                "Choice_en": clean_text(c.Choice),
                "Choice_ar": clean_text(c.Choice_Ar),
            }
            for c in (q.choices or []) if c.IsDeleted in [False, None]
        ]
        if choices:
            question_data["Choices"] = choices

        categories_dict[category_key]["Questions"].append(question_data)

    # Convert dict → list
    categories_list = list(categories_dict.values())

    return success_response("Survey questions grouped by category", data={"categories": categories_list})




# -------------------------------
# 4) POST bulk answers (multi-choice or text)
# -------------------------------
@router.post("/answers")
def submit_bulk_answers(
    payload: BulkAnswerRequest,
    request: Request = None,
    db: Session = Depends(get_db),
    token_payload: Optional[dict] = Depends(JWTBearer(auto_error=False))
):
    user_id, visitor_id = _resolve_identity(request, token_payload)

    # Ensure we have at least one identity
    if not user_id and not visitor_id:
        raise HTTPException(status_code=400, detail="Either UserId or VisitorId is required.")

    if not payload.answers:
        raise HTTPException(status_code=400, detail="No answers provided.")

    db_answers = []

    for item in payload.answers:
        # Validate: either ChoiceId or TextAnswer must be provided
        if not item.ChoiceId and not item.TextAnswer:
            raise HTTPException(
                status_code=400,
                detail=f"Either ChoiceId or TextAnswer is required for QuestionId {item.QuestionId}"
            )

        # Validate QuestionId exists
        question_exists = db.query(UsersFeedbackQuestion).filter(
            UsersFeedbackQuestion.Id == item.QuestionId,
            UsersFeedbackQuestion.IsDeleted == False
        ).first()
        if not question_exists:
            raise HTTPException(status_code=400, detail=f"Invalid QuestionId: {item.QuestionId}")

        # Normalize ChoiceId into a list
        choices = [item.ChoiceId] if isinstance(item.ChoiceId, int) else (item.ChoiceId or [])

        # Validate all choices exist for this question
        if choices:
            valid_choices = db.query(QuestionChoice.Id).filter(
                QuestionChoice.QuestionId == item.QuestionId,
                QuestionChoice.Id.in_(choices)
            ).all()
            valid_choice_ids = {c.Id for c in valid_choices}
            invalid = set(choices) - valid_choice_ids
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid ChoiceId(s) {list(invalid)} for QuestionId {item.QuestionId}"
                )

        # Insert one record per choice
        for choice_id in choices:
            answer = UsersFeedbackAnswer(
                VisitorId=visitor_id,
                QuestionId=item.QuestionId,
                ChoiceId=choice_id,
                please_specify=item.TextAnswer if item.TextAnswer else None,
                CreatedAt=datetime.utcnow(),
                CreatedByUserID=user_id if user_id else None,
            )
            db_answers.append(answer)

        # If no ChoiceId but there is TextAnswer → insert text-only record
        if not choices and item.TextAnswer:
            answer = UsersFeedbackAnswer(
                VisitorId=visitor_id,
                QuestionId=item.QuestionId,
                ChoiceId=None,
                please_specify=item.TextAnswer,
                CreatedAt=datetime.utcnow(),
                CreatedByUserID=user_id if user_id else None,
            )
            db_answers.append(answer)

    # Save to DB
    db.add_all(db_answers)
    db.commit()

    # Refresh IDs
    for answer in db_answers:
        db.refresh(answer)

    return success_response(
        "Bulk answers submitted",data=
        [
            {
                "Id": a.Id,
                "QuestionId": a.QuestionId,
                "ChoiceId": a.ChoiceId,
                "TextAnswer": a.please_specify,
                "VisitorId": a.VisitorId,
                "UserId": a.CreatedByUserID,
            }
            for a in db_answers
        ]
    )




# ========================================================================================
#                               ADMIN SURVEY ENDPOINTS
# ========================================================================================

@router.get("/admin/stats")
def get_survey_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin: summary of full survey statistics"""
    require_admin(current_user)

    # Total answers submitted
    total_answers = db.query(func.count(UsersFeedbackAnswer.Id)).scalar() or 0

    # Distinct respondents
    distinct_users = (
        db.query(UsersFeedbackAnswer.CreatedByUserID)
        .filter(UsersFeedbackAnswer.CreatedByUserID.isnot(None))
        .distinct()
        .count()
    )

    distinct_visitors = (
        db.query(UsersFeedbackAnswer.VisitorId)
        .filter(UsersFeedbackAnswer.VisitorId.isnot(None))
        .distinct()
        .count()
    )

    total_respondents = distinct_users + distinct_visitors

    # Question-level statistics
    question_stats = []
    questions = db.query(UsersFeedbackQuestion).all()

    for q in questions:
        answer_count = (
            db.query(func.count(UsersFeedbackAnswer.Id))
            .filter(UsersFeedbackAnswer.QuestionId == q.Id)
            .scalar()
        )

        # Count choices per question
        choice_counts = (
            db.query(
                QuestionChoice.Choice,
                func.count(UsersFeedbackAnswer.Id).label("count")
            )
            .join(
                UsersFeedbackAnswer,
                UsersFeedbackAnswer.ChoiceId == QuestionChoice.Id,
                isouter=True
            )
            .filter(QuestionChoice.QuestionId == q.Id)
            .group_by(QuestionChoice.Choice)
            .all()
        )

        question_stats.append({
            "QuestionId": q.Id,
            "Question_en": q.MainQuestion,
            "Question_ar": q.MainQuestion_Ar,
            "TotalAnswers": answer_count,
            "Choices": [{"choice": c[0], "count": c[1]} for c in choice_counts]
        })

    return success_response("Survey statistics loaded successfully", data={
        "total_answers": total_answers,
        "total_respondents": total_respondents,
        "users_count": distinct_users,
        "visitors_count": distinct_visitors,
        "questions": question_stats
    })



# ----------------------------
#  ADMIN – GET ALL USER RESPONSES (ONE ROW PER USER, NO VISITORS)
# ----------------------------
@router.get("/admin/responses")
def get_all_user_responses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)

    # Get DISTINCT real users only
    user_ids = (
        db.query(UsersFeedbackAnswer.CreatedByUserID)
        .filter(UsersFeedbackAnswer.CreatedByUserID.isnot(None))
        .distinct()
        .all()
    )
    user_ids = [u[0] for u in user_ids]

    rows = []

    for uid in user_ids:
        user = db.query(User).filter(User.UserID == uid).first()
        if not user:
            continue

        answers = (
            db.query(UsersFeedbackAnswer)
            .join(UsersFeedbackQuestion, UsersFeedbackAnswer.QuestionId == UsersFeedbackQuestion.Id)
            .filter(UsersFeedbackAnswer.CreatedByUserID == uid)
            .all()
        )

        structured = {}
        for a in answers:
            text_val = a.please_specify or (a.choice.Choice if a.choice else None)
            if text_val:
                structured[a.question.MainQuestion] = text_val

        rows.append({
            "user_email": user.Email,
            "user_name": user.FirstName,
            "answers": structured
        })

    return success_response("Responses loaded successfully",data= rows)


# ----------------------------
# 2) ADMIN – USER RESPONSE DETAILS (ONLY USERS, FILTER BY EMAIL)
# ----------------------------
@router.get("/admin/response-details")
def get_response_details(
    email: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)

    query = db.query(User).join(UsersFeedbackAnswer, UsersFeedbackAnswer.CreatedByUserID == User.UserID).distinct()

    if email:
        query = query.filter(User.Email == email)

    users = query.all()

    output = []

    for user in users:
        answers = (
            db.query(UsersFeedbackAnswer)
            .join(UsersFeedbackQuestion, UsersFeedbackAnswer.QuestionId == UsersFeedbackQuestion.Id)
            .filter(UsersFeedbackAnswer.CreatedByUserID == user.UserID)
            .all()
        )

        detailed = []
        for a in answers:
            text_val = a.please_specify or (a.choice.Choice if a.choice else None)
            if not text_val:
                continue

            detailed.append({
                "question": a.question.MainQuestion,
                "answer": text_val,
                "created_at": a.CreatedAt
            })

        output.append({
            "user_email": user.Email,
            "user_name": user.FirstName,
            "answers": detailed
        })

    return success_response("User response details loaded",data= output)


# ----------------------------
# 3) ADMIN – SURVEY REPORT (EXCEL STRUCTURE FORMAT)
# ----------------------------
@router.get("/admin/export")
def export_survey_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin: export full survey dataset (users only)"""
    require_admin(current_user)

    # Get all users who have submitted survey answers
    users = (
        db.query(User)
        .join(UsersFeedbackAnswer, UsersFeedbackAnswer.CreatedByUserID == User.UserID)
        .distinct()
        .all()
    )

    # Get all questions in order
    questions = db.query(UsersFeedbackQuestion).order_by(UsersFeedbackQuestion.Id.asc()).all()

    report_rows = []

    for user in users:
        row = {
            "Answer time": None,
            # "Language": getattr(user, "Language", None),
            "User Email": user.Email,
            "User Name": f"{user.FirstName} {user.LastName}" if hasattr(user, "LastName") else user.FirstName,
        }

        # Get all answers for this user
        answers = (
            db.query(UsersFeedbackAnswer)
            .filter(UsersFeedbackAnswer.CreatedByUserID == user.UserID)
            .all()
        )

        # Map answers by question id
        answer_map = {a.QuestionId: a for a in answers if a.please_specify or a.ChoiceId}

        for q in questions:
            if q.Id in answer_map:
                a = answer_map[q.Id]
                if row["Answer time"] is None:
                    row["Answer time"] = a.CreatedAt
                row[q.MainQuestion] = a.please_specify or (a.choice.Choice if a.choice else None)
            else:
                row[q.MainQuestion] = None

        report_rows.append(row)

    return success_response("Export generated", "تم التصدير بنجاح",data=report_rows)
