# models.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True)
    tariff     = Column(String, nullable=False)
    paid       = Column(Boolean, default=False)
    sheet_url  = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
