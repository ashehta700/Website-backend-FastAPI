# routers/requests.py
from fastapi import APIRouter, Depends, BackgroundTasks, File, UploadFile, Form, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.lookups import Category, Format, Projection, RequestInformation, Status, ComplaintScreen
from app.models.requests import Request
from app.models.users import User
from app.schemas.lookups import (
    CategorySchema, FormatSchema, ProjectionSchema,
    RequestInformationSchema, StatusSchema, ComplaintScreenSchema
)
from app.utils.response import success_response, error_response
from app.utils.email import send_email, send_email_with_attachment, REQUEST_DIR, SYSTEM_EMAIL
from datetime import datetime
import os
import shutil
from typing import Optional, List
from app.utils.utils import get_current_user
from sqlalchemy import text

router = APIRouter(prefix="/requests", tags=["Requests"])


# ---------------- Lookup Endpoint ----------------
@router.get("/lookups")
def get_lookups(db: Session = Depends(get_db)):
    categories = db.query(Category).filter(Category.IsDeleted == 0).all()
    projections = db.query(Projection).all()
    formats = db.query(Format).filter(Format.IsDeleted == 0).all()
    request_info = db.query(RequestInformation).filter(RequestInformation.IsDeleted == 0).all()
    statuses = db.query(Status).all()
    complaint_screens = db.query(ComplaintScreen).filter(ComplaintScreen.IsDeleted == 0).all()

    return success_response(
        "Lookup data fetched successfully",
        "تم جلب بيانات القوائم بنجاح",
        {
            "categories": [CategorySchema.from_orm(c).dict() for c in categories],
            "projections": [ProjectionSchema.from_orm(p).dict() for p in projections],
            "formats": [FormatSchema.from_orm(f).dict() for f in formats],
            "request_information": [RequestInformationSchema.from_orm(r).dict() for r in request_info],
            "statuses": [StatusSchema.from_orm(s).dict() for s in statuses],
            "complaint_screens": [ComplaintScreenSchema.from_orm(cs).dict() for cs in complaint_screens],
        }
    )


# ---------------- Create Request Endpoint ----------------
@router.post("/")
def create_request(
    background_tasks: BackgroundTasks,
    CategoryId: int = Form(...),
    ComplaintScreenId: Optional[int] = Form(None),
    Subject: Optional[str] = Form(None),
    Body: Optional[str] = Form(None),
    ProspectiveName: Optional[str] = Form(None),
    Coordinate_TopLeft: Optional[str] = Form(None),
    Coordinate_BottomRight: Optional[str] = Form(None),
    ProjectionId: Optional[int] = Form(None),
    OtherSpecification: Optional[str] = Form(None),
    OtherFormat: Optional[str] = Form(None),
    IntendedPurpose: Optional[str] = Form(None),
    RequirementsDetails: Optional[str] = Form(None),
    RequestInformationIds: Optional[str] = Form(None),
    FormatIds: Optional[str] = Form(None),
    attach: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # ---------------- 1) Save attachment ----------------
    attach_rel = None
    if attach:
        safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{attach.filename.replace(' ', '_')}"
        save_path = os.path.join(REQUEST_DIR, safe_name)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(attach.file, buffer)
        attach_rel = f"requests/{safe_name}"

    # ---------------- 2) Generate Request Number ----------------
    last_request = db.query(Request).order_by(Request.Id.desc()).first()
    next_number = 1 if not last_request else last_request.Id + 1
    request_number = f"RQ-{datetime.now().strftime('%Y%m%d')}-{str(next_number).zfill(4)}"

    # ---------------- 3) Validate Projection ----------------
    if ProjectionId in (0, "0", "", None):
        ProjectionId = None
    elif ProjectionId and not db.query(Projection).filter(Projection.Id == ProjectionId).first():
        return error_response("Invalid ProjectionId", "معرف الإسقاط غير صالح")

    # ---------------- 4) Create main request ----------------
    new_request = Request(
        UserId=user.UserID,
        CategoryId=CategoryId,
        ComplaintScreenId=ComplaintScreenId,
        Subject=Subject,
        Body=Body,
        AssignedRoleId=None,
        RequestNumber=request_number,
        StatusId=7,
        CreatedAt=datetime.utcnow(),
        AttachPath=attach_rel
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    # ---------------- 5) Create RequestData (Category = 8) ----------------
    if CategoryId == 8:
        from app.models.requests import RequestData
        data = RequestData(
            RequestId=new_request.Id,
            ProspectiveName=ProspectiveName,
            Coordinate_TopLeft=Coordinate_TopLeft,
            Coordinate_BottomRight=Coordinate_BottomRight,
            ProjectionId=ProjectionId,
            OtherSpecification=OtherSpecification,
            OtherFormat=OtherFormat,
            IntendedPurpose=IntendedPurpose,
            RequirementsDetails=RequirementsDetails,
            CreatedAt=datetime.utcnow()
        )
        db.add(data)
        db.commit()

    # ---------------- 6) Insert M2M relationships ----------------
    def parse_list(v):
        return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()] if v else []

    for info_id in parse_list(RequestInformationIds):
        db.execute(
            text("INSERT INTO [Requests].[Request_RequestInformation] (RequestId, RequestInformationId) VALUES (:r, :i)"),
            {"r": new_request.Id, "i": info_id}
        )
    for fmt in parse_list(FormatIds):
        db.execute(
            text("INSERT INTO [Requests].[Request_Format] (RequestId, FormatId) VALUES (:r, :f)"),
            {"r": new_request.Id, "f": fmt}
        )
    db.commit()

    # ---------------- 7) Prepare Emails ----------------
    category = db.query(Category).filter(Category.Id == CategoryId).first()
    category_name = category.Name if category else "Unknown Category"

    admin_body = f"""
    <div style='font-family:Arial,sans-serif;color:#1f2937;max-width:620px;margin:auto;'>
        <h2 style='color:#2563eb;'>New Request Received</h2>
        <p>A new request has been submitted.</p>
        <div style='background:#f3f4f6;padding:16px;border-radius:8px;'>
            <p><strong>User:</strong> {user.FirstName} ({user.Email})</p>
            <p><strong>Category:</strong> {category_name}</p>
            <p><strong>Request Number:</strong> {request_number}</p>
            <p><strong>Subject:</strong> {Subject or 'N/A'}</p>
            <p><strong>Body:</strong> {Body or 'N/A'}</p>
        </div>
    </div>
    """

    if attach_rel:
        background_tasks.add_task(send_email_with_attachment, f"New Request {request_number} - {category_name}", admin_body, SYSTEM_EMAIL, attach_rel)
    else:
        background_tasks.add_task(send_email, f"New Request {request_number} - {category_name}", admin_body, SYSTEM_EMAIL)

    user_body = f"""
    <div style='font-family:Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;'>
        <h2 style='color:#2563eb;'>Your request has been received</h2>
        <p>Hello {user.FirstName}, we received your request and our team will contact you soon.</p>
        <div style='background:#f3f4f6;padding:16px;border-radius:8px;'>
            <p><strong>Request Number:</strong> {request_number}</p>
            <p><strong>Category:</strong> {category_name}</p>
        </div>
    </div>
    """
    background_tasks.add_task(send_email, f"NGD - Request {request_number} received", user_body, user.Email)

    # ---------------- 8) Response ----------------
    return success_response(
        "Request created successfully",
        "تم إنشاء الطلب بنجاح",
        {
            "request_id": new_request.Id,
            "request_number": request_number,
            "AttachPath": attach_rel
        }
    )
