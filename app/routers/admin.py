# routers/admin.py
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime
import os
import shutil

from app.database import get_db
from app.auth.jwt_bearer import JWTBearer
from app.utils.response import success_response, error_response
from app.utils.email import send_reply_email, send_email_with_attachment, ADMIN_UPLOAD_DIR
from app.models.users import User
from app.models.lookups import Category, Status, ComplaintScreen, RequestInformation, Format, Projection
from app.models.requests import Request, Reply, Request_RequestInformation, Request_Format

router = APIRouter(prefix="/admin", tags=["Admin"])

# ------------------------
# Auth & Role Dependencies
# ------------------------
def get_current_user(payload: dict = Depends(JWTBearer()), db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.UserID == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.RoleID != 1:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return user

# ------------------------
# Assign role to request
# ------------------------
@router.post("/assign_request")
def assign_request(
    request_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    req = db.query(Request).filter(Request.Id == request_id).first()
    if not req:
        return error_response(
            message_en="Request not found",
            message_ar="الطلب غير موجود",
            error_code="REQUEST_NOT_FOUND"
        )
    req.AssignedRoleId = role_id
    db.commit()
    return success_response(
        message_en="Request assigned successfully",
        message_ar="تم تعيين الطلب بنجاح",
        data={"request_id": req.Id}
    )

# ------------------------
# List all requests (Admin only)
# ------------------------
@router.get("/requests")
def list_requests(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(25, ge=1, le=200, description="Page size"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    skip = (page - 1) * limit
    base_query = (
        db.query(Request, Status, Category, User)
        .join(Status, Request.StatusId == Status.Id, isouter=True)
        .join(Category, Request.CategoryId == Category.Id, isouter=True)
        .join(User, Request.UserId == User.UserID, isouter=True)
        .order_by(Request.CreatedAt.desc())
    )

    paged_requests = base_query.offset(skip).limit(limit).all()
    total_requests = db.query(Request).count()

    results = []
    for req, status, category, user in paged_requests:
        results.append({
            "id": req.Id,
            "number": req.RequestNumber,
            "created_at": req.CreatedAt,
            "status_name_en": status.Name if status else None,
            "status_name_ar": status.Name_Ar if status else None,
            "type_name_en": category.Name if category else None,
            "type_name_ar": category.Name_Ar if category else None,
            "user_email": user.Email if user else None,
            "subject": req.Subject,
            "body": req.Body,
            "AssignedRoleId": req.AssignedRoleId
        })

    payload = {
        "page": page,
        "limit": limit,
        "count": len(results),
        "total": total_requests,
        "requests": results
    }

    return success_response(
        message_en="Requests fetched successfully",
        message_ar="تم جلب الطلبات بنجاح",
        data=payload
    )

# ------------------------
# Get one request details (Admin only)
# ------------------------
@router.get("/request-details/")
def get_request_details(
    request_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    req = db.query(Request).filter(Request.Id == request_id).first()
    if not req:
        return error_response(
            message_en="Request not found",
            message_ar="الطلب غير موجود",
            error_code="REQUEST_NOT_FOUND"
        )

    user = db.query(User).filter(User.UserID == req.UserId).first() if req.UserId else None
    category = db.query(Category).filter(Category.Id == req.CategoryId).first() if req.CategoryId else None
    status = db.query(Status).filter(Status.Id == req.StatusId).first() if req.StatusId else None
    complaint_screen = (
        db.query(ComplaintScreen).filter(ComplaintScreen.Id == req.ComplaintScreenId).first()
        if req.ComplaintScreenId else None
    )

    request_info = (
        db.query(RequestInformation)
        .join(Request_RequestInformation, Request_RequestInformation.c.RequestInformationId == RequestInformation.Id)
        .filter(Request_RequestInformation.c.RequestId == req.Id)
        .all()
    )
    formats = (
        db.query(Format)
        .join(Request_Format, Request_Format.c.FormatId == Format.Id)
        .filter(Request_Format.c.RequestId == req.Id)
        .all()
    )
    replies = db.query(Reply).filter(Reply.RequestId == req.Id, Reply.IsDeleted == False).all()

    request_data_details = {}
    if category and category.Id == 8:  # RequestData
        from app.models.requests import RequestData
        rd = db.query(RequestData).filter(RequestData.RequestId == req.Id).first()
        if rd:
            projection = db.query(Projection).filter(Projection.Id == rd.ProjectionId).first() if rd.ProjectionId else None
            request_data_details = {
                "prospective_name": rd.ProspectiveName,
                "coordinates": {
                    "top_left": rd.Coordinate_TopLeft,
                    "bottom_right": rd.Coordinate_BottomRight
                } if rd.Coordinate_TopLeft or rd.Coordinate_BottomRight else {},
                "projection": projection.Name if projection else None,
                "other_specification": rd.OtherSpecification,
                "other_format": rd.OtherFormat,
                "intended_purpose": rd.IntendedPurpose,
                "requirements_details": rd.RequirementsDetails,
                "created_at": rd.CreatedAt,
            }

    details = {
        "id": req.Id,
        "number": req.RequestNumber,
        "status": {"Name_ar": status.Name_Ar, "Name_En": status.Name} if status else {},
        "type": {"Name_ar": category.Name_Ar, "Name_En": category.Name} if category else {},
        "user_email": user.Email if user else None,
        "subject": req.Subject,
        "body": req.Body,
        "complaint_screen": {"Name_ar": complaint_screen.Name_Ar, "Name_En": complaint_screen.Name} if complaint_screen else {},
        "assigned_role_id": req.AssignedRoleId,
        "attach_path": req.AttachPath,
        "created_at": req.CreatedAt,
        "created_by": req.CreatedByUserID,
        "updated_at": req.UpdatedAt,
        "updated_by": req.UpdatedByUserID,
        "request_information": [{"Name_Ar": ri.Name_Ar, "name": ri.Name} for ri in request_info] if request_info else [],
        "formats": [{"name": f.Name} for f in formats] if formats else [],
        "replies": [
            {
                "id": reply.Id,
                "subject": reply.Subject,
                "body": reply.Body,
                "attachment_path": reply.AttachmentPath,
                "created_at": reply.CreatedAt,
                "created_by": reply.CreatedByUserID,
                "responder_user_id": reply.ResponderUserId,
            }
            for reply in replies
        ] if replies else [],
        **request_data_details
    }

    return success_response(
        message_en="Request details fetched successfully",
        message_ar="تم جلب تفاصيل الطلب بنجاح",
        data={"request": details}
    )

# ------------------------
# List requests assigned to current admin role
# ------------------------
@router.get("/assigned_requests")
def assigned_requests(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    requests = (
        db.query(Request, Status, Category, User)
        .filter(Request.AssignedRoleId == user.RoleID)
        .join(Status, Request.StatusId == Status.Id, isouter=True)
        .join(Category, Request.CategoryId == Category.Id, isouter=True)
        .join(User, Request.UserId == User.UserID, isouter=True)
        .all()
    )

    results = []
    for req, status, category, user in requests:
        results.append({
            "id": req.Id,
            "number": req.RequestNumber,
            "created_at": req.CreatedAt,
            "status_name_en": status.Name if status else None,
            "status_name_ar": status.Name_Ar if status else None,
            "type_name_en": category.Name if category else None,
            "type_name_ar": category.Name_Ar if category else None,
            "user_email": user.Email if user else None,
            "subject": req.Subject,
            "body": req.Body
        })

    return success_response(
        message_en="Assigned requests fetched successfully",
        message_ar="تم جلب الطلبات المخصصة بنجاح",
        data={"requests": results}
    )

# ------------------------
# Admin reply to a request (with optional attachment)
# ------------------------
@router.post("/reply")
def admin_reply(
    request_id: int,
    status_id: int,  
    subject: str = None,
    body: str = None,
    attachment: UploadFile = File(None),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    req = db.query(Request).filter(Request.Id == request_id).first()
    if not req:
        return error_response(
            message_en="Request not found",
            message_ar="الطلب غير موجود",
            error_code="REQUEST_NOT_FOUND"
        )

    attachment_path = None
    if attachment:
        orig_name = os.path.basename(attachment.filename)
        filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{orig_name.replace(' ', '_')}"
        attachment_path = os.path.join(ADMIN_UPLOAD_DIR, filename)
        with open(attachment_path, "wb") as buffer:
            shutil.copyfileobj(attachment.file, buffer)
        attachment_path = f"requests/reply/{filename}"   

    new_reply = Reply(
        RequestId=request_id,
        Subject=subject,
        Body=body,
        AttachmentPath=attachment_path,
        ResponderUserId=user.UserID,
        CreatedAt=datetime.utcnow(),
        CreatedByUserID=user.UserID
    )
    db.add(new_reply)
    req.StatusId = status_id
    req.UpdatedAt = datetime.utcnow()
    req.UpdatedByUserID = user.UserID
    db.commit()
    db.refresh(new_reply)
    db.refresh(req)

    request_owner = db.query(User).filter(User.UserID == req.UserId).first()
    if not request_owner or not request_owner.Email:
        return error_response(
            message_en="Request owner email not found",
            message_ar="بريد صاحب الطلب غير موجود",
            error_code="USER_EMAIL_NOT_FOUND"
        )

    user_email = request_owner.Email
    email_subject = f"NGD - Response to your request {req.RequestNumber}"
    email_body = f"""
    <h4>Dear {request_owner.FirstName},</h4>
    <p>Your request <b>{req.RequestNumber}</b> has received a reply:</p>
    <p>{body or 'No message provided'}</p>
    <p>Thank you, NGD Team</p>
    """

    if attachment_path:
        background_tasks.add_task(send_email_with_attachment, email_subject, email_body, user_email, attachment_path)
    else:
        background_tasks.add_task(send_reply_email, email_subject, email_body, user_email)

    return success_response(
        message_en="Reply sent successfully",
        message_ar="تم إرسال الرد بنجاح",
        data={"reply_id": new_reply.Id, "new_status": status_id, "request_id": req.Id}
    )
