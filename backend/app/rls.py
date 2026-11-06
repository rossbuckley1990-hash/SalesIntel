"""PostgreSQL row-level security: the database itself refuses rows from another workspace.

This sits beneath the session-level filters in app/tenancy.py. Each tenant table gets one policy:
a row is visible and writable only when its organisation_id equals the transaction-local
setting `salesintel.organisation_id`, which the session sets from the authenticated workspace.
Trusted system work (collectors, the job claimer, migrations) sets `salesintel.bypass = on`.

The application must connect as a role that is neither a superuser nor BYPASSRLS, and FORCE is
used so that even the table owner is subject to the policy. Startup refuses otherwise.
"""
from sqlalchemy import text

TENANT_TABLES = ('si_accounts', 'si_account_links', 'si_sites', 'si_contacts', 'si_drafts', 'si_activities', 'si_tasks', 'si_deals', 'si_saved_views',
                 'si_funnel_events', 'si_preferences', 'si_lead_states', 'prospects', 'prospect_searches', 'si_audit_events', 'si_research_jobs',
                 'si_spend_budgets', 'si_idempotency', 'si_suppressions', 'si_dossiers', 'si_lead_feedback', 'si_gap_requests', 'si_review_decisions',
                 'si_review_adjudications', 'si_review_states', 'atlas_relationships', 'si_brief_reviews')
CONDITION = ("current_setting('salesintel.bypass', true) = 'on' OR "
             "organisation_id = NULLIF(current_setting('salesintel.organisation_id', true), '')::integer")


def statements(tables=TENANT_TABLES) -> list[str]:
    out = []
    for t in tables:
        out += [f'ALTER TABLE {t} ENABLE ROW LEVEL SECURITY', f'ALTER TABLE {t} FORCE ROW LEVEL SECURITY', f'DROP POLICY IF EXISTS si_workspace ON {t}',
                f'CREATE POLICY si_workspace ON {t} USING ({CONDITION}) WITH CHECK ({CONDITION})']
    return out


def enable(connection) -> None:
    if connection.dialect.name != 'postgresql':
        return
    for sql in statements():
        connection.execute(text(sql))


def check_role(connection) -> None:
    """Refuse to serve hosted workspaces through a database role that ignores row-level security."""
    row = connection.execute(text('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user')).one()
    if row[0] or row[1]:
        raise RuntimeError('The application database role bypasses row-level security. Connect as a role without SUPERUSER or BYPASSRLS.')
