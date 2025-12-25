import secrets
import os
from datetime import datetime, timedelta
from typing import Optional


def generate_token() -> str:
    """Генерирует уникальный токен для файла"""
    return secrets.token_urlsafe(32)


def generate_stored_name(filename: str) -> str:
    """Генерирует уникальное имя для хранения файла"""
    ext = os.path.splitext(filename)[1]
    return f"{secrets.token_urlsafe(16)}{ext}"


def parse_expires_at(days: Optional[int] = None, hours: Optional[int] = None) -> Optional[datetime]:
    """Парсит срок жизни файла"""
    if days is None and hours is None:
        return None
    
    delta = timedelta()
    if days:
        delta += timedelta(days=days)
    if hours:
        delta += timedelta(hours=hours)
    
    return datetime.utcnow() + delta


def is_file_expired(expires_at: Optional[datetime]) -> bool:
    """Проверяет, истек ли срок действия файла"""
    if expires_at is None:
        return False
    return datetime.utcnow() > expires_at


def is_download_limit_reached(downloads_count: int, max_downloads: Optional[int]) -> bool:
    """Проверяет, достигнут ли лимит скачиваний"""
    if max_downloads is None:
        return False
    return downloads_count >= max_downloads

