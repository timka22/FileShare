import httpx
from typing import Optional, List
from app.config import FILE_SERVICE_URL


class FileServiceClient:
    """Клиент для взаимодействия с File Service"""
    
    def __init__(self, base_url: str = FILE_SERVICE_URL):
        self.base_url = base_url
    
    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        password: Optional[str] = None,
        expires_days: Optional[int] = None,
        expires_hours: Optional[int] = None,
        max_downloads: Optional[int] = None,
        user_id: Optional[str] = None
    ) -> dict:
        """Загружает файл через API"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (filename, file_content)}
            data = {}
            if password:
                data["password"] = password
            if expires_days:
                data["expires_days"] = expires_days
            if expires_hours:
                data["expires_hours"] = expires_hours
            if max_downloads:
                data["max_downloads"] = max_downloads
            if user_id:
                data["user_id"] = user_id
            
            response = await client.post(
                f"{self.base_url}/api/files/upload",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()
    
    async def get_file_info(self, token: str) -> dict:
        """Получает информацию о файле"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/files/info/{token}")
            response.raise_for_status()
            return response.json()
    
    async def get_user_files(self, user_id: str) -> List[dict]:
        """Получает список файлов пользователя"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/files/user/{user_id}")
            response.raise_for_status()
            return response.json()
    
    async def update_file(
        self,
        token: str,
        password: Optional[str] = None,
        expires_days: Optional[int] = None,
        expires_hours: Optional[int] = None,
        max_downloads: Optional[int] = None,
        remove_password: bool = False,
        user_id: Optional[str] = None
    ) -> dict:
        """Обновляет настройки файла"""
        async with httpx.AsyncClient() as client:
            data = {}
            if password is not None:
                data["password"] = password
            if expires_days is not None:
                data["expires_days"] = expires_days
            if expires_hours is not None:
                data["expires_hours"] = expires_hours
            if max_downloads is not None:
                data["max_downloads"] = max_downloads
            if remove_password:
                data["remove_password"] = True
            
            params = {}
            if user_id:
                params["user_id"] = user_id
            
            response = await client.patch(
                f"{self.base_url}/api/files/{token}",
                json=data,
                params=params
            )
            response.raise_for_status()
            return response.json()
    
    async def transfer_files(self, old_user_id: str, new_user_id: str) -> dict:
        """Переносит файлы с временного user_id на постоянный"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/files/transfer/{old_user_id}/{new_user_id}"
            )
            response.raise_for_status()
            return response.json()
    
    async def delete_file(self, token: str) -> dict:
        """Удаляет файл"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}/api/files/{token}")
            response.raise_for_status()
            return response.json()
    
    def get_download_url(self, token: str) -> str:
        """Возвращает URL для скачивания файла"""
        return f"{self.base_url}/api/files/download/{token}"
    
    async def download_file(self, token: str, password: Optional[str] = None) -> tuple[bytes, str, dict]:
        """Скачивает файл и возвращает содержимое, имя файла и заголовки"""
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            url = f"{self.base_url}/api/files/download/{token}"
            params = {}
            if password:
                params["password"] = password
            
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            # Получаем имя файла из заголовков Content-Disposition
            filename = "file"
            content_disposition = response.headers.get("content-disposition", "")
            if "filename=" in content_disposition:
                # Извлекаем имя файла из заголовка
                filename_part = content_disposition.split("filename=")[1]
                # Убираем кавычки и пробелы
                filename = filename_part.strip().strip('"').strip("'")
            else:
                # Если имени нет в заголовках, получаем из информации о файле
                try:
                    file_info = await self.get_file_info(token)
                    filename = file_info.get("filename", "file")
                except:
                    filename = "file"
            
            return response.content, filename, response.headers

