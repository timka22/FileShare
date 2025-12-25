FROM python:3.11-slim

WORKDIR /app

# Создаем директории для загрузок и БД
RUN mkdir -p /app/uploads /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

