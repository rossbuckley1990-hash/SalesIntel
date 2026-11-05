"""Workspaces, people and tenant isolation.

Adds organisations, users (identities from a managed provider; no passwords), memberships
with roles, invitations, the workspace audit log and per-workspace lead review. Every
private commercial record gains a required ``organisation_id``. Existing records are
assigned to the local workspace (id 1), so a single-user install keeps all of its data.

Uniqueness that used to be global becomes per workspace, so two companies can both track
the same organisation or public notice without either learning the other does.

Downgrade refuses once any workspace other than the local one exists, because collapsing
several companies' records into one schema would mix them.

Revision ID: 0020_workspaces_and_tenancy
Revises: 0019_salesintel_crm
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = '0020_workspaces_and_tenancy'
down_revision = '0019_salesintel_crm'
branch_labels = None
depends_on = None

LOCAL_ORG_ID = 1
TENANT_TABLES = ('si_accounts', 'si_account_links', 'si_sites', 'si_contacts', 'si_drafts', 'si_activities', 'si_tasks', 'si_deals',
                 'si_saved_views', 'si_funnel_events', 'prospects', 'prospect_searches')
NAMING = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}
TS = lambda name, nullable=False: sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)  # noqa: E731
ORG = lambda: sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), nullable=False, index=True)  # noqa: E731


def _sqlite() -> bool:
    return op.get_bind().dialect.name == 'sqlite'


def _drop_single_column_unique(table: str, column: str) -> None:
    """Drop an unnamed UNIQUE(column) created by an earlier migration, on SQLite or PostgreSQL."""
    if _sqlite():
        with op.batch_alter_table(table, naming_convention=NAMING) as batch:
            batch.drop_constraint(f'uq_{table}_{column}', type_='unique')
        return
    for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table):
        if constraint['column_names'] == [column]:
            op.drop_constraint(constraint['name'], table, type_='unique')


def upgrade():
    op.create_table('organisations', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('name', sa.String(160), nullable=False),
                    sa.Column('slug', sa.String(80), nullable=False, unique=True), sa.Column('industry', sa.String(48), nullable=False), TS('created_at'))
    op.create_table('users', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('issuer', sa.String(255), nullable=False),
                    sa.Column('subject', sa.String(255), nullable=False), sa.Column('email', sa.String(255), nullable=False, index=True),
                    sa.Column('email_verified', sa.Boolean(), nullable=False), sa.Column('name', sa.String(160), nullable=False),
                    TS('created_at'), TS('last_seen_at'), sa.UniqueConstraint('issuer', 'subject', name='uq_users_identity'))
    op.create_table('memberships', sa.Column('id', sa.Integer(), primary_key=True), ORG(),
                    sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
                    sa.Column('role', sa.String(24), nullable=False), sa.Column('territory', sa.JSON(), nullable=False),
                    sa.Column('services', sa.JSON(), nullable=False), sa.Column('target_amount', sa.String(24)),
                    sa.Column('target_basis', sa.String(24)), sa.Column('target_period', sa.String(16)), TS('created_at'),
                    sa.UniqueConstraint('organisation_id', 'user_id', name='uq_membership'))
    op.create_table('invitations', sa.Column('id', sa.Integer(), primary_key=True), ORG(), sa.Column('email', sa.String(255), nullable=False),
                    sa.Column('role', sa.String(24), nullable=False), sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
                    sa.Column('invited_by', sa.Integer(), nullable=False), sa.Column('status', sa.String(12), nullable=False),
                    TS('expires_at'), TS('created_at'))
    op.create_table('si_audit_events', sa.Column('id', sa.Integer(), primary_key=True), ORG(), sa.Column('user_id', sa.Integer(), index=True),
                    sa.Column('action', sa.String(12), nullable=False), sa.Column('entity_type', sa.String(48), nullable=False),
                    sa.Column('entity_id', sa.Integer()), sa.Column('fields', sa.JSON(), nullable=False), sa.Column('detail', sa.JSON(), nullable=False),
                    sa.Column('at', sa.DateTime(timezone=True), nullable=False, index=True))
    op.create_table('si_lead_states', sa.Column('id', sa.Integer(), primary_key=True), ORG(), sa.Column('entity_type', sa.String(32), nullable=False),
                    sa.Column('entity_id', sa.Integer(), nullable=False), sa.Column('status', sa.String(16), nullable=False), TS('updated_at'),
                    sa.Column('updated_by', sa.Integer()), sa.UniqueConstraint('organisation_id', 'entity_type', 'entity_id', name='uq_si_lead_state'))

    organisations = sa.table('organisations', sa.column('id', sa.Integer()), sa.column('name', sa.String()), sa.column('slug', sa.String()),
                             sa.column('industry', sa.String()), sa.column('created_at', sa.DateTime(timezone=True)))
    op.bulk_insert(organisations, [{'id': LOCAL_ORG_ID, 'name': 'Local workspace', 'slug': 'local', 'industry': 'fire_and_security',
                                    'created_at': datetime(2026, 1, 1)}])
    if not _sqlite():
        op.execute("SELECT setval(pg_get_serial_sequence('organisations', 'id'), (SELECT MAX(id) FROM organisations))")

    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('organisation_id', sa.Integer(), nullable=True))
        op.execute(sa.text(f'UPDATE {table} SET organisation_id = :org').bindparams(org=LOCAL_ORG_ID))
        with op.batch_alter_table(table) as batch:
            batch.alter_column('organisation_id', existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(f'fk_{table}_organisation', 'organisations', ['organisation_id'], ['id'], ondelete='CASCADE')
            batch.create_index(f'ix_{table}_organisation_id', ['organisation_id'])

    # Uniqueness per workspace, not across every company.
    _drop_single_column_unique('si_accounts', 'company_number')
    _drop_single_column_unique('prospects', 'dedup_key')
    with op.batch_alter_table('si_accounts') as batch:
        batch.create_unique_constraint('uq_si_account_company', ['organisation_id', 'company_number'])
        batch.add_column(sa.Column('owner_user_id', sa.Integer()))
        batch.create_index('ix_si_accounts_owner_user_id', ['owner_user_id'])
    with op.batch_alter_table('prospects') as batch:
        batch.create_unique_constraint('uq_prospects_dedup', ['organisation_id', 'dedup_key'])
    with op.batch_alter_table('si_account_links') as batch:
        batch.drop_constraint('uq_si_account_link_entity', type_='unique')
        batch.create_unique_constraint('uq_si_account_link_entity', ['organisation_id', 'entity_type', 'entity_id'])
    with op.batch_alter_table('si_deals') as batch:
        batch.alter_column('opportunity_id', existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column('owner_user_id', sa.Integer()))
        batch.add_column(sa.Column('seller_confidence', sa.String(12)))
        batch.create_index('ix_si_deals_owner_user_id', ['owner_user_id'])
    with op.batch_alter_table('si_tasks') as batch:
        batch.add_column(sa.Column('assignee_user_id', sa.Integer()))
        batch.create_index('ix_si_tasks_assignee_user_id', ['assignee_user_id'])

    # Preferences become per workspace: the key alone is no longer the identity.
    op.create_table('si_preferences_new', sa.Column('organisation_id', sa.Integer(), sa.ForeignKey('organisations.id', ondelete='CASCADE'), primary_key=True),
                    sa.Column('key', sa.String(64), primary_key=True), sa.Column('value', sa.JSON(), nullable=False))
    op.execute(sa.text('INSERT INTO si_preferences_new (organisation_id, key, value) SELECT :org, key, value FROM si_preferences').bindparams(org=LOCAL_ORG_ID))
    op.drop_table('si_preferences')
    op.rename_table('si_preferences_new', 'si_preferences')


def downgrade():
    bind = op.get_bind()
    others = bind.execute(sa.text('SELECT COUNT(*) FROM organisations WHERE id <> :org').bindparams(org=LOCAL_ORG_ID)).scalar()
    for table in TENANT_TABLES + ('si_preferences',):  # rows can outlive their workspace where foreign keys are not enforced
        others += bind.execute(sa.text(f'SELECT COUNT(*) FROM {table} WHERE organisation_id <> :org').bindparams(org=LOCAL_ORG_ID)).scalar()
    if others:
        raise RuntimeError('Refusing to downgrade: other workspaces exist and their records would be mixed into one schema.')
    op.create_table('si_preferences_old', sa.Column('key', sa.String(64), primary_key=True), sa.Column('value', sa.JSON(), nullable=False))
    op.execute('INSERT INTO si_preferences_old (key, value) SELECT key, value FROM si_preferences')
    op.drop_table('si_preferences')
    op.rename_table('si_preferences_old', 'si_preferences')
    with op.batch_alter_table('si_tasks') as batch:
        batch.drop_index('ix_si_tasks_assignee_user_id')
        batch.drop_column('assignee_user_id')
    with op.batch_alter_table('si_deals') as batch:
        batch.drop_index('ix_si_deals_owner_user_id')
        batch.drop_column('seller_confidence')
        batch.drop_column('owner_user_id')
        batch.alter_column('opportunity_id', existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table('si_account_links') as batch:
        batch.drop_constraint('uq_si_account_link_entity', type_='unique')
        batch.create_unique_constraint('uq_si_account_link_entity', ['entity_type', 'entity_id'])
    with op.batch_alter_table('prospects') as batch:
        batch.drop_constraint('uq_prospects_dedup', type_='unique')
        batch.create_unique_constraint('uq_prospects_dedup_key', ['dedup_key'])
    with op.batch_alter_table('si_accounts') as batch:
        batch.drop_index('ix_si_accounts_owner_user_id')
        batch.drop_column('owner_user_id')
        batch.drop_constraint('uq_si_account_company', type_='unique')
        batch.create_unique_constraint('uq_si_accounts_company_number', ['company_number'])
    for table in TENANT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f'ix_{table}_organisation_id')
            batch.drop_constraint(f'fk_{table}_organisation', type_='foreignkey')
            batch.drop_column('organisation_id')
    for table in ('si_lead_states', 'si_audit_events', 'invitations', 'memberships', 'users', 'organisations'):
        op.drop_table(table)
