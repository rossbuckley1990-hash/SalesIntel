from alembic import context
from app.db import Base, create_database_engine
import app.models  # register schemas

config = context.config
if context.is_offline_mode():
    raise RuntimeError("Use an explicit database connection for migration validation.")
else:
    engine = create_database_engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()
