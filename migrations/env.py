from dotenv import load_dotenv
load_dotenv()

import os
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

# Safe sync URL (avoid turning psycopg2 -> psycopg22)
url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@db:5432/market_edge",
)
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

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
