from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routes import files, auth

app = FastAPI(
    title="FileShare API",
    description="Микросервис для управления файлами",
    version="1.0.0"
)

# CORS для взаимодействия с веб-сервисом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(files.router)
app.include_router(auth.router)

# Инициализация БД при старте
@app.on_event("startup")
async def startup_event():
    init_db()


@app.get("/")
async def root():
    return {"message": "FileShare API Service", "docs": "/docs"}

