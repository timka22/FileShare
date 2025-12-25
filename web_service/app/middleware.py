from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления информации об авторизации в контекст запроса"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Проверяем наличие сессии безопасно
        try:
            request.state.is_authenticated = "auth_token" in request.session
        except (AttributeError, AssertionError):
            # Если сессия еще не инициализирована, считаем пользователя неавторизованным
            request.state.is_authenticated = False
        
        response = await call_next(request)
        return response

