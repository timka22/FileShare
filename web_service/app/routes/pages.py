from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import secrets
import httpx

from app.client import FileServiceClient
from app.auth_client import AuthClient

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
file_client = FileServiceClient()
auth_client = AuthClient()


def get_user_id(request: Request) -> str:
    """Получает user_id из сессии (авторизованный или временный)"""
    # Сначала проверяем авторизованного пользователя
    if "user_id" in request.session:
        return request.session["user_id"]

    # Если нет авторизованного пользователя, создаем временный ID
    temp_user_id = secrets.token_urlsafe(16)
    request.session["user_id"] = temp_user_id
    return temp_user_id


def get_auth_token(request: Request) -> Optional[str]:
    """Получает токен авторизации из сессии"""
    return request.session.get("auth_token")


def is_authenticated(request: Request) -> bool:
    """Проверяет, авторизован ли пользователь"""
    return "auth_token" in request.session and "user_id" in request.session


async def get_template_context(request: Request, **kwargs):
    """Создает базовый контекст для шаблонов"""
    context = {
        "request": request,
        "is_authenticated": is_authenticated(request),
        "username": request.session.get("username")  # Берем из сессии для производительности
    }

    # Если username нет в сессии, но пользователь авторизован, получаем его
    if is_authenticated(request) and not context["username"]:
        auth_token = get_auth_token(request)
        if auth_token:
            try:
                user_info = await auth_client.get_current_user(auth_token)
                username = user_info.get("username")
                context["username"] = username
                request.session["username"] = username  # Сохраняем в сессию
            except Exception:
                # Если не удалось получить информацию, просто игнорируем
                pass

    context.update(kwargs)
    return context


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница с формой загрузки"""
    context = await get_template_context(request)
    return templates.TemplateResponse("index.html", context)


@router.post("/upload", response_class=HTMLResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    expires_days: Optional[int] = Form(None),
    expires_hours: Optional[int] = Form(None),
    max_downloads: Optional[int] = Form(None)
):
    """Обработка загрузки файла"""
    try:
        # Читаем содержимое файла
        content = await file.read()

        # Получаем user_id из сессии
        user_id = get_user_id(request)

        # Загружаем файл через API
        result = await file_client.upload_file(
            file_content=content,
            filename=file.filename,
            password=password,
            expires_days=expires_days,
            expires_hours=expires_hours,
            max_downloads=max_downloads,
            user_id=user_id
        )

        # Формируем полный URL для скачивания
        base_url = str(request.base_url).rstrip("/")
        full_download_url = f"{base_url}/download/{result['token']}"

        # Проверяем, является ли запрос AJAX (через XMLHttpRequest)
        # Если да, возвращаем JSON с URL для редиректа
        accept_header = request.headers.get("accept", "")
        if "application/json" in accept_header or request.headers.get("x-requested-with") == "XMLHttpRequest":
            # Для AJAX запросов возвращаем JSON с URL для редиректа
            success_url = f"{base_url}/success/{result['token']}"
            from fastapi.responses import JSONResponse
            return JSONResponse({
                "success": True,
                "redirect_url": success_url,
                "token": result['token']
            })

        # Для обычных запросов возвращаем HTML страницу
        context = await get_template_context(request, file_info=result, download_url=full_download_url)
        return templates.TemplateResponse("success.html", context)
    except Exception as e:
        context = await get_template_context(request, error=str(e))
        return templates.TemplateResponse("error.html", context, status_code=500)


@router.get("/download/{token}", response_class=HTMLResponse)
async def download_page(request: Request, token: str):
    """Страница скачивания файла"""
    try:
        file_info = await file_client.get_file_info(token)

        # Проверяем, требуется ли пароль
        requires_password = file_info.get("has_password", False)

        # Проверяем, является ли пользователь владельцем файла
        user_id = get_user_id(request)
        is_owner = file_info.get("user_id") == user_id

        context = await get_template_context(
            request,
            file_info=file_info,
            token=token,
            requires_password=requires_password,
            is_expired=file_info.get("is_expired", False),
            is_limit_reached=file_info.get("is_download_limit_reached", False),
            is_owner=is_owner
        )
        return templates.TemplateResponse("download.html", context)
    except HTTPException:
        raise
    except Exception as e:
        context = await get_template_context(request, error=f"File not found: {str(e)}")
        return templates.TemplateResponse("error.html", context, status_code=404)


@router.post("/download/{token}")
async def download_file(request: Request, token: str, password: Optional[str] = Form(None)):
    """Проксирование скачивания файла через Web Service"""
    from fastapi.responses import Response
    from urllib.parse import quote
    import base64

    try:
        # Сначала получаем информацию о файле для имени
        file_info = await file_client.get_file_info(token)
        filename = file_info.get("filename", "file")

        # Получаем файл через File Service
        file_content, _, headers = await file_client.download_file(token, password)

        # Правильно кодируем имя файла для заголовка Content-Disposition
        # Starlette/FastAPI использует latin-1 для заголовков HTTP, поэтому нужно быть осторожным
        # Используем только ASCII-совместимые символы в основном filename
        try:
            # Пытаемся создать ASCII-совместимое имя
            safe_filename = filename.encode('ascii', 'ignore').decode('ascii')
            if not safe_filename or safe_filename.strip() == '':
                safe_filename = 'file'
        except:
            safe_filename = 'file'

        # Кодируем оригинальное имя в UTF-8 для filename* (RFC 5987)
        # Используем percent-encoding для UTF-8 байтов (только заглавные буквы в hex)
        filename_bytes = filename.encode('utf-8')
        encoded_parts = []
        for b in filename_bytes:
            # Кодируем все байты, которые не являются безопасными ASCII символами
            if 32 <= b <= 126 and b not in [34, 37, 39, 92]:  # Печатные ASCII кроме проблемных символов
                encoded_parts.append(chr(b))
            else:
                # Используем заглавные буквы для hex кодирования
                encoded_parts.append(f'%{b:02X}')
        encoded_filename = ''.join(encoded_parts)

        # Убеждаемся, что encoded_filename содержит только ASCII символы
        # Это должно быть так, так как мы используем только ASCII символы и %XX
        if not all(ord(c) < 128 for c in encoded_filename):
            # Если по какой-то причине есть не-ASCII символы, используем только безопасное имя
            content_disposition = f'attachment; filename="{safe_filename}"'
        else:
            # Формируем заголовок Content-Disposition согласно RFC 5987
            # Важно: вся строка должна быть ASCII-совместимой
            content_disposition = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}'

        # Возвращаем файл пользователю
        # Используем raw headers для обхода проблем с кодировкой
        response = Response(
            content=file_content,
            media_type="application/octet-stream"
        )
        # Устанавливаем заголовки напрямую, чтобы избежать проблем с кодировкой
        # Используем lowercase ключи для совместимости
        # Убеждаемся, что заголовок может быть закодирован в latin-1 (требование HTTP)
        try:
            # Проверяем, что строка может быть закодирована в latin-1
            content_disposition.encode('latin-1')
            response.headers["content-disposition"] = content_disposition
        except (UnicodeEncodeError, ValueError):
            # Если все еще есть проблемы, используем только безопасное имя
            response.headers["content-disposition"] = f'attachment; filename="{safe_filename}"'
        response.headers["content-length"] = str(len(file_content))
        return response
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="File not found")
        elif e.response.status_code == 403:
            raise HTTPException(status_code=403, detail="Invalid password")
        elif e.response.status_code == 410:
            raise HTTPException(status_code=410, detail="File expired or download limit reached")
        else:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/success/{token}", response_class=HTMLResponse)
async def success_page(request: Request, token: str):
    """Страница успешной загрузки файла"""
    try:
        file_info = await file_client.get_file_info(token)

        # Формируем полный URL для скачивания
        base_url = str(request.base_url).rstrip("/")
        full_download_url = f"{base_url}/download/{token}"

        context = await get_template_context(request, file_info=file_info, download_url=full_download_url)
        return templates.TemplateResponse("success.html", context)
    except Exception as e:
        context = await get_template_context(request, error=f"File not found: {str(e)}")
        return templates.TemplateResponse("error.html", context, status_code=404)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Личный кабинет пользователя"""
    try:
        user_id = get_user_id(request)
        files = await file_client.get_user_files(user_id)

        context = await get_template_context(request, files=files, user_id=user_id)
        return templates.TemplateResponse("dashboard.html", context)
    except Exception as e:
        context = await get_template_context(request, error=str(e))
        return templates.TemplateResponse("error.html", context, status_code=500)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница авторизации"""
    context = await get_template_context(request)
    return templates.TemplateResponse("login.html", context)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Страница регистрации"""
    context = await get_template_context(request)
    return templates.TemplateResponse("register.html", context)


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Обработка авторизации"""
    try:
        # Сохраняем старый user_id (временный) перед входом
        old_user_id = get_user_id(request)

        result = await auth_client.login(username, password)
        new_user_id = result["user_id"]

        # Переносим файлы с временного user_id на аккаунт пользователя
        try:
            await file_client.transfer_files(old_user_id, new_user_id)
        except Exception:
            pass

        # Сохраняем токен, user_id и username в сессии
        request.session["auth_token"] = result["access_token"]
        request.session["user_id"] = new_user_id
        request.session["username"] = username

        return RedirectResponse(url="/dashboard", status_code=303)
    
    except httpx.HTTPStatusError as e:
        # Обрабатываем HTTP ошибки от auth service
        error_message = "Неверное имя пользователя или пароль"
        
        try:
            error_detail = e.response.json()
            
            # Обрабатываем ошибки валидации Pydantic (422)
            if e.response.status_code == 422 and isinstance(error_detail.get("detail"), list):
                pydantic_errors = error_detail["detail"]
                error_messages = []
                
                for err in pydantic_errors:
                    field = err.get("loc", [])[-1] if err.get("loc") else "unknown"
                    msg = err.get("msg", "")
                    
                    field_names = {
                        "username": "Имя пользователя",
                        "password": "Пароль"
                    }
                    field_ru = field_names.get(field, field)
                    
                    if "at least" in msg and "characters" in msg:
                        min_length = err.get("ctx", {}).get("min_length", 6)
                        error_messages.append(f"{field_ru} должен содержать минимум {min_length} символов")
                    elif "required" in msg.lower():
                        error_messages.append(f"{field_ru} обязателен для заполнения")
                    else:
                        error_messages.append(f"{field_ru}: {msg}")
                
                error_message = ". ".join(error_messages) if error_messages else "Проверьте введенные данные"
            
            # Обрабатываем обычные текстовые ошибки - переводим на русский
            elif "detail" in error_detail and isinstance(error_detail["detail"], str):
                detail = error_detail["detail"].lower()
                
                # Словарь переводов типичных ошибок
                if "invalid username or password" in detail or "incorrect" in detail:
                    error_message = "Неверное имя пользователя или пароль"
                elif "user not found" in detail or "not found" in detail:
                    error_message = "Пользователь не найден"
                elif "invalid credentials" in detail:
                    error_message = "Неверные данные для входа"
                else:
                    # Если не можем перевести, используем стандартное сообщение
                    error_message = "Неверное имя пользователя или пароль"
        
        except:
            # Если не удалось распарсить, используем стандартные сообщения по коду ошибки
            if e.response.status_code == 401:
                error_message = "Неверное имя пользователя или пароль"
            elif e.response.status_code == 404:
                error_message = "Пользователь не найден"
            else:
                error_message = "Ошибка при входе"
        
        context = await get_template_context(
            request, 
            error=error_message, 
            username=username
        )
        return templates.TemplateResponse("login.html", context, status_code=200)
    
    except Exception as e:
        context = await get_template_context(
            request, 
            error="Ошибка при входе. Попробуйте позже.", 
            username=username
        )
        return templates.TemplateResponse("login.html", context, status_code=200)


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    """Обработка регистрации"""
    try:
        result = await auth_client.register(username, email, password)

        # Сохраняем токен, user_id и username в сессии
        request.session["auth_token"] = result["access_token"]
        request.session["user_id"] = result["user_id"]
        request.session["username"] = username

        return RedirectResponse(url="/dashboard", status_code=303)
    
    except httpx.HTTPStatusError as e:
        # Обрабатываем HTTP ошибки от auth service
        error_message = "Ошибка при регистрации"
        
        try:
            error_detail = e.response.json()
            
            # Обрабатываем ошибки валидации Pydantic (422)
            if e.response.status_code == 422 and isinstance(error_detail.get("detail"), list):
                pydantic_errors = error_detail["detail"]
                error_messages = []
                
                for err in pydantic_errors:
                    field = err.get("loc", [])[-1] if err.get("loc") else "unknown"
                    msg = err.get("msg", "")
                    
                    field_names = {
                        "username": "Имя пользователя",
                        "email": "Email",
                        "password": "Пароль"
                    }
                    field_ru = field_names.get(field, field)
                    
                    if "at least" in msg and "characters" in msg:
                        min_length = err.get("ctx", {}).get("min_length", 6)
                        error_messages.append(f"{field_ru} должен содержать минимум {min_length} символов")
                    elif "valid email" in msg.lower():
                        error_messages.append(f"{field_ru} должен быть действительным email адресом")
                    elif "required" in msg.lower():
                        error_messages.append(f"{field_ru} обязателен для заполнения")
                    else:
                        error_messages.append(f"{field_ru}: {msg}")
                
                error_message = ". ".join(error_messages) if error_messages else "Проверьте введенные данные"
            
            # Обрабатываем обычные текстовые ошибки - переводим на русский
            elif "detail" in error_detail and isinstance(error_detail["detail"], str):
                detail = error_detail["detail"].lower()
                
                # Словарь переводов типичных ошибок
                if "already exists" in detail or "already registered" in detail:
                    error_message = "Пользователь с таким именем или email уже существует"
                elif "username" in detail and "taken" in detail:
                    error_message = "Имя пользователя уже занято"
                elif "email" in detail and "taken" in detail:
                    error_message = "Email уже используется"
                elif "invalid email" in detail:
                    error_message = "Некорректный email адрес"
                elif "password" in detail and ("short" in detail or "length" in detail):
                    error_message = "Пароль слишком короткий (минимум 6 символов)"
                else:
                    # Если не можем перевести, используем стандартное сообщение
                    error_message = "Ошибка при регистрации. Проверьте введенные данные"
        
        except:
            # Если не удалось распарсить, используем стандартные сообщения по коду ошибки
            if e.response.status_code == 422:
                error_message = "Некорректные данные. Проверьте введенные значения"
            elif e.response.status_code == 400:
                error_message = "Пользователь с таким именем или email уже существует"
            else:
                error_message = "Ошибка при регистрации"
        
        context = await get_template_context(
            request, 
            error=error_message, 
            username=username, 
            email=email
        )
        return templates.TemplateResponse("register.html", context, status_code=200)
    
    except Exception as e:
        error_message = "Ошибка при регистрации. Попробуйте позже."
        context = await get_template_context(
            request, 
            error=error_message, 
            username=username, 
            email=email
        )
        return templates.TemplateResponse("register.html", context, status_code=200)

@router.post("/logout")
async def logout(request: Request):
    """Выход из системы"""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/file/{token}/settings", response_class=HTMLResponse)
async def file_settings(request: Request, token: str):
    """Страница настроек файла"""
    try:
        user_id = get_user_id(request)
        file_info = await file_client.get_file_info(token)

        # Проверяем права доступа
        if file_info.get("user_id") != user_id:
            context = await get_template_context(request, error="You don't have permission to modify this file")
            return templates.TemplateResponse("error.html", context, status_code=403)

        context = await get_template_context(request, file_info=file_info, token=token)
        return templates.TemplateResponse("file_settings.html", context)
    except Exception as e:
        context = await get_template_context(request, error=f"Error: {str(e)}")
        return templates.TemplateResponse("error.html", context, status_code=500)


@router.post("/file/{token}/settings")
async def update_file_settings(
    request: Request,
    token: str,
    password: Optional[str] = Form(None),
    remove_password: bool = Form(False),
    expires_days: Optional[int] = Form(None),
    expires_hours: Optional[int] = Form(None),
    max_downloads: Optional[int] = Form(None)
):
    """Обновление настроек файла"""
    try:
        user_id = get_user_id(request)

        # Преобразуем пустые строки в None
        expires_days = expires_days if expires_days else None
        expires_hours = expires_hours if expires_hours else None
        max_downloads = max_downloads if max_downloads else None
        password = password if password else None

        await file_client.update_file(
            token=token,
            password=password,
            expires_days=expires_days,
            expires_hours=expires_hours,
            max_downloads=max_downloads,
            remove_password=remove_password,
            user_id=user_id
        )

        return RedirectResponse(url=f"/file/{token}/settings", status_code=303)
    except Exception as e:
        context = await get_template_context(request, error=f"Failed to update file: {str(e)}")
        return templates.TemplateResponse("error.html", context, status_code=500)


@router.post("/delete/{token}")
async def delete_file(request: Request, token: str):
    """Удаление файла"""
    try:
        await file_client.delete_file(token)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        context = await get_template_context(request, error=f"Failed to delete file: {str(e)}")
        return templates.TemplateResponse("error.html", context, status_code=500)
