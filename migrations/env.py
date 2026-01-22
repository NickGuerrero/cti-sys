from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from src.database.postgres import models
target_metadata = models.Base.metadata

# map Alembic environment names to DB URLs
DB_URLS = {
    "development": os.getenv("DEV_DATABASE_URL"),
    "production": os.getenv("PROD_DATABASE_URL"),
    "custom": os.getenv("CUSTOM_DATABASE_URL"),
}

def get_url() -> str:
    # Alembic Command line: alembic -x environment=development
    env_name = context.get_x_argument(as_dictionary=True).get("environment") or "development"
    url = DB_URLS.get(env_name)
    if not url:
        raise RuntimeError(f"No database URL configured for environment '{env_name}'")
    return url

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.
from os import environ as env
def env_url():
    return env.get("CTI_POSTGRES_URL")

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # url = config.get_main_option("sqlalchemy.url") -> Refer to the env file/config vars for correct url
    url = env_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
