from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class ContactUs(Base):
    __tablename__ = "ContactUs"
    __table_args__ = {"schema": "Website"}

    ContactID = Column(Integer, primary_key=True, index=True)
    FirstName = Column(String(100), nullable=False)
    LastName = Column(String(100), nullable=True)
    Subject = Column(String(150), nullable=True)
    Body = Column(Text, nullable=True)
    AttachPath = Column(String(500), nullable=True)
    UserID = Column(Integer, ForeignKey("Website.Users.UserID"), nullable=True)
    CreatedAt = Column(DateTime, default=datetime.utcnow)
    Email = Column(String(150), nullable=True)
    PhoneNumber = Column(String(50), nullable=True)
    Organization = Column(String(200), nullable=True)
    ReplyStatus = Column(Boolean, default=False)
    Responses = relationship("ContactUsResponse", back_populates="Contact")





class ContactUsResponse(Base):
    __tablename__ = "ContactUsResponse"
    __table_args__ = {"schema": "Website"}

    ResponseID = Column(Integer, primary_key=True, index=True)
    Subject = Column(String(150), nullable=True)
    Body = Column(Text, nullable=True)
    AttachPath = Column(String(500), nullable=True)
    CreatedByUserID = Column(Integer, ForeignKey("Website.Users.UserID"), nullable=False)
    CreatedAt = Column(DateTime, default=datetime.utcnow)
    ContactID = Column(Integer, ForeignKey("Website.ContactUs.ContactID"), nullable=False)

    Contact = relationship("ContactUs", back_populates="Responses")
