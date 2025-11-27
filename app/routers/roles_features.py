# routers/roles_features.py
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

@router.post("/appfeatures", dependencies=[Depends(require_admin)])
def create_app_feature(payload: AppFeatureCreate, db: Session = Depends(get_db)):
    feature = AppFeature(**payload.dict())
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return success_response(
        "App feature created successfully",
        "تم إنشاء ميزة التطبيق بنجاح",
        {"AppFeatureID": feature.AppFeatureID}
    )

@router.get("/appfeatures", dependencies=[Depends(require_admin)])
def get_all_features(db: Session = Depends(get_db)):
    features = db.query(AppFeature).all()
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
            "RoleIDs": role_ids
        })
    return success_response(
        "App features retrieved successfully",
        "تم جلب ميزات التطبيق بنجاح",
        data
    )

@router.put("/appfeatures/{feature_id}", dependencies=[Depends(require_admin)])
def update_feature(feature_id: int, payload: AppFeatureUpdate, db: Session = Depends(get_db)):
    feature = db.query(AppFeature).filter(AppFeature.AppFeatureID == feature_id).first()
    if not feature:
        return error_response("Feature not found", "الميزة غير موجودة")
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(feature, key, value)
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
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    role = Role(**payload.dict())
    db.add(role)
    db.commit()
    db.refresh(role)
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
            "Features": [
                {"AppFeatureID": f.AppFeatureID, "NameEn": f.NameEn, "Link": f.Link}
                for f in r.features
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
        return error_response("App feature not found", "ميزة التطبيق غير موجودة")

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

@router.get("/roles/{role_id}")
def get_role_details(role_id: int, db: Session = Depends(get_db)):
    role = db.query(Role).filter(Role.RoleID == role_id).first()
    if not role:
        return error_response("Role not found", "الدور غير موجود")
    data = {
        "RoleID": role.RoleID,
        "NameEn": role.NameEn,
        "NameAr": role.NameAr,
        "Features": [
            {"AppFeatureID": f.AppFeatureID, "NameEn": f.NameEn, "Link": f.Link}
            for f in role.features
        ]
    }
    return success_response(
        "Role details retrieved successfully",
        "تم جلب تفاصيل الدور بنجاح",
        data
    )
