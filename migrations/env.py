from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# Build DATABASE_URL if not provided, defaulting to Docker service "db"
def _default_url() -> str:
    user = os.getenv("POSTGRES_USER", "postgres")
    pwd = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("DB_HOST", "db")  # <— IMPORTANT: container talks to 'db'
    port = os.getenv("DB_PORT", "5432")
    dbn  = os.getenv("POSTGRES_DB", "market_edge")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{dbn}"

url = os.getenv("DATABASE_URL") or _default_url()

# Normalize URL/driver variants
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg2://", 1)
if "+asyncpg" in url:
    url = url.replace("+asyncpg", "+psycopg2")
elif "+psycopg" in url and "+psycopg2" not in url:
    url = url.replace("+psycopg", "+psycopg2")

config.set_main_option("sqlalchemy.url", url)

# Import your models’ metadata here if/when needed
target_metadata = None

def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
