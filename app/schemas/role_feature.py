from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class FeatureTypeEnum(str, Enum):
    EARTH = "Earth"
    ADMIN = "Admin"

class AppFeatureBase(BaseModel):
    NameEn: str
    NameAr: Optional[str] = None
    DescriptionEn: Optional[str] = None
    DescriptionAr: Optional[str] = None
    Link: Optional[str] = None
    AppType: Optional[FeatureTypeEnum] = FeatureTypeEnum.EARTH  # default Earth


class AppFeatureCreate(AppFeatureBase):
    pass

class AppFeatureUpdate(BaseModel):
    NameEn: Optional[str] = None
    NameAr: Optional[str] = None
    DescriptionEn: Optional[str] = None
    DescriptionAr: Optional[str] = None
    Link: Optional[str] = None
    AppType: Optional[FeatureTypeEnum] = None

class AppFeatureOut(AppFeatureBase):
    AppFeatureID: int
    class Config:
        orm_mode = True


class RoleBase(BaseModel):
    NameEn: str
    NameAr: Optional[str] = None
    DescriptionEn: Optional[str] = None
    DescriptionAr: Optional[str] = None

class RoleCreate(RoleBase):
    app_feature_ids: Optional[List[int]] = []  # <-- assign features on creation

class RoleUpdate(BaseModel):
    NameEn: Optional[str] = None
    NameAr: Optional[str] = None
    DescriptionEn: Optional[str] = None
    DescriptionAr: Optional[str] = None
    app_feature_ids: Optional[List[int]] = None  # <-- assign/update features

class RoleOut(RoleBase):
    RoleID: int
    features: List[AppFeatureOut] = []
    class Config:
        orm_mode = True
