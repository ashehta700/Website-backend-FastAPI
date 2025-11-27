from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.utils.response import success_response 
from datetime import datetime
from app.models.users import User
from app.models.visitors import Visitor
from app.models.dashboard import DownloadItem, DownloadRequest, NGDModsBiblio, BibliographyDownloadRequest
from app.models.lookups import UserTitle
from app.database import get_db
from sqlalchemy import func

router = APIRouter(prefix="/statistics", tags=["Statistics"])



# get the statistics for the home page like the total numbers of the users or visitors 
@router.get("")
async def get_summary(request: Request, db: Session = Depends(get_db)):
    users_count = db.query(User).count()
    visitors_count = db.query(Visitor).count()
    downloads_count = db.query(DownloadItem).count()
    requests_count = db.query(DownloadRequest).count()
    
    # Total Technical Requests: count of distinct requests in BIBLIOGRAPHY_DOWNLOAD_REQUESTS
    total_technical_requests = (
        db.query(func.count(func.distinct(BibliographyDownloadRequest.ReqNo)))
        .scalar()
    )
    
    # Total Download Reports: count of all files (ReportID) in NGD_MODS_BIBLIO 
    # that are related to requests in BIBLIOGRAPHY_DOWNLOAD_REQUESTS (by joining on MODS)
    total_download_reports = (
        db.query(func.count(func.distinct(NGDModsBiblio.ReportID)))
        .join(
            BibliographyDownloadRequest,
            NGDModsBiblio.MODS == BibliographyDownloadRequest.MODS
        )
        .scalar()
    )
    
    # titles_count = db.query(UserTitle).count()

    data = {
        "total_users": users_count,
        "total_visitors": visitors_count,
        "total_requests": requests_count,
        "total_downloads": downloads_count,
        "total_technical_requests": total_technical_requests,
        "total_download_reports": total_download_reports,
    }

    return success_response("Statistics summary", data=data)