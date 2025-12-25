# FileShare - Учебный проект для обмена файлами

Простой веб-сервис для обмена файлами с микросервисной архитектурой. Проект демонстрирует принципы REST API, работу с БД и взаимодействие микросервисов.

## Архитектура

Проект состоит из двух микросервисов:

1. **File Service** (порт 18000) - API сервис для управления файлами
   - REST API endpoints
   - Работа с базой данных SQLite
   - Хранение файлов
   - Бизнес-логика (срок жизни, лимиты скачиваний, пароли)

2. **Web Service** (порт 18080) - Веб-интерфейс
   - HTML страницы с Jinja2 шаблонами
   - Взаимодействие с File Service через HTTP API
   - Формы загрузки и управления файлами
   - Личный кабинет пользователя

## Технологии

- Python 3.11+
- FastAPI
- SQLite + SQLAlchemy
- Jinja2 (HTML шаблоны)
- Docker & Docker Compose
- HTTP клиент (httpx) для взаимодействия микросервисов

## Возможности

- ✅ Загрузка файлов с настройками доступа
- ✅ Уникальные ссылки для скачивания
- ✅ Парольная защита файлов
- ✅ Ограничение срока жизни файла
- ✅ Лимит на количество скачиваний
- ✅ Личный кабинет со списком файлов
- ✅ Swagger документация API
- ✅ Красивый минималистичный интерфейс

## Быстрый старт

### Вариант 1: Docker Compose (рекомендуется)

```bash
# Запустить все сервисы
docker-compose up --build

# Сервисы будут доступны:
# - File Service API: http://localhost:18000
# - Web Interface: http://localhost:18080
# - Swagger: http://localhost:18000/docs
```

**Примечание:** Если возникают проблемы с подключением к Docker registry (ошибки DNS/сети), попробуйте:
- Проверить настройки DNS на сервере
- Использовать локальный запуск (см. Вариант 2)
- Настроить Docker proxy или использовать альтернативный registry

### Вариант 2: Локальный запуск

#### 1. Запустить File Service

```bash
cd file_service
pip install -r requirements.txt

# Создать директорию для загрузок
mkdir -p uploads

# Запустить сервис
uvicorn app.main:app --reload --port 8000
```

#### 2. Запустить Web Service

В новом терминале:

```bash
cd web_service
pip install -r requirements.txt

# Запустить веб-сервис
uvicorn app.main:app --reload --port 8080
```

#### 3. Открыть в браузере

- Веб-интерфейс: http://localhost:18080
- API документация: http://localhost:18000/docs

## Структура проекта

```
fileshare/
├── file_service/          # Микросервис для файлов
│   ├── app/
│   │   ├── main.py       # Точка входа FastAPI
│   │   ├── database.py   # Настройка БД
│   │   ├── models.py     # SQLAlchemy модели
│   │   ├── schemas.py    # Pydantic схемы
│   │   ├── utils.py      # Утилиты
│   │   └── routes/
│   │       └── files.py  # API endpoints
│   ├── uploads/          # Директория для файлов
│   ├── requirements.txt
│   └── Dockerfile
│
├── web_service/          # Микросервис веб-интерфейса
│   ├── app/
│   │   ├── main.py       # Точка входа FastAPI
│   │   ├── config.py     # Конфигурация
│   │   ├── client.py     # HTTP клиент для File Service
│   │   ├── routes/
│   │   │   └── pages.py  # Веб-страницы
│   │   ├── templates/    # Jinja2 шаблоны
│   │   └── static/       # CSS стили
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml
└── README.md
```

## API Endpoints

### File Service (http://localhost:18000)

- `POST /api/files/upload` - Загрузка файла
- `GET /api/files/info/{token}` - Информация о файле
- `GET /api/files/download/{token}` - Скачивание файла
- `GET /api/files/user/{user_id}` - Список файлов пользователя
- `DELETE /api/files/{token}` - Удаление файла
- `GET /docs` - Swagger документация

### Web Service (http://localhost:18080)

- `GET /` - Главная страница (форма загрузки)
- `POST /upload` - Обработка загрузки
- `GET /download/{token}` - Страница скачивания
- `POST /download/{token}` - Скачивание файла
- `GET /dashboard` - Личный кабинет
- `POST /delete/{token}` - Удаление файла

## Примеры использования

### Загрузка файла через API

```bash
curl -X POST "http://localhost:18000/api/files/upload" \
  -F "file=@example.txt" \
  -F "password=secret123" \
  -F "expires_days=7" \
  -F "max_downloads=10"
```

### Получение информации о файле

```bash
curl "http://localhost:18000/api/files/info/{token}"
```

### Скачивание файла

```bash
curl "http://localhost:18000/api/files/download/{token}?password=secret123" \
  -o downloaded_file.txt
```

## Взаимодействие микросервисов

Web Service взаимодействует с File Service через HTTP API используя `httpx`:

1. Пользователь загружает файл через веб-форму
2. Web Service получает файл и отправляет его в File Service через `POST /api/files/upload`
3. File Service сохраняет файл и возвращает метаданные
4. Web Service отображает ссылку пользователю
5. При скачивании Web Service перенаправляет на File Service API

## База данных

Используется SQLite с одной таблицей `files`:

- `id` - уникальный идентификатор
- `filename` - оригинальное имя файла
- `stored_name` - имя файла на диске
- `token` - уникальный токен для доступа
- `password` - опциональный пароль
- `expires_at` - срок действия
- `max_downloads` - лимит скачиваний
- `downloads_count` - текущее количество скачиваний
- `created_at` - дата создания
- `user_id` - идентификатор пользователя (для личного кабинета)

## Развитие проекта

Возможные улучшения:

- [ ] Аутентификация пользователей
- [ ] Регистрация и авторизация
- [ ] Поддержка нескольких файлов в одном пакете
- [ ] Статистика и аналитика
- [ ] Уведомления по email
- [ ] Поддержка облачного хранилища (S3)
- [ ] Rate limiting
- [ ] Логирование и мониторинг

## Лицензия

Учебный проект для демонстрации микросервисной архитектуры.

