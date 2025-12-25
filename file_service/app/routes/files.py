from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import os
import shutil

from app.database import get_db
from app.models import File as FileModel
from app.schemas import FileResponse, FileInfo, DownloadRequest, FileUpdate
from app.utils import (
    generate_token,
    generate_stored_name,
    parse_expires_at,
    is_file_expired,
    is_download_limit_reached
)

router = APIRouter(prefix="/api/files", tags=["files"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")


@router.post("/upload", response_model=FileResponse)
async def upload_file(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    expires_days: Optional[int] = Form(None),
    expires_hours: Optional[int] = Form(None),
    max_downloads: Optional[int] = Form(None),
    user_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Загружает файл и возвращает ссылку для скачивания"""
    # Создаем директорию для загрузок, если её нет
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Генерируем уникальные имена
    stored_name = generate_stored_name(file.filename)
    token = generate_token()
    
    # Сохраняем файл
    file_path = os.path.join(UPLOAD_DIR, stored_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Парсим срок жизни
    expires_at = parse_expires_at(expires_days, expires_hours)
    
    # Создаем запись в БД
    db_file = FileModel(
        filename=file.filename,
        stored_name=stored_name,
        token=token,
        password=password,
        expires_at=expires_at,
        max_downloads=max_downloads,
        user_id=user_id
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    
    # Формируем URL для скачивания
    download_url = f"/api/files/download/{token}"
    
    return FileResponse(
        id=db_file.id,
        filename=db_file.filename,
        token=db_file.token,
        expires_at=db_file.expires_at,
        max_downloads=db_file.max_downloads,
        downloads_count=db_file.downloads_count,
        created_at=db_file.created_at,
        download_url=download_url
    )


@router.get("/info/{token}", response_model=FileInfo)
async def get_file_info(token: str, db: Session = Depends(get_db)):
    """Получает информацию о файле по токену"""
    db_file = db.query(FileModel).filter(FileModel.token == token).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    expired = is_file_expired(db_file.expires_at)
    limit_reached = is_download_limit_reached(db_file.downloads_count, db_file.max_downloads)
    
    return FileInfo(
        id=db_file.id,
        filename=db_file.filename,
        token=db_file.token,
        expires_at=db_file.expires_at,
        max_downloads=db_file.max_downloads,
        downloads_count=db_file.downloads_count,
        created_at=db_file.created_at,
        is_expired=expired,
        is_download_limit_reached=limit_reached,
        has_password=db_file.password is not None,
        user_id=db_file.user_id
    )


@router.get("/download/{token}")
async def download_file(
    token: str,
    password: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Скачивает файл по токену"""
    db_file = db.query(FileModel).filter(FileModel.token == token).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Проверка пароля
    if db_file.password and db_file.password != password:
        raise HTTPException(status_code=403, detail="Invalid password")
    
    # Проверка срока действия
    if is_file_expired(db_file.expires_at):
        raise HTTPException(status_code=410, detail="File has expired")
    
    # Проверка лимита скачиваний
    if is_download_limit_reached(db_file.downloads_count, db_file.max_downloads):
        raise HTTPException(status_code=410, detail="Download limit reached")
    
    # Увеличиваем счетчик скачиваний
    db_file.downloads_count += 1
    db.commit()
    
    # Возвращаем файл
    file_path = os.path.join(UPLOAD_DIR, db_file.stored_name)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    from fastapi.responses import FileResponse as FastAPIFileResponse
    return FastAPIFileResponse(
        path=file_path,
        filename=db_file.filename,
        media_type="application/octet-stream"
    )


@router.get("/user/{user_id}", response_model=list[FileInfo])
async def get_user_files(user_id: str, db: Session = Depends(get_db)):
    """Получает список файлов пользователя"""
    files = db.query(FileModel).filter(FileModel.user_id == user_id).all()
    
    result = []
    for db_file in files:
        expired = is_file_expired(db_file.expires_at)
        limit_reached = is_download_limit_reached(db_file.downloads_count, db_file.max_downloads)
        
        result.append(FileInfo(
            id=db_file.id,
            filename=db_file.filename,
            token=db_file.token,
            expires_at=db_file.expires_at,
            max_downloads=db_file.max_downloads,
            downloads_count=db_file.downloads_count,
            created_at=db_file.created_at,
            is_expired=expired,
            is_download_limit_reached=limit_reached,
            has_password=db_file.password is not None,
            user_id=db_file.user_id
        ))
    
    return result


@router.patch("/{token}", response_model=FileInfo)
async def update_file(
    token: str,
    file_update: FileUpdate,
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Обновляет настройки файла"""
    db_file = db.query(FileModel).filter(FileModel.token == token).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Проверяем права доступа (только владелец может изменять)
    if user_id and db_file.user_id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to modify this file")
    
    # Обновляем пароль
    if file_update.remove_password:
        db_file.password = None
    elif file_update.password is not None:
        db_file.password = file_update.password
    
    # Обновляем срок действия
    if file_update.expires_days is not None or file_update.expires_hours is not None:
        new_expires_at = parse_expires_at(file_update.expires_days, file_update.expires_hours)
        db_file.expires_at = new_expires_at
    
    # Обновляем лимит скачиваний
    if file_update.max_downloads is not None:
        db_file.max_downloads = file_update.max_downloads
    
    db.commit()
    db.refresh(db_file)
    
    expired = is_file_expired(db_file.expires_at)
    limit_reached = is_download_limit_reached(db_file.downloads_count, db_file.max_downloads)
    
    return FileInfo(
        id=db_file.id,
        filename=db_file.filename,
        token=db_file.token,
        expires_at=db_file.expires_at,
        max_downloads=db_file.max_downloads,
        downloads_count=db_file.downloads_count,
        created_at=db_file.created_at,
        is_expired=expired,
        is_download_limit_reached=limit_reached,
        has_password=db_file.password is not None,
        user_id=db_file.user_id
    )


@router.post("/transfer/{old_user_id}/{new_user_id}")
async def transfer_files(
    old_user_id: str,
    new_user_id: str,
    db: Session = Depends(get_db)
):
    """Переносит файлы с временного user_id на постоянный user_id (при регистрации/входе)"""
    files = db.query(FileModel).filter(FileModel.user_id == old_user_id).all()
    
    transferred_count = 0
    for db_file in files:
        db_file.user_id = new_user_id
        transferred_count += 1
    
    db.commit()
    
    return {"message": f"Transferred {transferred_count} files", "count": transferred_count}


@router.delete("/{token}")
async def delete_file(token: str, db: Session = Depends(get_db)):
    """Удаляет файл"""
    db_file = db.query(FileModel).filter(FileModel.token == token).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Удаляем файл с диска
    file_path = os.path.join(UPLOAD_DIR, db_file.stored_name)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Удаляем запись из БД
    db.delete(db_file)
    db.commit()
    
    return {"message": "File deleted successfully"}

