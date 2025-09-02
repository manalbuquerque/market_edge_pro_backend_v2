# migrations/env.py
from __future__ import annotations
import os, time
from dotenv import load_dotenv
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError

load_dotenv()
config = context.config

# Default URL: use 'db' host in Docker, 127.0.0.1 locally
in_docker = bool(os.path.exists("/.dockerenv")) or os.getenv("IN_DOCKER")
default_url = (
    "postgresql+psycopg2://postgres:postgres@db:5432/market_edge"
    if in_docker else
    "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/market_edge"
)

url = os.getenv("DATABASE_URL", default_url)

# Force sync driver for Alembic
if "+asyncpg" in url:
    url = url.replace("+asyncpg", "+psycopg2")
elif "+psycopg" in url and "+psycopg2" not in url:
    url = url.replace("+psycopg", "+psycopg2")

config.set_main_option("sqlalchemy.url", url)
target_metadata = None

def run_migrations_offline():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def _connect_with_retries(cfg, attempts=20, delay=1.0):
    last = None
    for _ in range(attempts):
        try:
            return engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool).connect()
        except OperationalError as e:
            last = e
            time.sleep(delay)
    raise last

def run_migrations_online():
    connectable = _connect_with_retries(config.get_section(config.config_ini_section))
    with connectable:
        context.configure(connection=connectable)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
