from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.sql import func
from app.database import Base
from datetime import datetime


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    stored_name = Column(String, nullable=False, unique=True)
    token = Column(String, nullable=False, unique=True, index=True)
    password = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    max_downloads = Column(Integer, nullable=True)
    downloads_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    user_id = Column(String, nullable=True)  # Для личного кабинета

