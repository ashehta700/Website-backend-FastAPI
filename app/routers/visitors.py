# routers/visitors.py
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid
from app.database import get_db
from app.models.visitors import Visitor
from app.schemas.visitors import VisitorCreate
from app.utils.response import success_response, error_response

router = APIRouter(prefix="/track", tags=["Visitors"])

# --- 1️⃣ Endpoint to get visitor IP ---
@router.get("/ip")
def get_client_ip(request: Request):
    ip_address = request.headers.get("x-forwarded-for")
    if ip_address:
        ip_address = ip_address.split(",")[0]  # first IP if multiple
    else:
        ip_address = request.client.host

    return success_response("Visitor IP retrieved successfully", data= {"IPAddress": ip_address})


# --- 2️⃣ Endpoint to track visitor ---
@router.post("/auto")
async def auto_track(visitor: VisitorCreate, request: Request, db: Session = Depends(get_db)):
    """
    Tracks a visitor based on session ID, IP, and country ID.
    Frontend provides:
        - SessionID (optional)
        - IPAddress
        - CountryID (from COUNTRIES_LIST)
        - X, Y coordinates (optional)
    """
    now = datetime.utcnow()
    session_id = visitor.SessionID or str(uuid.uuid4())

    ip_address = visitor.IPAddress or request.client.host

    # --- Check if session already exists ---
    existing_session = db.query(
        Visitor.VisitorID,
        Visitor.VisitAt
    ).filter(
        Visitor.SessionID == session_id
    ).order_by(Visitor.VisitAt.desc()).first()

    if existing_session:
        # Update VisitAt timestamp
        db.execute(
            text("UPDATE Website.Visitors SET VisitAt = :visit WHERE VisitorID = :vid"),
            {"visit": now, "vid": existing_session.VisitorID}
        )
        db.commit()
        visitor_id = existing_session.VisitorID
    else:
        # Insert new visitor
        geom_wkt = f"POINT({visitor.X} {visitor.Y})" if visitor.X is not None and visitor.Y is not None else None
        stmt = text("""
            INSERT INTO Website.Visitors (IPAddress, CountryID, X, Y, Geom, VisitAt, SessionID)
            OUTPUT inserted.VisitorID
            VALUES (:ip, :country, :x, :y, geometry::STGeomFromText(:geom, 4326), :visit, :sess)
        """)
        params = {
            "ip": ip_address,
            "country": visitor.CountryID,
            "x": visitor.X,
            "y": visitor.Y,
            "geom": geom_wkt or "",
            "visit": now,
            "sess": session_id
        }
        result = db.execute(stmt, params)
        visitor_id = result.fetchone()[0]
        db.commit()

    return success_response("Visitor tracked successfully", data={
        "VisitorID": visitor_id,
        "IPAddress": ip_address,
        "SessionID": session_id,
        "CountryID": visitor.CountryID,
        "VisitAt": now.isoformat()
    })
