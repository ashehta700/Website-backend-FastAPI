from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime , Boolean, Unicode, UnicodeText
from app.database import Base
from datetime import datetime
from sqlalchemy.orm import relationship
from app.models import lookups



class Projects(Base):
    __tablename__ = "Projects"
    __table_args__ = {'schema': 'Website'}

    ProjectID = Column(Integer, primary_key=True, index=True)
    NameEn = Column(String(100))
    NameAr = Column(Unicode(255), nullable=False)
    DescriptionEn = Column(String(255))
    DescriptionAr = Column(UnicodeText)
    ServicesName = Column(String(255))
    ServicesLink = Column(String(255))
    ImagePath = Column(String(255))
    VideoPath = Column(String(255))
    CreatedAt = Column(DateTime, default=datetime.utcnow)
    CreatedByUserID = Column(Integer, ForeignKey("Website.Users.UserID"))
    UpdatedAt = Column(DateTime)
    UpdatedByUserID = Column(Integer, ForeignKey("Website.Users.UserID"))
    IsDeleted = Column(Boolean)