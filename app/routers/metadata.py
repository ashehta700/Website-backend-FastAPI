# routers/metadata.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from urllib.parse import quote
import os, shutil

from app.database import get_db
from app.models.metadata import DatasetInfo, MetadataInfo
from app.schemas.metadata import (
    DatasetInfoResponse, MetadataInfoResponse
)
from app.utils.response import success_response, error_response
from app.utils.utils import require_admin
from app.utils.paths import static_path

router = APIRouter(prefix="/metadata", tags=["Metadata"])


# --------------------------
# Helper to build file/image URLs
# --------------------------
def build_file_url(request: Request, path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/static/{quote(path)}"


# -------------------- PUBLIC ENDPOINTS --------------------

@router.get("/datasets")
def get_all_datasets(request: Request, db: Session = Depends(get_db)):
    """
    Get all datasets (for dropdowns or homepage cards)
    """
    datasets = db.query(DatasetInfo).filter(DatasetInfo.IsDeleted == False).all()
    if not datasets:
        return error_response("No datasets found", "لا توجد مجموعات بيانات")

    data = []
    for dataset in datasets:
        data.append({
            "DatasetID": dataset.DatasetID,
            "Name": dataset.Name,
            "NameAr": dataset.NameAr,
            "Title": dataset.Title,
            "TitleAr": dataset.TitleAr,
            "CRS_Name": dataset.CRS_Name,
            "EPSG": dataset.EPSG,
            "Keywords": dataset.Keywords,
            "KeywordsAr": dataset.KeywordsAr,
            "Img": build_file_url(request, dataset.img)
        })

    return success_response(
        "Datasets retrieved successfully",
        "تم جلب مجموعات البيانات بنجاح",
        data
    )


@router.get("/datasets/{dataset_id}")
def get_dataset_with_metadata(request: Request, dataset_id: int, db: Session = Depends(get_db)):
    """
    Get single dataset with metadata
    """
    dataset = db.query(DatasetInfo).filter(DatasetInfo.DatasetID == dataset_id).first()
    if not dataset:
        return error_response("Dataset not found", "لم يتم العثور على مجموعة البيانات")

    metadata_list = db.query(MetadataInfo).filter(
        MetadataInfo.DatasetID == dataset_id, MetadataInfo.IsDeleted == False
    ).all()

    data = {
        "DatasetID": dataset.DatasetID,
        "Name": dataset.Name,
        "NameAr": dataset.NameAr,
        "Title": dataset.Title,
        "TitleAr": dataset.TitleAr,
        "Description": dataset.description,
        "DescriptionAr": dataset.descriptionAr,
        "CRS_Name": dataset.CRS_Name,
        "EPSG": dataset.EPSG,
        "Keywords": dataset.Keywords,
        "KeywordsAr": dataset.KeywordsAr,
        "Img": build_file_url(request, dataset.img),
        "Metadata": [
            {
                "MetadataID": m.MetadataID,
                "Name": m.Name,
                "NameAr": m.NameAr,
                "Title": m.Title,
                "TitleAr": m.TitleAr,
                "Description": m.description,
                "DescriptionAr": m.descriptionAr
            } for m in metadata_list
        ]
    }

    return success_response(
        "Dataset with metadata retrieved successfully",
        "تم جلب مجموعة البيانات مع البيانات الوصفية بنجاح",
        data
    )


@router.get("/datasets/{dataset_id}/services")
def get_dataset_services(dataset_id: int, db: Session = Depends(get_db)):
    """
    Get metadata service links for a dataset
    """
    dataset = db.query(DatasetInfo).filter(DatasetInfo.DatasetID == dataset_id).first()
    if not dataset:
        return error_response("Dataset not found", "لم يتم العثور على مجموعة البيانات")

    metadata_list = db.query(MetadataInfo).filter(
        MetadataInfo.DatasetID == dataset_id, MetadataInfo.IsDeleted == False
    ).all()

    data = {
        "DatasetID": dataset.DatasetID,
        "Name": dataset.Name,
        "NameAr": dataset.NameAr,
        "Metadata_servicesLink": [
            {
                "MetadataID": m.MetadataID,
                "Name": m.Name,
                "NameAr": m.NameAr,
                "URL": m.URL
            } for m in metadata_list
        ]
    }

    return success_response(
        "Dataset services retrieved successfully",
        "تم جلب خدمات مجموعة البيانات بنجاح",
        data
    )


@router.get("/metadata/{metadata_id}")
def get_metadata_details(request: Request, metadata_id: int, db: Session = Depends(get_db)):
    """
    Get metadata details
    """
    metadata = db.query(MetadataInfo).filter(
        MetadataInfo.MetadataID == metadata_id, MetadataInfo.IsDeleted == False
    ).first()
    if not metadata:
        return error_response("Metadata not found", "لم يتم العثور على البيانات الوصفية")

    data = {
        "MetadataID": metadata.MetadataID,
        "DatasetID": metadata.DatasetID,
        "Name": metadata.Name,
        "NameAr": metadata.NameAr,
        "Title": metadata.Title,
        "TitleAr": metadata.TitleAr,
        "Description": metadata.description,
        "DescriptionAr": metadata.descriptionAr,
        "CreationDate": metadata.CreationDate,
        "ServicesURL": metadata.URL,
        "DocumentPath": build_file_url(request, metadata.FilePath),
        "Bounds": {
            "West": metadata.WestBound,
            "East": metadata.EastBound,
            "North": metadata.NorthBound,
            "South": metadata.SouthBound
        },
        "MetadataStandard": {
            "Name": metadata.MetadataStandardName,
            "Version": metadata.MetadataStandardVersion
        },
        "Contact": {
            "ContactName": metadata.ContactName,
            "PositionName": metadata.PositionName,
            "Organization": metadata.Organization,
            "Email": metadata.Email,
            "Phone": metadata.Phone,
            "Role": metadata.Role
        }
    }

    return success_response(
        "Metadata details retrieved successfully",
        "تم جلب تفاصيل البيانات الوصفية بنجاح",
        data
    )


# -------------------- ADMIN ENDPOINTS --------------------

@router.post("/admin/datasets")
def create_dataset(
    Name: str = Form(...),
    NameAr: str = Form(...),
    Title: str = Form(None),
    TitleAr: str = Form(None),
    description: str = Form(None),
    descriptionAr: str = Form(None),
    CRS_Name: str = Form(None),
    EPSG: int = Form(3857),
    Keywords: str = Form(None),
    KeywordsAr: str = Form(None),
    img: UploadFile = File(None),
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    new_dataset = DatasetInfo(
        Name=Name, NameAr=NameAr, Title=Title, TitleAr=TitleAr,
        description=description, descriptionAr=descriptionAr,
        CRS_Name=CRS_Name, EPSG=EPSG,
        Keywords=Keywords, KeywordsAr=KeywordsAr, img=None
    )
    db.add(new_dataset)
    db.commit()
    db.refresh(new_dataset)

    # Handle image
    if img:
        folder_path = static_path("dataset", str(new_dataset.DatasetID), ensure=True)
        file_path = os.path.join(folder_path, img.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(img.file, buffer)
        new_dataset.img = f"dataset/{new_dataset.DatasetID}/{img.filename}"
        db.commit()

    return success_response(
        "Dataset created successfully",
        "تم إنشاء مجموعة البيانات بنجاح",
        {"DatasetID": new_dataset.DatasetID}
    )


@router.put("/admin/datasets/{dataset_id}")
def update_dataset(
    dataset_id: int,
    Name: Optional[str] = Form(None),
    NameAr: Optional[str] = Form(None),
    Title: Optional[str] = Form(None),
    TitleAr: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    descriptionAr: Optional[str] = Form(None),
    CRS_Name: Optional[str] = Form(None),
    EPSG: Optional[int] = Form(None),
    Keywords: Optional[str] = Form(None),
    KeywordsAr: Optional[str] = Form(None),
    img: UploadFile = File(None),
    db: Session = Depends(get_db),
    admin_user=Depends(require_admin)
):
    dataset = db.query(DatasetInfo).filter(DatasetInfo.DatasetID == dataset_id).first()
    if not dataset:
        return error_response("Dataset not found", "لم يتم العثور على مجموعة البيانات")

    # Update fields
    for field, value in {
        "Name": Name, "NameAr": NameAr, "Title": Title, "TitleAr": TitleAr,
        "description": description, "descriptionAr": descriptionAr,
        "CRS_Name": CRS_Name, "EPSG": EPSG, "Keywords": Keywords, "KeywordsAr": KeywordsAr
    }.items():
        if value is not None:
            setattr(dataset, field, value)

    # Image replacement
    if img:
        folder_path = static_path("dataset", str(dataset.DatasetID), ensure=True)
        file_path = os.path.join(folder_path, img.filename)
        if dataset.img and os.path.exists(static_path(dataset.img)):
            os.remove(static_path(dataset.img))
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(img.file, buffer)
        dataset.img = f"dataset/{dataset.DatasetID}/{img.filename}"

    db.commit()
    db.refresh(dataset)

    return success_response(
        "Dataset updated successfully",
        "تم تحديث مجموعة البيانات بنجاح",
        {"DatasetID": dataset.DatasetID}
    )


@router.delete("/admin/datasets/{dataset_id}")
def delete_dataset(dataset_id: int, db: Session = Depends(get_db), admin_user=Depends(require_admin)):
    dataset = db.query(DatasetInfo).filter(DatasetInfo.DatasetID == dataset_id).first()
    if not dataset:
        return error_response("Dataset not found", "لم يتم العثور على مجموعة البيانات")
    dataset.IsDeleted = True
    db.commit()
    return success_response(
        "Dataset soft deleted successfully",
        "تم حذف مجموعة البيانات بنجاح",
        {"DatasetID": dataset.DatasetID}
    )


@router.post("/admin/metadata")
def create_metadata(
    DatasetID: int = Form(...),
    Name: str = Form(...),
    NameAr: str = Form(...),
    Title: str = Form(None),
    TitleAr: str = Form(None),
    description: str = Form(None),
    descriptionAr: str = Form(None),
    CreationDate: Optional[date] = Form(None),
    URL: str = Form(None),
    WestBound: Optional[float] = Form(None),
    EastBound: Optional[float] = Form(None),
    NorthBound: Optional[float] = Form(None),
    SouthBound: Optional[float] = Form(None),
    MetadataStandardName: str = Form("ISO19115"),
    MetadataStandardVersion: str = Form("1.0"),
    ContactName: str = Form(None),
    PositionName: str = Form(None),
    Organization: str = Form(None),
    Email: str = Form(None),
    Phone: str = Form(None),
    Role: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    dataset = db.query(DatasetInfo).filter(DatasetInfo.DatasetID == DatasetID, DatasetInfo.IsDeleted == False).first()
    if not dataset:
        return error_response("Dataset not found or deleted", "لم يتم العثور على مجموعة البيانات")

    new_metadata = MetadataInfo(
        DatasetID=DatasetID, Name=Name, NameAr=NameAr, Title=Title, TitleAr=TitleAr,
        description=description, descriptionAr=descriptionAr,
        CreationDate=CreationDate, URL=URL,
        WestBound=WestBound, EastBound=EastBound, NorthBound=NorthBound, SouthBound=SouthBound,
        MetadataStandardName=MetadataStandardName, MetadataStandardVersion=MetadataStandardVersion,
        ContactName=ContactName, PositionName=PositionName, Organization=Organization,
        Email=Email, Phone=Phone, Role=Role
    )
    db.add(new_metadata)
    db.commit()
    db.refresh(new_metadata)

    # Handle file
    if file:
        folder_path = static_path("dataset", str(DatasetID), "metadata", ensure=True)
        file_path = os.path.join(folder_path, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        new_metadata.FilePath = f"dataset/{DatasetID}/metadata/{file.filename}"
        db.commit()

    return success_response(
        "Metadata created successfully",
        "تم إنشاء البيانات الوصفية بنجاح",
        {"MetadataID": new_metadata.MetadataID}
    )


@router.put("/admin/metadata/{metadata_id}")
def update_metadata(
    metadata_id: int,
    DatasetID: Optional[int] = Form(None),
    Name: Optional[str] = Form(None),
    NameAr: Optional[str] = Form(None),
    Title: Optional[str] = Form(None),
    TitleAr: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    descriptionAr: Optional[str] = Form(None),
    CreationDate: Optional[date] = Form(None),
    URL: Optional[str] = Form(None),
    WestBound: Optional[float] = Form(None),
    EastBound: Optional[float] = Form(None),
    NorthBound: Optional[float] = Form(None),
    SouthBound: Optional[float] = Form(None),
    MetadataStandardName: Optional[str] = Form(None),
    MetadataStandardVersion: Optional[str] = Form(None),
    ContactName: Optional[str] = Form(None),
    PositionName: Optional[str] = Form(None),
    Organization: Optional[str] = Form(None),
    Email: Optional[str] = Form(None),
    Phone: Optional[str] = Form(None),
    Role: Optional[str] = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    metadata = db.query(MetadataInfo).filter(MetadataInfo.MetadataID == metadata_id, MetadataInfo.IsDeleted == False).first()
    if not metadata:
        return error_response("Metadata not found", "لم يتم العثور على البيانات الوصفية")

    for field, value in {
        "DatasetID": DatasetID, "Name": Name, "NameAr": NameAr,
        "Title": Title, "TitleAr": TitleAr, "description": description,
        "descriptionAr": descriptionAr, "CreationDate": CreationDate, "URL": URL,
        "WestBound": WestBound, "EastBound": EastBound, "NorthBound": NorthBound, "SouthBound": SouthBound,
        "MetadataStandardName": MetadataStandardName, "MetadataStandardVersion": MetadataStandardVersion,
        "ContactName": ContactName, "PositionName": PositionName, "Organization": Organization,
        "Email": Email, "Phone": Phone, "Role": Role
    }.items():
        if value is not None:
            setattr(metadata, field, value)

    # Handle file
    if file:
        folder_path = static_path("dataset", str(metadata.DatasetID), "metadata", ensure=True)
        file_path = os.path.join(folder_path, file.filename)
        if metadata.FilePath and os.path.exists(static_path(metadata.FilePath)):
            os.remove(static_path(metadata.FilePath))
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        metadata.FilePath = f"dataset/{metadata.DatasetID}/metadata/{file.filename}"

    db.commit()
    db.refresh(metadata)

    return success_response(
        "Metadata updated successfully",
        "تم تحديث البيانات الوصفية بنجاح",
        {"MetadataID": metadata.MetadataID}
    )


@router.delete("/admin/metadata/{metadata_id}")
def delete_metadata(metadata_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    metadata = db.query(MetadataInfo).filter(MetadataInfo.MetadataID == metadata_id).first()
    if not metadata:
        return error_response("Metadata not found", "لم يتم العثور على البيانات الوصفية")
    metadata.IsDeleted = True
    db.commit()
    return success_response(
        "Metadata soft deleted successfully",
        "تم حذف البيانات الوصفية بنجاح",
        {"MetadataID": metadata.MetadataID}
    )
