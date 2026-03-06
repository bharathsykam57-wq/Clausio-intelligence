"""
Alembic migration environment.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from auth.models import Base as AuthBase
from config import get_settings

settings = get_settings()
config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = AuthBase.metadata

EXCLUDE_TABLES = {"documents", "request_logs"}

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in EXCLUDE_TABLES:
        return False
    return True

def run_migrations_offline():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
