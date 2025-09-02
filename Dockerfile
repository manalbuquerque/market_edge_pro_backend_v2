FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8010
# Sobe migrações e arranca API
CMD ["sh", "-c", "alembic upgrade head || true && uvicorn main1:app --host 0.0.0.0 --port 8010 --workers 2"]
