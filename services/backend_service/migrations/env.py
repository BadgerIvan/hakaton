from alembic import context
from sqlalchemy import create_engine, pool
from app.config import Settings
from app.database import Base

config = context.config
url = config.attributes.get('database_url') or Settings().database_url
options = dict(target_metadata=Base.metadata, version_table='backend_schema_version')
if context.is_offline_mode():
    context.configure(url=url, literal_binds=True, **options)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url, poolclass=pool.NullPool).connect() as connection:
        context.configure(connection=connection, **options)
        with context.begin_transaction():
            context.run_migrations()
