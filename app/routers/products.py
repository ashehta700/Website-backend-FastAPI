# routers/products.py
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
import os, shutil
from urllib.parse import quote

from app.models.products import Product
from app.models.users import User
from app.schemas.products import ProductResponse
from app.utils.response import success_response, error_response
from app.database import get_db
from app.utils.utils import require_admin
from app.utils.paths import static_path

router = APIRouter(prefix="/products", tags=["Products"])

PRODUCT_IMAGES_DIR = static_path("Products", "images", ensure=True)
PRODUCT_VIDEOS_DIR = static_path("Products", "videos", ensure=True)


# -------------------------
# Helper functions
# -------------------------
def parse_services(product: Product) -> List[dict]:
    """
    Convert comma-separated services fields into structured list.
    """
    names = (product.ServicesName or "").split(",") if product.ServicesName else []
    descriptions = (product.ServicesDescription or "").split(",") if product.ServicesDescription else []
    links = (product.ServicesLink or "").split(",") if product.ServicesLink else []

    services = []
    for i in range(max(len(names), len(descriptions), len(links))):
        services.append({
            "Name": names[i].strip() if i < len(names) else None,
            "Description": descriptions[i].strip() if i < len(descriptions) else None,
            "Link": links[i].strip() if i < len(links) else None
        })
    return services


def format_product(product: Product, request: Request) -> dict:
    """
    Format product info with services list and full image/video URLs.
    """
    item = ProductResponse.from_orm(product).dict()
    item["Services"] = parse_services(product)

    # Remove old individual service fields
    item.pop("ServicesName", None)
    item.pop("ServicesDescription", None)
    item.pop("ServicesLink", None)

    base_url = str(request.base_url).rstrip("/")

    if item.get("ImagePath"):
        item["ImagePath"] = f"{base_url}/static/Products/images/{quote(os.path.basename(item['ImagePath']))}"
    if item.get("VideoPath"):
        item["VideoPath"] = f"{base_url}/static/Products/videos/{quote(os.path.basename(item['VideoPath']))}"

    return item


def save_uploaded_file(upload: UploadFile, folder: str) -> str:
    """
    Save uploaded image or video and return path.
    """
    file_path = os.path.join(folder, upload.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return file_path


# -------------------------
# Public Endpoints
# -------------------------
@router.get("/all")
def get_all_products(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).filter(Product.IsDeleted != True).order_by(Product.CreatedAt.desc()).all()
    data = [format_product(p, request) for p in products]
    return success_response(
        "Products retrieved successfully",
        "تم جلب المنتجات بنجاح",
        data
    )


# -------------------------
# Admin Endpoints
# -------------------------
@router.get("/admin")
def get_all_products_admin(request: Request, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.CreatedAt.desc()).all()
    data = [format_product(p, request) for p in products]
    return success_response(
        "All products retrieved successfully",
        "تم جلب جميع المنتجات بنجاح",
        data
    )


@router.get("/{product_id}")
def get_product(product_id: int, request: Request, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.ProductID == product_id, Product.IsDeleted != True).first()
    if not product:
        return error_response("Product not found", "لم يتم العثور على المنتج")
    data = format_product(product, request)
    return success_response(
        "Product retrieved successfully",
        "تم جلب المنتج بنجاح",
        data
    )


@router.post("/add")
def create_product(
    NameEn: str = Form(...),
    NameAr: Optional[str] = Form(None),
    DescriptionEn: Optional[str] = Form(None),
    DescriptionAr: Optional[str] = Form(None),
    ServicesName: Optional[str] = Form(None),
    ServicesDescription: Optional[str] = Form(None),
    ServicesLink: Optional[str] = Form(None),
    ImagePath: Optional[UploadFile] = File(None),
    VideoPath: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    request: Request = None
):
    image_path = save_uploaded_file(ImagePath, PRODUCT_IMAGES_DIR) if ImagePath else None
    video_path = save_uploaded_file(VideoPath, PRODUCT_VIDEOS_DIR) if VideoPath else None

    new_product = Product(
        NameEn=NameEn,
        NameAr=NameAr,
        DescriptionEn=DescriptionEn,
        DescriptionAr=DescriptionAr,
        ServicesName=ServicesName,
        ServicesDescription=ServicesDescription,
        ServicesLink=ServicesLink,
        ImagePath=image_path,
        VideoPath=video_path,
        CreatedAt=datetime.utcnow(),
        CreatedByUserID=current_user.UserID,
        IsDeleted=False
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    data = format_product(new_product, request)
    return success_response(
        "Product created successfully",
        "تم إنشاء المنتج بنجاح",
        data
    )


@router.put("/{product_id}")
def update_product(
    product_id: int,
    NameEn: Optional[str] = Form(None),
    NameAr: Optional[str] = Form(None),
    DescriptionEn: Optional[str] = Form(None),
    DescriptionAr: Optional[str] = Form(None),
    ServicesName: Optional[str] = Form(None),
    ServicesDescription: Optional[str] = Form(None),
    ServicesLink: Optional[str] = Form(None),
    ImagePath: Optional[UploadFile] = File(None),
    VideoPath: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    request: Request = None
):
    product = db.query(Product).filter(Product.ProductID == product_id, Product.IsDeleted != True).first()
    if not product:
        return error_response("Product not found", "لم يتم العثور على المنتج")

    if NameEn is not None: product.NameEn = NameEn
    if NameAr is not None: product.NameAr = NameAr
    if DescriptionEn is not None: product.DescriptionEn = DescriptionEn
    if DescriptionAr is not None: product.DescriptionAr = DescriptionAr
    if ServicesName is not None: product.ServicesName = ServicesName
    if ServicesDescription is not None: product.ServicesDescription = ServicesDescription
    if ServicesLink is not None: product.ServicesLink = ServicesLink

    if ImagePath:
        if product.ImagePath and os.path.exists(product.ImagePath):
            os.remove(product.ImagePath)
        product.ImagePath = save_uploaded_file(ImagePath, PRODUCT_IMAGES_DIR)

    if VideoPath:
        if product.VideoPath and os.path.exists(product.VideoPath):
            os.remove(product.VideoPath)
        product.VideoPath = save_uploaded_file(VideoPath, PRODUCT_VIDEOS_DIR)

    product.UpdatedAt = datetime.utcnow()
    product.UpdatedByUserID = current_user.UserID
    db.commit()
    db.refresh(product)
    data = format_product(product, request)
    return success_response(
        "Product updated successfully",
        "تم تحديث المنتج بنجاح",
        data
    )


@router.delete("/{product_id}")
def delete_product(product_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.ProductID == product_id, Product.IsDeleted != True).first()
    if not product:
        return error_response("Product not found", "لم يتم العثور على المنتج")

    product.IsDeleted = True
    product.UpdatedAt = datetime.utcnow()
    product.UpdatedByUserID = current_user.UserID
    db.commit()
    return success_response(
        "Product soft-deleted successfully",
        "تم حذف المنتج بنجاح"
    )
