from fastapi import (
    APIRouter,
    Depends,
    Path,
    File,
    UploadFile,
    Request,
    BackgroundTasks,
    Query,
)
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from app.models.users import User, Domain
from app.schemas.users import (
    UserCreate,
    UserUpdate,
    UserStatusUpdate,
)
from passlib.context import CryptContext
from typing import Optional
from datetime import datetime
import os
from dotenv import load_dotenv
from app.utils.response import success_response, error_response
from app.database import get_db
from app.utils.utils import get_current_user, extract_email_domain
from app.auth.tokens import create_verification_token
from app.utils.email import send_email, send_domain_refused_email
from app.utils.paths import static_path

load_dotenv()
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "")

router = APIRouter(prefix="/users", tags=["Users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _photo_url(request: Request, photo_path: Optional[str]) -> Optional[str]:
    if not photo_path:
        return None
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/{photo_path.lstrip('/')}"


def _serialize_user(user: User, request: Request) -> dict:
    data = {
        "UserID": user.UserID,
        "TitleId": user.TitleId,
        "FirstName": user.FirstName,
        "LastName": user.LastName,
        "OrganizationTypeID": user.OrganizationTypeID,
        "OrganizationName": user.OrganizationName,
        "Department": user.Department,
        "JobTitle": user.JobTitle,
        "CityID": user.CityID,
        "CountryID": user.CountryID,
        "PhoneNumber": user.PhoneNumber,
        "Email": user.Email,
        "RoleID": user.RoleID,
        "UserType": user.UserType,
        "PhotoPath": user.PhotoPath,
        "PhotoURL": _photo_url(request, user.PhotoPath),
        "DateOfBirth": user.DateOfBirth,
        "IsApproved": user.IsApproved,
        "IsActive": user.IsActive,
        "EmailVerified": user.EmailVerified,
        "CreatedAt": user.CreatedAt,
        "UpdatedAt": user.UpdatedAt,
    }
    return data







# @router.get("/getcount")
# def get_user_count( db: Session = Depends(get_db)):
#     user = db.query(User).count()
#     return success_response("User count retrieved successfully", {"user_count": user})





#List all users for only super admin user
@router.get("/")
def get_users(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None, description="Search by first name, last name, organization, or email"),
    role_id: Optional[int] = Query(None),
    is_active: Optional[str] = Query(None, description="True, False, or null"),
    is_approved: Optional[str] = Query(None, description="True, False, or null"),
    is_verified: Optional[str] = Query(None, description="True, False, or null"),
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.RoleID != 1:
        return error_response("Only admins can view all users", "FORBIDDEN")

    query = db.query(User).filter(User.IsDeleted == False)

    # --- Flexible search filter ---
    if search:
        # split search term by spaces
        search_terms = search.strip().split()
        search_filters = []
        for term in search_terms:
            like_term = f"%{term}%"
            search_filters.append(
                or_(
                    User.FirstName.ilike(like_term),
                    User.LastName.ilike(like_term),
                    User.Email.ilike(like_term),
                    User.OrganizationName.ilike(like_term),
                )
            )
        query = query.filter(and_(*search_filters))

    # --- Role filter ---
    if role_id:
        query = query.filter(User.RoleID == role_id)

    # --- Boolean filters (True, False, or None) ---
    def bool_filter(field, value: Optional[str]):
        if value is None:
            return
        v = value.lower()
        if v == "true":
            query.filter(field == True)
        elif v == "false":
            query.filter(field == False)
        elif v == "null":
            query.filter(field.is_(None))

    if is_active is not None:
        if is_active.lower() == "true":
            query = query.filter(User.IsActive == True)
        elif is_active.lower() == "false":
            query = query.filter(User.IsActive == False)
        elif is_active.lower() == "null":
            query = query.filter(User.IsActive.is_(None))

    if is_approved is not None:
        if is_approved.lower() == "true":
            query = query.filter(User.IsApproved == True)
        elif is_approved.lower() == "false":
            query = query.filter(User.IsApproved == False)
        elif is_approved.lower() == "null":
            query = query.filter(User.IsApproved.is_(None))

    if is_verified is not None:
        if is_verified.lower() == "true":
            query = query.filter(User.EmailVerified == True)
        elif is_verified.lower() == "false":
            query = query.filter(User.EmailVerified == False)
        elif is_verified.lower() == "null":
            query = query.filter(User.EmailVerified.is_(None))

    # --- Pagination ---
    total = query.count()
    skip = (page - 1) * limit
    users = query.order_by(User.CreatedAt.desc()).offset(skip).limit(limit).all()

    results = [_serialize_user(u, request) for u in users]

    payload = {
        "page": page,
        "limit": limit,
        "count": len(results),
        "total": total,
        "users": results,
    }

    return success_response("Users retrieved successfully", payload)




# get only the details for user id  for super admin user only with role id 1
@router.get("/{user_id}")
def get_user(request: Request, user_id: int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    user = db.query(User).filter(User.UserID == user_id).first()
    if not user:
        return error_response("User not found", "USER_NOT_FOUND")

    if current.RoleID != 1:
        return error_response("Only admins can view user details", "FORBIDDEN")

    user_data = _serialize_user(user, request)

    return success_response("User retrieved successfully", user_data)


# get the details for the current user with token
@router.get("/profile/me")
def get_me(request: Request, current=Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.UserID == current.UserID).first()
    if not user:
        return error_response("User not found", "USER_NOT_FOUND")

    return success_response("Profile retrieved successfully", _serialize_user(user, request))



# edit on each user from the super admin user only with role id 1
@router.put("/{user_id}")
def update_user(user_update: UserUpdate, user_id: int = Path(...), current=Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.UserID == user_id).first()
    if not db_user:
        return error_response("User not found", "USER_NOT_FOUND")

    is_owner = current.UserID == user_id
    is_admin = current.RoleID == 1
    if not (is_owner or is_admin):
        return error_response("Not authorized", "FORBIDDEN")

    update_data = user_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    db_user.UpdatedAt = datetime.utcnow()
    db_user.UpdatedByUserID = current.UserID

    db.commit()
    db.refresh(db_user)

    user_dict = db_user.__dict__.copy()
    user_dict.pop("PasswordHash", None)
    user_dict.pop("PhotoURL", None)

    return success_response("User updated successfully", user_dict)



@router.post("/admin-create")
def admin_create_user(
    user: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    current=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current.RoleID != 1:
        return error_response("Only admins can create users", "FORBIDDEN")

    existing_user = db.query(User).filter(User.Email == user.Email).first()
    if existing_user:
        return error_response("Email already registered", "EMAIL_EXISTS")

    hashed_password = pwd_context.hash(user.Password)

    new_user = User(
        FirstName=user.FirstName,
        LastName=user.LastName,
        OrganizationTypeID=user.OrganizationTypeID,
        OrganizationName=user.OrganizationName,
        Department=user.Department,
        JobTitle=user.JobTitle,
        CityID=user.CityID,
        CountryID=user.CountryID,
        PhoneNumber=user.PhoneNumber,
        TitleId=user.TitleId,
        Email=user.Email,
        DateOfBirth=user.DateOfBirth,
        PasswordHash=hashed_password,
        RoleID=user.RoleID or 2,
        UserType=user.UserType,
        PhotoPath=user.PhotoPath,
        CreatedAt=datetime.utcnow(),
        CreatedByUserID=current.UserID,
        IsApproved=True,
        IsActive=True,
        EmailVerified=False,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_verification_token(user.Email, expires_minutes=None)
    base_frontend = FRONTEND_BASE_URL or str(request.base_url).rstrip("/")
    verify_url = f"{base_frontend}/auth/verify-email?token={token}"
    email_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;">
        <h2 style="color:#2563eb;margin-bottom:8px;">Welcome to NGD, {user.FirstName}!</h2>
        <p>An administrator created an account for you. Please confirm your email to activate your access.</p>
        <p style="margin:24px 0;">
            <a href="{verify_url}" style="background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:6px;display:inline-block;">
                Verify my email
            </a>
        </p>
        <p style="font-size:13px;color:#6b7280;">If the button doesn't work, copy this link into your browser:</p>
        <p style="font-size:13px;color:#2563eb;word-break:break-all;">{verify_url}</p>
        <p style="margin-top:32px;">Best regards,<br/>NGD Team</p>
    </div>
    """
    background_tasks.add_task(send_email, "Verify your NGD account", email_body, user.Email)

    return success_response("User created and invitation sent.", _serialize_user(new_user, request))


@router.put("/{user_id}/status")
def update_user_status(
    user_id: int,
    status: UserStatusUpdate,
    current=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current.RoleID != 1:
        return error_response("Only admins can update status", "FORBIDDEN")

    user = db.query(User).filter(User.UserID == user_id).first()
    if not user:
        return error_response("User not found", "USER_NOT_FOUND")

    user.IsActive = status.is_active
    user.UpdatedAt = datetime.utcnow()
    user.UpdatedByUserID = current.UserID
    db.commit()

    return success_response("User status updated successfully", {"user_id": user_id, "is_active": user.IsActive})




UPLOAD_DIR = static_path("profile_images", ensure=True)


# for upload profile photo for the user
@router.post("/{user_id}/upload-photo")
def upload_profile_photo(user_id: int, file: UploadFile = File(...), current=Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.UserID == user_id).first()
    if not user:
        return error_response("User not found", "USER_NOT_FOUND")

    is_owner = current.UserID == user_id
    is_admin = current.RoleID == 1
    if not is_owner and not is_admin:
        return error_response("Not authorized", "FORBIDDEN")

    ext = file.filename.split(".")[-1]
    filename = f"{user_id}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    user.PhotoPath = f"static/profile_images/{filename}"
    user.UpdatedAt = datetime.utcnow()
    user.UpdatedByUserID = current.UserID
    db.commit()

    return success_response("Photo uploaded successfully", {"photo_url": user.PhotoPath})



# for soft delete the specific user form the admin user only with roled id 1 
@router.delete("/{user_id}")
def delete_user(user_id: int, current=Depends(get_current_user), db: Session = Depends(get_db)):
    if current.RoleID != 1:
        return error_response("Only admins can delete users", "FORBIDDEN")

    user = db.query(User).filter(User.UserID == user_id, User.IsDeleted == False).first()
    if not user:
        return error_response("User not found", "USER_NOT_FOUND")

    user.IsDeleted = True
    db.commit()

    return success_response("User marked as deleted successfully")



# for approve the user and update it forom only super admin user only with role id 1
@router.put("/{user_id}/approve")
def approve_user(user_id: int, current=Depends(get_current_user), db: Session = Depends(get_db)):
    if current.RoleID != 1:
        return error_response("Only admins can approve users", "FORBIDDEN")

    user = db.query(User).filter(User.UserID == user_id).first()
    if not user:
        return error_response("User not found", "USER_NOT_FOUND")

    user.IsApproved = True
    user.IsActive = True
    user.UpdatedAt = datetime.utcnow()
    user.UpdatedByUserID = current.UserID

    domain_value = extract_email_domain(user.Email)
    if domain_value:
        domain_record = (
            db.query(Domain)
            .filter(func.lower(Domain.Domain) == domain_value)
            .first()
        )
        if domain_record:
            domain_record.Type = "accept"
        else:
            db.add(Domain(Domain=domain_value, Type="accept"))

    db.commit()

    return success_response(f"User ID {user_id} approved and activated successfully.", {"user_id": user_id})


@router.put("/{user_id}/refuse")
def refuse_user(
    user_id: int,
    background_tasks: BackgroundTasks,
    current=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current.RoleID != 1:
        return error_response("Only admins can refuse users", "FORBIDDEN")

    user = db.query(User).filter(User.UserID == user_id).first()
    if not user:
        return error_response("User not found", "USER_NOT_FOUND")

    domain_value = extract_email_domain(user.Email)
    if domain_value:
        domain_record = (
            db.query(Domain)
            .filter(func.lower(Domain.Domain) == domain_value)
            .first()
        )
        if domain_record:
            domain_record.Type = "refused"
        else:
            db.add(Domain(Domain=domain_value, Type="refused"))

        background_tasks.add_task(send_domain_refused_email, user.Email, domain_value)

    user.IsApproved = False
    user.IsActive = False
    user.IsDeleted = True
    user.UpdatedAt = datetime.utcnow()
    user.UpdatedByUserID = current.UserID

    db.commit()

    return success_response("User refused and notified.", {"user_id": user_id})
