import httpx
from typing import Optional
from app.config import FILE_SERVICE_URL


class AuthClient:
    """Клиент для взаимодействия с Auth API"""
    
    def __init__(self, base_url: str = FILE_SERVICE_URL):
        self.base_url = base_url
    
    async def register(self, username: str, email: str, password: str) -> dict:
        """Регистрация нового пользователя"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def login(self, username: str, password: str) -> dict:
        """Авторизация пользователя"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/auth/login",
                json={
                    "username": username,
                    "password": password
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_current_user(self, token: str) -> dict:
        """Получает информацию о текущем пользователе"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/auth/me",
                params={"token": token}
            )
            response.raise_for_status()
            return response.json()

