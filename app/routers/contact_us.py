# routers/contact_us.py
import os, shutil
from fastapi import APIRouter, Depends, UploadFile, File, Form, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from urllib.parse import quote
from typing import Optional
from app.database import get_db
from app.models.contact_us import ContactUs, ContactUsResponse
from app.models.users import User
from app.utils.email import send_email, send_email_with_attachment , CONTACT_DIR, SYSTEM_EMAIL
from app.utils.response import success_response, error_response
from app.utils.utils import get_optional_user, require_admin
from app.utils.paths import static_path

router = APIRouter(prefix="/contact-us", tags=["ContactUs"])


def build_file_url(request: Request, relative_path: Optional[str]) -> Optional[str]:
    if not relative_path:
        return None
    base = str(request.base_url).rstrip("/")
    return f"{base}/static/{quote(relative_path)}"


# ------------------ Public: Submit Contact ------------------
@router.post("/", response_model=dict)
def create_contact(
    request: Request,
    background_tasks: BackgroundTasks,
    FirstName: Optional[str] = Form(None),
    LastName: Optional[str] = Form(None),
    Subject: Optional[str] = Form(None),
    Body: Optional[str] = Form(None),
    Email: Optional[str] = Form(None),
    PhoneNumber: Optional[str] = Form(None),
    attach: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    # 1️⃣ Save attachment
    attach_rel = None
    if attach:
        os.makedirs(CONTACT_DIR, exist_ok=True)
        orig = os.path.basename(attach.filename)
        safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{orig.replace(' ', '_')}"
        save_path = os.path.join(CONTACT_DIR, safe_name)

        with open(save_path, "wb") as buff:
            shutil.copyfileobj(attach.file, buff)

        attach_rel = f"contact/{safe_name}"

    # 2️⃣ Auth or guest
    if current_user:
        user_email = current_user.Email
        PhoneNumber = current_user.PhoneNumber
        FirstName = current_user.FirstName
        LastName = current_user.LastName
        user_id = current_user.UserID
    else:
        user_email = Email
        user_id = None

    # 3️⃣ Store record
    new_contact = ContactUs(
        FirstName=FirstName,
        LastName=LastName,
        Subject=Subject,
        Body=Body,
        AttachPath=attach_rel,
        UserID=user_id,
        Email=user_email,
        PhoneNumber=PhoneNumber,
        ReplyStatus=False
    )

    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)

    # 4️⃣ Notify admin
    admin_subject = f"New ContactUs: {Subject or 'No subject'}"
    admin_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;">
        <h2 style="color:#2563eb;">New Contact Form Submitted</h2>
        <p>A new contact form has been submitted.</p>
        <ul>
            <li><strong>Name:</strong> {FirstName or ''} {LastName or ''}</li>
            <li><strong>Email:</strong> {user_email or 'N/A'}</li>
            <li><strong>Phone:</strong> {PhoneNumber or 'N/A'}</li>
            <li><strong>Subject:</strong> {Subject or 'N/A'}</li>
            <li><strong>Message:</strong> {Body or 'N/A'}</li>
            <li><strong>ContactID:</strong> {new_contact.ContactID}</li>
        </ul>
    </div>
    """

    if attach_rel:
        background_tasks.add_task(
            send_email_with_attachment,
            admin_subject,
            admin_body,
            SYSTEM_EMAIL,
            attach_rel
        )
    else:
        background_tasks.add_task(send_email, admin_subject, admin_body, SYSTEM_EMAIL)

    # 5️⃣ Notify user (bilingual HTML)
    if user_email:
        user_subject = f"NGD - We received your message"
        user_body = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;">
            <h2 style="color:#2563eb;">Message Received</h2>
            <p>Dear {FirstName or 'User'},</p>
            <p>We received your message (<strong>ID {new_contact.ContactID}</strong>).</p>
            <p>We will reply to you soon.</p>
            <hr style="margin:24px 0;">
            <p>عزيزي {FirstName or 'المستخدم'},</p>
            <p>لقد تلقينا رسالتك (<strong>رقم {new_contact.ContactID}</strong>).</p>
            <p>سوف نقوم بالرد عليك في أقرب وقت.</p>
            <p style="margin-top:32px;">Thanks / شكراً,<br/>NGD Team</p>
        </div>
        """
        if attach_rel:
            background_tasks.add_task(
                send_email_with_attachment,
                user_subject,
                user_body,
                user_email,
                attach_rel
            )
        else:
            background_tasks.add_task(send_email, user_subject, user_body, user_email)

    return success_response(
        message_en="Contact form submitted successfully.",
        message_ar="تم إرسال نموذج الاتصال بنجاح.",
        data={
            "ContactID": new_contact.ContactID,
            "EmailSentTo": user_email,
            "AttachPath": build_file_url(request, new_contact.AttachPath)
        }
    )
# ------------------ Admin: List Contacts ------------------
@router.get("/admin", response_model=dict)
def list_contacts_admin(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    contacts = db.query(ContactUs).order_by(ContactUs.CreatedAt.desc()).all()
    out = []

    for c in contacts:
        out.append({
            "ContactID": c.ContactID,
            "FirstName": c.FirstName,
            "LastName": c.LastName,
            "Subject": c.Subject,
            "Body": c.Body,
            "Email": c.Email,
            "PhoneNumber": c.PhoneNumber,
            "AttachPath": build_file_url(request, c.AttachPath) if request else None,
            "ReplyStatus": c.ReplyStatus,
            "UserId": c.UserID,
            "CreatedAt": c.CreatedAt
        })

    return success_response(
        message_en="Contacts retrieved successfully.",
        message_ar="تم جلب جميع رسائل التواصل بنجاح.",
        data={"contacts": out}
    )


# ------------------ Admin: Contact Details ------------------
@router.get("/admin/{contact_id}", response_model=dict)
def get_contact_details_admin(
    contact_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    request: Request = None
):
    contact = db.query(ContactUs).filter(ContactUs.ContactID == contact_id).first()

    if not contact:
        return error_response(
            message_en="Contact record not found.",
            message_ar="سجل التواصل غير موجود.",
            error_code="CONTACT_NOT_FOUND"
        )

    replies = db.query(ContactUsResponse).filter(
        ContactUsResponse.ContactID == contact.ContactID
    ).order_by(ContactUsResponse.CreatedAt.asc()).all()

    reply_list = []
    for r in replies:
        reply_list.append({
            "ResponseID": r.ResponseID,
            "Subject": r.Subject,
            "Body": r.Body,
            "AttachPath": build_file_url(request, r.AttachPath) if r.AttachPath else None,
            "CreatedByUserID": r.CreatedByUserID,
            "CreatedAt": r.CreatedAt
        })

    contact_data = {
        "ContactID": contact.ContactID,
        "FirstName": contact.FirstName,
        "LastName": contact.LastName,
        "Subject": contact.Subject,
        "Body": contact.Body,
        "Email": contact.Email,
        "PhoneNumber": contact.PhoneNumber,
        "AttachPath": build_file_url(request, contact.AttachPath),
        "ReplyStatus": contact.ReplyStatus,
        "UserId": contact.UserID,
        "CreatedAt": contact.CreatedAt,
        "Replies": reply_list
    }

    return success_response(
        message_en="Contact details retrieved successfully.",
        message_ar="تم جلب تفاصيل رسالة التواصل بنجاح.",
        data=contact_data
    )


# ------------------ Admin: Reply to Contact ------------------
@router.post("/admin/{contact_id}/reply", response_model=dict)
def reply_contact_admin(
    contact_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    Subject: Optional[str] = Form(None),
    Body: Optional[str] = Form(None),
    attach: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    contact = db.query(ContactUs).filter(ContactUs.ContactID == contact_id).first()

    if not contact:
        return error_response(
            message_en="Contact record not found.",
            message_ar="سجل التواصل غير موجود.",
            error_code="CONTACT_NOT_FOUND"
        )

    # 1️⃣ Save reply attachment
    attach_rel = None
    if attach:
        reply_dir = static_path("contact", "reply", ensure=True)
        orig = os.path.basename(attach.filename)
        safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{orig.replace(' ', '_')}"
        save_path = os.path.join(reply_dir, safe_name)

        with open(save_path, "wb") as buff:
            shutil.copyfileobj(attach.file, buff)

        attach_rel = f"contact/reply/{safe_name}"

    # 2️⃣ Create reply
    new_reply = ContactUsResponse(
        ContactID=contact.ContactID,
        Subject=Subject,
        Body=Body,
        AttachPath=attach_rel,
        CreatedByUserID=admin.UserID,
        CreatedAt=datetime.utcnow()
    )

    db.add(new_reply)
    contact.ReplyStatus = True
    db.commit()
    db.refresh(new_reply)

    # 3️⃣ Notify user
    if contact.Email:
        reply_subject = Subject or f"Reply to your Contact Form #{contact.ContactID}"

        reply_body = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;">
            <h2 style="color:#2563eb;margin-bottom:8px;">Reply to your Contact Form</h2>
            <p>Dear {contact.FirstName or 'User'},</p>
            <p>We have replied to your Contact Form #{contact.ContactID}.</p>
            <p>{Body or ''}</p>
            <hr style="margin:24px 0;">
            <p>عزيزي {contact.FirstName or 'المستخدم'},</p>
            <p>لقد قمنا بالرد على نموذج الاتصال الخاص بك #{contact.ContactID}.</p>
            <p>{Body or ''}</p>
            <p style="margin-top:32px;">Best regards,<br/>NGD Team</p>
        </div>
        """

        # Send email with or without attachment
        if attach_rel:
            background_tasks.add_task(
                send_email_with_attachment,
                reply_subject,
                reply_body,
                contact.Email,
                attach_rel
            )
        else:
            background_tasks.add_task(
                send_email,
                reply_subject,
                reply_body,
                contact.Email
            )

    return success_response(
        message_en="Reply sent successfully.",
        message_ar="تم إرسال الرد بنجاح.",
        data={
            "reply_id": new_reply.ResponseID,
            "attach_url": build_file_url(request, attach_rel)
        }
    )