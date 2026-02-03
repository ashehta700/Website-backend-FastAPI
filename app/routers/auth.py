# app/routers/auth.py
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from passlib.hash import bcrypt
from app.models.users import User, Domain
from app.schemas.users import UserCreate, UserLogin
from app.auth.jwt_handler import create_access_token
from app.auth.jwt_bearer import ALGORITHM, SECRET_KEY
from app.utils.response import success_response, error_response
from app.database import get_db
from app.utils.email import send_email, send_domain_refused_email
from app.auth.tokens import create_verification_token, verify_verification_token
import jwt
from app.models.lookups import  UserTitle, OrganizationType, Country, City
from datetime import datetime
from app.utils.utils import get_optional_user, extract_email_domain
from app.models.role_feature import Role
import os
from dotenv import load_dotenv

load_dotenv()


router = APIRouter(prefix="/auth", tags=["Auth"])

#load the base URL for the front end application
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL")


# ✅ Lookups endpoint for user registration
@router.get("/lookups")
def get_registration_lookups(db: Session = Depends(get_db)):
    """
    Returns lookup data used for registration forms
    such as available roles or other dropdowns.
    """
    try:
        # Example: Fetch only roles allowed for public registration
        roles = db.query(Role).filter(Role.RoleID != 1)
        UserTitles = db.query(UserTitle).all()
        OrganizationTypes = db.query(OrganizationType).all()
        # Exclude Geom column (geometry type) which pyodbc doesn't support
        Countries = db.query(
            Country.OBJECTID.label("id"),
            Country.CountryCode.label("code"),
            Country.CountryName.label("name"),
            Country.CountryNameAr.label("name_ar")

        ).all()
        Cities = db.query(City).all()

        roles_data = [
            {"role_id": role.RoleID, "NameEn": role.NameEn , "NameAr": role.NameAr}
            for role in roles
        ]

        # You can add other lookup sets later, e.g.:
        titles =  [{"id": title.Id, "title": title.Title} for title in UserTitles]
        organizations =  [{"id": org.OrganizationTypeID, "NameEn": org.NameEn,"NameAr":org.NameAr} for org in OrganizationTypes]
        # Access labeled columns by attribute name
        countries = [{"id": country.id, "NameEn": country.name, "NameAr": country.name_ar, "CountryCode": country.code} for country in Countries]
        # cities = [{"id": city.CityID, "NameEn": city.NameEn,"NameAr":city.NameAr} for city in Cities]
        # departments = [{"id": 1, "name": "IT"}, {"id": 2, "name": "HR"}]

        domains = db.query(Domain).order_by(Domain.Type.asc(), Domain.Domain.asc()).all()

        lookups = {
            "roles": roles_data,
            "titles": titles,
            "Organizations": organizations,
            "countries": countries,
            # "cities": cities,
            "domains": [
                {
                    "id": domain.Id,
                    "domain": domain.Domain,
                    "type": domain.Type
                }
                for domain in domains
            ],
            # "departments": departments,
        }

        return success_response("Lookups loaded successfully", lookups)

    except Exception as e:
        return error_response(f"Error fetching lookup data: {str(e)}", "LOOKUP_ERROR")


# make a new endpoint to return all cities related to a country
@router.get("/lookups/cities")
def get_cities(country_id: int = None, db: Session = Depends(get_db)):
    """
    Returns list of cities.
    - If no country_id is provided → return all cities.
    - If country_id is provided → return only cities belonging to that country.
    """

    try:
        query = db.query(City)

        # Filter if country_id provided
        if country_id:
            query = query.filter(City.CountryID == country_id)

        cities = query.all()

        cities_data = [
            {
                "id": city.CityID,
                "NameEn": city.NameEn,
                "NameAr": city.NameAr,
                "CountryID": city.CountryID
            }
            for city in cities
        ]

        return success_response(
            message_en="Cities loaded successfully",
            message_ar="تم جلب المدن بنجاح",
            data={"cities": cities_data}
        )

    except Exception as e:
        return error_response(
            message_en=f"Error fetching cities: {str(e)}",
            message_ar="خطأ في جلب المدن",
            error_code="CITY_LOOKUP_ERROR"
        )
# this is endpoint for Registering a new Account (Admin or Self Registration)
@router.post("/register")
def register(
    user: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_user)  # <-- allow admin or none
):
    # Check for existing user
    existing_user = db.query(User).filter(User.Email == user.Email).first()
    if existing_user:
        return error_response(
            message_en="Email already registered",
            message_ar= "هذا البريد مسجل بالفل",
            error_code="EMAIL_EXISTS")

    # Hash password
    hashed_password = bcrypt.hash(user.Password)

    email_domain = extract_email_domain(user.Email)
    auto_approve = False
    if email_domain:
        domain_record = (
            db.query(Domain)
            .filter(func.lower(Domain.Domain) == email_domain)
            .first()
        )
        if domain_record and domain_record.Type == "refused":
            background_tasks.add_task(send_domain_refused_email, user.Email, email_domain)
            return error_response(
            message_en="This email domain is not allowed. Please use your company email.",
            message_ar= "هذا البريد غير مسموح له بالتسجيل , برجاء التسجيل ببريد شركة",
            error_code="DOMAIN_REFUSED")
             
        if domain_record and domain_record.Type == "accept":
            auto_approve = True

    # Create new user object
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
        UserType=user.UserType,
        PasswordHash=hashed_password,
        RoleID=user.RoleID or 2,
        IsApproved=auto_approve,
        EmailVerified=False,
        IsActive=auto_approve,
        CreatedAt=datetime.now(),
        CreatedByUserID=current_user.UserID if current_user else None,  # 👈 NEW LINE
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate email verification link
    token = create_verification_token(user.Email, expires_minutes=None)
    verify_url = f"{FRONTEND_BASE_URL}/auth/verify-email?token={token}"

    email_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;">
        <h2 style="color:#2563eb;margin-bottom:8px;">Welcome to NGD, {user.FirstName}!</h2>
        <p>Thanks for registering. Please confirm your email so we can activate your account.</p>
        <p style="margin:24px 0;">
            <a href="{verify_url}" style="background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:6px;display:inline-block;">
                Verify my email
            </a>
        </p>
        <p style="font-size:13px;color:#6b7280;">If the button doesn't work, copy and paste this link into your browser:</p>
        <p style="font-size:13px;color:#2563eb;word-break:break-all;">{verify_url}</p>
        <p style="margin-top:32px;">Best regards,<br/>NGD Team</p>
    </div>
    """

    # Send verification email in background
    background_tasks.add_task(send_email, "Verify your NGD account", email_body, user.Email)

    return success_response(
    message_en="Registration successful. Please verify your email.",
    message_ar="تم التسجيل بنجاح , برجاء التحقق من بريدك الالكترونى",
    data={"email": user.Email, "created_by": current_user.UserID if current_user else None}
    )
  




# this endpoint for verify the email
@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    email = verify_verification_token(token)
    if not email:
        return error_response(
        message_en="Invalid or expired token",
        message_ar="رمز التحقق غير صالح أو انتهت صلاحيته",
        error_code="TOKEN_INVALID"
    )

    user = db.query(User).filter(User.Email == email).first()
    if not user:
        return error_response(
        message_en="User not found",
        message_ar="هذا المستخدم غير موجود",
        error_code="USER_NOT_FOUND"
    )

    if user.EmailVerified:
        return error_response(
        message_en="Email already verified",
        message_ar="هذا البريد تم التحقق منه مسبقاً",
        error_code="EMAIL_ALREADY_VERIFIED"
    )
        

    user.EmailVerified = True
    db.commit()

    return success_response(
    message_en="Email verified successfully. Waiting for admin approval.",
    message_ar="تم التحقق من البريد بنجاح , برجاء انتظار موافقة مدير النظام"
    )
    


# this endpoint for Login to the System
@router.post("/login")
def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.Email == user.Email).first()

    # 1️⃣ Check if user exists and password matches
    if not db_user or not bcrypt.verify(user.Password, db_user.PasswordHash):
        return error_response(
        message_en="Invalid email or password",
        message_ar="البريد الإلكتروني أو كلمة المرور غير صحيحة",
        error_code="INVALID_CREDENTIALS"
    )

    # 2️⃣ Check if email is verified (first priority)
    if not db_user.EmailVerified:
        return error_response(
        message_en= "Please verify your email address before logging in. Check your inbox for the verification link.",
        message_ar="برجاء التحقق من البريد اولا قبل تسجيل الدخول , فضلاً تحقق من بريدك الاكترونى",
        error_code="EMAIL_NOT_VERIFIED"
        )


    # 3️⃣ Check if user is approved by administrator
    if not db_user.IsApproved:
        return error_response(
        message_en= "Your account is pending approval by an administrator. Please wait for approval or contact support.",
        message_ar="بريدك فى انتظار مواقفة مدير المظام , فضلا انتظر الموافقة او تواصل بنا" ,
        error_code="ACCOUNT_NOT_APPROVED"
        )
        
    # 4️⃣ Check if user account is active
    if not db_user.IsActive:
        return error_response(
        message_en= "Your account has been deactivated. Please contact support to reactivate your account.",
        message_ar="حسابك غير مفعل , من فضلك قم بالتواصل معنا للتفعيل مرة اخري" ,
        error_code="ACCOUNT_INACTIVE"
        )

    # 5️⃣ Build photo URL
    base_url = os.getenv("BASE_URL")
    photo_relative_path = db_user.PhotoPath or ""
    photo_url = f"{base_url}/{photo_relative_path.lstrip('/')}" if photo_relative_path else None

    # 6️⃣ Create JWT token
    token = create_access_token(
        data={
            "sub": db_user.Email,
            "user_id": db_user.UserID,
            "role_id": db_user.RoleID,
            "first_name": db_user.FirstName,
            "last_name": db_user.LastName,
            "photo_url": photo_url,
        }
    )

    # 7️⃣ Return success response
    return success_response(
    message_en="Login successful",
    message_ar="تم تسجيل الدخول بنجاح",
    data={"access_token": token}
)



# for forget and reset password for user
@router.post("/forgot-password")
def forgot_password(request: Request, email: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.Email == email).first()
    if not user:
        return error_response(
        message_en="Email not found",
        message_ar="هذا البريد غير مسجل",
        error_code="EMAIL_NOT_FOUND"
    )

    token = create_verification_token(email, expires_minutes=60)
    reset_url = f"{FRONTEND_BASE_URL}/auth/reset-password?token={token}"
    email_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;color:#1f2937;max-width:520px;margin:auto;">
        <h2 style="color:#2563eb;margin-bottom:8px;">Reset your NGD password</h2>
        <p>We received a request to reset the password for your account. Click the button below to choose a new password.</p>
        <p style="margin:24px 0;">
            <a href="{reset_url}" style="background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:6px;display:inline-block;">
                Reset password
            </a>
        </p>
        <p style="font-size:13px;color:#6b7280;">If you didn't request this, you can safely ignore this email.</p>
        <p style="font-size:13px;color:#6b7280;">Link (valid for 60 minutes): <span style="color:#2563eb;word-break:break-all;">{reset_url}</span></p>
        <p style="margin-top:32px;">Best regards,<br/>NGD Team</p>
    </div>
    """
    background_tasks.add_task(send_email, "Password Reset - NGD", email_body, email)
    return success_response(
    message_en="Password reset email sent successfully.",
    message_ar="تم ارسال رابط تغير كلمة المرور الى بريدك بنجاح",
    data={"email": email}
)



@router.post("/reset-password")
def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    email = verify_verification_token(token)
    if not email:
        return error_response(
        message_en="Invalid or expired token",
        message_ar="خطأ او تم انتهاء صلاحية الرابط",
        error_code="TOKEN_INVALID"
    )


    user = db.query(User).filter(User.Email == email).first()
    if not user:
        return error_response(
        message_en="User not found",
        message_ar="هذا المستخدم غير موجود",
        error_code="USER_NOT_FOUND"
    )

    user.PasswordHash = bcrypt.hash(new_password)
    db.commit()

    return success_response(
    message_en="Password has been reset successfully.",
    message_ar="تم تغيير كلمة المرور بنجاح"
)