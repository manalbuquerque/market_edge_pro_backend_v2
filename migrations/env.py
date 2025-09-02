# migrations/env.py
from __future__ import annotations

import os
import time
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Optional: load .env if present (useful for local dev)
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):  # fallback no-op
        return False

load_dotenv()

# Alembic Config object, provides access to the .ini values
config = context.config

# If you have metadata to autogenerate, import it here; otherwise keep None
target_metadata = None  # e.g., from myapp.models import Base; target_metadata = Base.metadata


def _normalize_driver(url: str) -> str:
    """
    Force a sync driver (psycopg2) — Alembic env should use sync engines.
    """
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    # Guard for psycopg v3 DSNs ("+psycopg")
    if "+psycopg" in url and "+psycopg2" not in url:
        url = url.replace("+psycopg", "+psycopg2")
    # Guard plain "postgresql://" (let it be — SQLAlchemy maps to psycopg2 by default)
    return url


def _default_db_host() -> str:
    """
    Inside containers, default host should be the Compose service name 'db'.
    Locally, default to 127.0.0.1.
    """
    in_docker = Path("/.dockerenv").exists()
    return "db" if in_docker else "127.0.0.1"


def _compose_url_from_env() -> str:
    user = os.getenv("POSTGRES_USER", "postgres")
    pwd = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("DB_HOST", _default_db_host())
    port = os.getenv("DB_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "market_edge")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"


def _get_database_url() -> str:
    """
    Pick DATABASE_URL if provided, otherwise build it from POSTGRES_* envs.
    Normalize to a sync driver.
    """
    url = os.getenv("DATABASE_URL")
    if not url or url.strip() == "":
        url = _compose_url_from_env()
    return _normalize_driver(url)


# Resolve and inject sqlalchemy.url so Alembic uses it
SQLALCHEMY_URL = _get_database_url()
config.set_main_option("sqlalchemy.url", SQLALCHEMY_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=SQLALCHEMY_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Small retry helper: DB might need a moment to accept connections (especially in CI/Compose).
    max_tries = int(os.getenv("ALEMBIC_CONNECT_RETRIES", "30"))
    wait_s = float(os.getenv("ALEMBIC_CONNECT_WAIT", "1.0"))

    last_exc: Exception | None = None
    for attempt in range(1, max_tries + 1):
        try:
            connectable = engine_from_config(
                config.get_section(config.config_ini_section),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )
            with connectable.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    compare_type=True,
                    compare_server_default=True,
                )
                with context.begin_transaction():
                    context.run_migrations()
            return  # success
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            time.sleep(wait_s)

    # If we got here, all retries failed
    if last_exc:
        raise last_exc


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
