"""Alembic environment.

Pulls the DB URL from app settings (not alembic.ini) so secrets stay in .env,
and points autogenerate at our models' metadata. Run from `backend/`:

    uv run alembic revision --autogenerate -m "message"
    uv run alembic upgrade head
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from core.config import settings
from data.models import Base, Geography

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the real URL from settings (loaded from .env).
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)

target_metadata = Base.metadata

# Tables that belong to Postgres extensions, never to our models. Supabase installs
# PostGIS into the `extensions` schema, but if it ever lands in `public` these must not be
# picked up — autogenerate would otherwise propose dropping them (AGENTS.md guardrail 2).
EXTENSION_TABLES = {
    "spatial_ref_sys",
    "geometry_columns",
    "geography_columns",
    "raster_columns",
    "raster_overviews",
}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name in EXTENSION_TABLES:
        return False
    return True


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    # SQLAlchemy can't reflect PostGIS `geography`, so it would report a change every time.
    if isinstance(metadata_column.type, Geography):
        return False
    return None  # default comparison for everything else


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sqlalchemy_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = settings.sqlalchemy_url
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=compare_type,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
