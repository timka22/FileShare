from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class FileCreate(BaseModel):
    filename: str
    stored_name: str
    password: Optional[str] = None
    expires_at: Optional[datetime] = None
    max_downloads: Optional[int] = None
    user_id: Optional[str] = None


class FileResponse(BaseModel):
    id: int
    filename: str
    token: str
    expires_at: Optional[datetime] = None
    max_downloads: Optional[int] = None
    downloads_count: int
    created_at: datetime
    download_url: str

    class Config:
        from_attributes = True


class FileInfo(BaseModel):
    id: int
    filename: str
    token: str
    expires_at: Optional[datetime] = None
    max_downloads: Optional[int] = None
    downloads_count: int
    created_at: datetime
    is_expired: bool
    is_download_limit_reached: bool
    has_password: bool = False
    user_id: Optional[str] = None

    class Config:
        from_attributes = True


class FileUpdate(BaseModel):
    password: Optional[str] = None
    expires_days: Optional[int] = None
    expires_hours: Optional[int] = None
    max_downloads: Optional[int] = None
    remove_password: bool = False


class DownloadRequest(BaseModel):
    password: Optional[str] = None

