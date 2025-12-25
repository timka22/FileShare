FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Убеждаемся, что директории существуют
RUN mkdir -p /app/app/templates /app/app/static

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

