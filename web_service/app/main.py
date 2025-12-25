from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.routes import pages

app = FastAPI(title="FileShare Web")

# Middleware для сессий (для user_id)
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

# Статические файлы ДОЛЖНЫ быть подключены ДО роутов
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Подключаем роуты
app.include_router(pages.router)


@app.get("/health")
async def health():
    return {"status": "ok"}