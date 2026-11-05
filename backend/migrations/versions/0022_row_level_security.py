"""PostgreSQL row-level security on every tenant table (defence in depth; SQLite is single-user only).

Revision ID: 0022_row_level_security
Revises: 0021_acquisition_engine
"""
from alembic import op
import sqlalchemy as sa

from app.rls import statements

# Frozen at this revision: later migrations add their own tables to row-level security.
TENANT_TABLES = ('si_accounts', 'si_account_links', 'si_sites', 'si_contacts', 'si_drafts', 'si_activities', 'si_tasks', 'si_deals', 'si_saved_views',
                 'si_funnel_events', 'si_preferences', 'si_lead_states', 'prospects', 'prospect_searches', 'si_audit_events', 'si_research_jobs',
                 'si_spend_budgets', 'si_idempotency', 'si_suppressions')

revision = '0022_row_level_security'
down_revision = '0021_acquisition_engine'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    for sql in statements(TENANT_TABLES):
        op.execute(sql)


def downgrade():
    if op.get_bind().dialect.name != 'postgresql':
        return
    for t in TENANT_TABLES:
        op.execute(f'DROP POLICY IF EXISTS si_workspace ON {t}')
        op.execute(f'ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {t} DISABLE ROW LEVEL SECURITY')
