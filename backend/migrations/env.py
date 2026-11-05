from alembic import context
from app.db import Base, create_database_engine
import app.models  # register schemas

config = context.config
if context.is_offline_mode():
    raise RuntimeError("Use an explicit database connection for migration validation.")
else:
    engine = create_database_engine()
    with engine.connect() as connection:
        if connection.dialect.name == "postgresql":  # migrations are trusted system work beneath row-level security
            from sqlalchemy import text
            connection.execute(text("SELECT set_config('salesintel.bypass', 'on', false)"))
            connection.commit()
        context.configure(
            connection=connection, target_metadata=Base.metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()
