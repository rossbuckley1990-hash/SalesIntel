"""PostgreSQL row-level security on every tenant table (defence in depth; SQLite is single-user only).

Revision ID: 0022_row_level_security
Revises: 0021_acquisition_engine
"""
from alembic import op
import sqlalchemy as sa

from app.rls import TENANT_TABLES, statements

revision = '0022_row_level_security'
down_revision = '0021_acquisition_engine'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    for sql in statements():
        op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    for t in TENANT_TABLES:
        op.execute(f'DROP POLICY IF EXISTS si_workspace ON {t}')
        op.execute(f'ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {t} DISABLE ROW LEVEL SECURITY')
