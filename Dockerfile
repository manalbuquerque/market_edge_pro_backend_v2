FROM python:3.13-slim

WORKDIR /app

# system deps for psycopg2 etc.
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# deps (add pandas/numpy so metrics/backtests load)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir "pandas>=2.2" "numpy>=1.26"

# app code + migrations
COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8010

# run migrations then start the v2 app
CMD ["sh","-lc","alembic upgrade head || true && uvicorn app_mep_v2:app --host 0.0.0.0 --port 8010 --workers 2"]
