from alembic import context
from sqlalchemy import engine_from_config, pool
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    from config import settings
    from database import Base
    import models  # noqa: F401  # registers models with Alembic metadata
    db_url = settings.DATABASE_URL
except ImportError:
    from app.core.config import settings
    from app.models import Base
    db_url = settings.database_url

config = context.config
target_metadata = Base.metadata

# If sqlalchemy.url is set on config (e.g. from run_migrations or cli), use it; otherwise fallback to settings
custom_url = config.get_main_option("sqlalchemy.url")
if not custom_url:
    custom_url = db_url
    config.set_main_option("sqlalchemy.url", custom_url.replace("%", "%%"))
else:
    db_url = custom_url


def run_migrations_offline() -> None:
    context.configure(url=db_url, target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
