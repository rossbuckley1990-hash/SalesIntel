"""SalesIntel 2.0 commercial memory: accounts, links, sites, contacts, drafts, activities,
tasks, deal records, saved views, preferences and aggregate funnel events. Additive only.

Revision ID: 0019_salesintel_crm
Revises: 0018_prospects
"""
from alembic import op
import sqlalchemy as sa

revision = '0019_salesintel_crm'
down_revision = '0018_prospects'
branch_labels = None
depends_on = None

TS = lambda name, nullable=False: sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)  # noqa: E731
ACCOUNT = lambda: sa.Column('account_id', sa.Integer(), sa.ForeignKey('si_accounts.id', ondelete='CASCADE'), nullable=False, index=True)  # noqa: E731


def upgrade():
    op.create_table('si_accounts', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key', sa.String(255), nullable=False, index=True), sa.Column('kind', sa.String(24), nullable=False),
        sa.Column('company_number', sa.String(16), unique=True), sa.Column('website', sa.String(512)), sa.Column('sector', sa.String(160)),
        sa.Column('region', sa.String(160)), sa.Column('status', sa.String(24), nullable=False), sa.Column('watched', sa.Boolean(), nullable=False),
        TS('watched_seen_at', True), sa.Column('notes', sa.Text(), nullable=False), TS('created_at'), TS('updated_at'))
    op.create_table('si_account_links', sa.Column('id', sa.Integer(), primary_key=True), ACCOUNT(),
        sa.Column('entity_type', sa.String(32), nullable=False), sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('name_seen', sa.String(255), nullable=False), sa.Column('basis', sa.String(32), nullable=False),
        sa.Column('confirmed', sa.Boolean(), nullable=False), TS('created_at'),
        sa.UniqueConstraint('entity_type', 'entity_id', name='uq_si_account_link_entity'))
    op.create_table('si_sites', sa.Column('id', sa.Integer(), primary_key=True), ACCOUNT(), sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.Text(), nullable=False), sa.Column('postcode', sa.String(12)), sa.Column('uprn', sa.String(20)),
        sa.Column('basis', sa.String(24), nullable=False), sa.Column('source_url', sa.Text()), sa.Column('systems', sa.JSON(), nullable=False), TS('created_at'))
    op.create_table('si_contacts', sa.Column('id', sa.Integer(), primary_key=True), ACCOUNT(), sa.Column('name', sa.String(180)),
        sa.Column('role', sa.String(240), nullable=False), sa.Column('email', sa.String(255)), sa.Column('phone', sa.String(40)),
        sa.Column('label', sa.String(160), nullable=False), sa.Column('basis', sa.String(24), nullable=False), sa.Column('source_url', sa.Text()),
        sa.Column('source_quote', sa.Text()), sa.Column('status', sa.String(24), nullable=False), sa.Column('influence', sa.String(24), nullable=False),
        TS('created_at'), TS('updated_at'))
    op.create_table('si_drafts', sa.Column('id', sa.Integer(), primary_key=True), ACCOUNT(), sa.Column('deal_id', sa.Integer()),
        sa.Column('contact_id', sa.Integer()), sa.Column('channel', sa.String(16), nullable=False), sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False), sa.Column('evidence', sa.JSON(), nullable=False), sa.Column('gaps', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False), TS('approved_at', True), TS('created_at'), TS('updated_at'))
    op.create_table('si_activities', sa.Column('id', sa.Integer(), primary_key=True), ACCOUNT(), sa.Column('deal_id', sa.Integer(), index=True),
        sa.Column('contact_id', sa.Integer()), sa.Column('draft_id', sa.Integer()), sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('direction', sa.String(12), nullable=False), sa.Column('summary', sa.Text(), nullable=False), sa.Column('outcome', sa.String(32), nullable=False),
        sa.Column('requirements', sa.Text(), nullable=False), sa.Column('objections', sa.Text(), nullable=False), sa.Column('commitments', sa.Text(), nullable=False),
        TS('occurred_at'), TS('created_at'))
    op.create_table('si_tasks', sa.Column('id', sa.Integer(), primary_key=True), ACCOUNT(), sa.Column('deal_id', sa.Integer()),
        sa.Column('activity_id', sa.Integer()), sa.Column('title', sa.String(255), nullable=False), sa.Column('due_on', sa.Date(), nullable=False, index=True),
        sa.Column('status', sa.String(12), nullable=False), TS('done_at', True), TS('created_at'))
    op.create_table('si_deals', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('opportunity_id', sa.Integer(), nullable=False, unique=True), ACCOUNT(),
        sa.Column('title', sa.String(255), nullable=False), sa.Column('stage', sa.String(24), nullable=False), sa.Column('origin_type', sa.String(32)),
        sa.Column('origin_id', sa.Integer()), sa.Column('origin', sa.JSON(), nullable=False), sa.Column('services', sa.JSON(), nullable=False),
        sa.Column('work_type', sa.String(32), nullable=False), sa.Column('qualification', sa.JSON(), nullable=False), sa.Column('value_annual', sa.Float()),
        sa.Column('value_total', sa.Float()), sa.Column('value_basis', sa.String(24), nullable=False), sa.Column('next_step', sa.Text(), nullable=False),
        sa.Column('scope', sa.JSON(), nullable=False), sa.Column('quote', sa.JSON(), nullable=False), sa.Column('handover', sa.JSON(), nullable=False),
        sa.Column('outcome_reason', sa.Text(), nullable=False), TS('created_at'), TS('updated_at'))
    op.create_table('si_saved_views', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('name', sa.String(120), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=False), TS('created_at'))
    op.create_table('si_preferences', sa.Column('key', sa.String(64), primary_key=True), sa.Column('value', sa.JSON(), nullable=False))
    op.create_table('si_funnel_events', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('event', sa.String(48), nullable=False, index=True),
        sa.Column('day', sa.Date(), nullable=False, index=True))


def downgrade():
    for name in ('si_funnel_events', 'si_preferences', 'si_saved_views', 'si_deals', 'si_tasks', 'si_activities', 'si_drafts', 'si_contacts',
                 'si_sites', 'si_account_links', 'si_accounts'):
        op.drop_table(name)
