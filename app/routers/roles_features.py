# routers/role_features.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from app.database import get_db
from app.models.role_feature import Role, AppFeature, RoleApp
from app.schemas.role_feature import *
from app.utils.response import success_response, error_response
from app.utils.utils import require_admin, get_current_user
from app.models.users import User

router = APIRouter(prefix="/features", tags=["App Features & Roles"])

# ---------------------- APP FEATURES ----------------------
# List all features, optionally filter by type
@router.get("/appfeatures", dependencies=[Depends(require_admin)])
def get_all_features(type: Optional[FeatureTypeEnum] = None, db: Session = Depends(get_db)):
    query = db.query(AppFeature)
    if type:
        query = query.filter(AppFeature.AppType == type)
    features = query.all()
    data = []
    for f in features:
        role_ids = [ra.RoleID for ra in f.role_apps]
        data.append({
            "AppFeatureID": f.AppFeatureID,
            "NameEn": f.NameEn,
            "NameAr": f.NameAr,
            "DescriptionEn": f.DescriptionEn,
            "DescriptionAr": f.DescriptionAr,
            "Link": f.Link,
            "AppType": f.AppType,
            "RoleIDs": role_ids
        })
    return success_response(
        "App features retrieved successfully",
        "تم جلب ميزات التطبيق بنجاح",
        data
    )




@router.post("/appfeatures", dependencies=[Depends(require_admin)])
def create_app_feature(payload: AppFeatureCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    feature = AppFeature(**payload.dict(), CreatedByUserID=user.UserID)
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return success_response(
        "App feature created successfully",
        "تم إنشاء ميزة التطبيق بنجاح",
        {"AppFeatureID": feature.AppFeatureID}
    )




@router.put("/appfeatures/{feature_id}", dependencies=[Depends(require_admin)])
def update_feature(feature_id: int, payload: AppFeatureUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    feature = db.query(AppFeature).filter(AppFeature.AppFeatureID == feature_id).first()
    if not feature:
        return error_response("Feature not found", "الميزة غير موجودة")
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(feature, key, value)
    feature.UpdatedByUserID = user.UserID
    feature.UpdatedAt = datetime.utcnow()
    db.commit()
    db.refresh(feature)
    return success_response(
        "Feature updated successfully",
        "تم تحديث الميزة بنجاح",
        {"AppFeatureID": feature.AppFeatureID}
    )



@router.delete("/appfeatures/{feature_id}", dependencies=[Depends(require_admin)])
def delete_feature(feature_id: int, db: Session = Depends(get_db)):
    feature = db.query(AppFeature).filter(AppFeature.AppFeatureID == feature_id).first()
    if not feature:
        return error_response("Feature not found", "الميزة غير موجودة")
    db.delete(feature)
    db.commit()
    return success_response(
        "Feature deleted successfully",
        "تم حذف الميزة بنجاح",
        None
    )

# ---------------------- ROLES ----------------------

@router.post("/roles", dependencies=[Depends(require_admin)])
def create_role(payload: RoleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # 1. Create the role
    role = Role(**payload.dict(exclude={"app_feature_ids"}), CreatedByUserID=user.UserID)
    db.add(role)
    db.commit()
    db.refresh(role)

    # 2. Assign features if provided (Admin features only)
    if payload.app_feature_ids:
        admin_features = db.query(AppFeature).filter(
            AppFeature.AppFeatureID.in_(payload.app_feature_ids),
            AppFeature.AppType == FeatureTypeEnum.ADMIN
        ).all()
        for feature in admin_features:
            db.add(RoleApp(RoleID=role.RoleID, AppFeatureID=feature.AppFeatureID, CreatedByUserID=user.UserID))
        db.commit()

    return success_response(
        "Role created successfully",
        "تم إنشاء الدور بنجاح",
        {"RoleID": role.RoleID}
    )



@router.get("/roles", dependencies=[Depends(require_admin)])
def get_all_roles(db: Session = Depends(get_db)):
    roles = db.query(Role).all()
    data = []
    for r in roles:
        data.append({
            "RoleID": r.RoleID,
            "NameEn": r.NameEn,
            "NameAr": r.NameAr,
            "AdminFeatures": [
                {
                    "AppFeatureID": f.AppFeatureID,
                    "NameEn": f.NameEn,
                    "Link": f.Link
                }
                for f in r.features if f.AppType == FeatureTypeEnum.ADMIN
            ],
            "EarthFeatures": [
                {
                    "AppFeatureID": f.AppFeatureID,
                    "NameEn": f.NameEn,
                    "Link": f.Link
                }
                for f in r.features if f.AppType == FeatureTypeEnum.EARTH
            ]
        })
    return success_response(
        "Roles retrieved successfully",
        "تم جلب الأدوار بنجاح",
        data
    )




class AssignFeatureToRolesPayload(BaseModel):
    role_ids: List[int]

@router.post("/roles/{app_feature_id}/assign_features", dependencies=[Depends(require_admin)])
def assign_feature_to_roles(
    app_feature_id: int,
    payload: AssignFeatureToRolesPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    feature = db.query(AppFeature).filter(AppFeature.AppFeatureID == app_feature_id).first()
    if not feature:
        return error_response("App feature not found", "ميزة التطبيق غير موجود")

    # Optionally, allow only admin features to be assigned here
    if feature.Type != FeatureTypeEnum.ADMIN:
        return error_response("Feature is not an admin feature", "الميزة ليست من لوحة الإدارة")

    existing_links = db.query(RoleApp).filter(RoleApp.AppFeatureID == app_feature_id).all()
    existing_role_ids = {link.RoleID for link in existing_links}

    new_role_ids = set(payload.role_ids)
    to_add = new_role_ids - existing_role_ids
    to_remove = existing_role_ids - new_role_ids

    for rid in to_add:
        db.add(RoleApp(RoleID=rid, AppFeatureID=app_feature_id, CreatedByUserID=user.UserID))

    if to_remove:
        db.query(RoleApp).filter(
            RoleApp.AppFeatureID == app_feature_id,
            RoleApp.RoleID.in_(to_remove)
        ).delete(synchronize_session=False)

    db.commit()

    current_roles = [r[0] for r in db.query(RoleApp.RoleID).filter(RoleApp.AppFeatureID == app_feature_id).all()]

    return success_response(
        "Feature roles updated successfully",
        "تم تحديث صلاحيات الميزة بنجاح",
        {
            "AppFeatureID": app_feature_id,
            "AddedRoles": list(to_add),
            "RemovedRoles": list(to_remove),
            "CurrentRoles": current_roles
        }
    )

@router.put("/roles/{role_id}", dependencies=[Depends(require_admin)])
def update_role(role_id: int, payload: RoleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    role = db.query(Role).filter(Role.RoleID == role_id).first()
    if not role:
        return error_response("Role not found", "الدور غير موجود")

    # 1. Update role fields
    for key, value in payload.dict(exclude_unset=True, exclude={"app_feature_ids"}).items():
        setattr(role, key, value)
    role.UpdatedAt = datetime.utcnow()
    role.UpdatedByUserID = user.UserID
    db.commit()
    db.refresh(role)

    # 2. Update feature assignments if provided
    if payload.app_feature_ids is not None:
        # Filter only Admin features
        admin_features = db.query(AppFeature).filter(
            AppFeature.AppFeatureID.in_(payload.app_feature_ids),
            AppFeature.AppType == FeatureTypeEnum.ADMIN
        ).all()
        admin_feature_ids = {f.AppFeatureID for f in admin_features}

        # Existing assigned features
        existing_links = db.query(RoleApp).filter(RoleApp.RoleID == role_id).all()
        existing_feature_ids = {link.AppFeatureID for link in existing_links}

        # Determine features to add/remove
        to_add = admin_feature_ids - existing_feature_ids
        to_remove = existing_feature_ids - admin_feature_ids

        # Add new
        for fid in to_add:
            db.add(RoleApp(RoleID=role_id, AppFeatureID=fid, CreatedByUserID=user.UserID))
        # Remove old
        if to_remove:
            db.query(RoleApp).filter(
                RoleApp.RoleID == role_id,
                RoleApp.AppFeatureID.in_(to_remove)
            ).delete(synchronize_session=False)

        db.commit()

    return success_response(
        "Role updated successfully",
        "تم تحديث الدور بنجاح",
        {"RoleID": role.RoleID}
    )



@router.delete("/roles/{role_id}", dependencies=[Depends(require_admin)])
def delete_role(role_id: int, db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.RoleID == role_id).first()
    if not role:
        return error_response("Role not found", "الدور غير موجود")
    db.delete(role)
    db.commit()
    return success_response(
        "Role deleted successfully",
        "تم حذف الدور بنجاح",
        None
    )




@router.get("/public/earth-features")
def get_public_earth_features(db: Session = Depends(get_db)):
    # 1. Get Public Role
    public_role = db.query(Role).filter(
        Role.NameEn.ilike("public")  # أو "Public"
    ).first()

    if not public_role:
        return error_response("Public role not found", "دور المستخدم العام غير موجود")

    # 2. Get features linked to this role (EARTH only)
    features = db.query(AppFeature).join(RoleApp).filter(
        RoleApp.RoleID == public_role.RoleID,
        AppFeature.AppType == FeatureTypeEnum.EARTH
    ).all()

    # 3. Format response
    data = [
        {
            "AppFeatureID": f.AppFeatureID,
            "NameEn": f.NameEn,
            "NameAr": f.NameAr,
            "DescriptionEn": f.DescriptionEn,
            "DescriptionAr": f.DescriptionAr,
            "Link": f.Link
        }
        for f in features
    ]

    return success_response(
        "Public earth features retrieved successfully",
        "تم جلب ميزات تطبيق الأرض للمستخدم العام بنجاح",
        data
    )