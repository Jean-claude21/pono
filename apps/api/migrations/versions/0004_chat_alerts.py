"""Chat alerts: the chat a person links, and delivery of alerts to it (D-015).

Revision ID: 0004_chat_alerts
Revises: 0003_quotas
Create Date: 2026-09-23

No new table: `people` and `alerts` keep the row-level security set by their creating migrations.
Only the digest of a linking code is stored, never the code itself.
"""

from alembic import op

revision = "0004_chat_alerts"
down_revision = "0003_quotas"
branch_labels = None
depends_on = None

RECIPIENTS = """
    CREATE FUNCTION pono_alert_recipients(p_organization_id uuid)
    RETURNS TABLE (email text, chat_id text, locale text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
      SELECT p.email, p.chat_id, p.locale
      FROM memberships m JOIN people p ON p.id = m.person_id
      WHERE m.organization_id = p_organization_id
        AND p_organization_id = ANY (pono_current_organizations())
        AND (p.email IS NOT NULL OR p.chat_id IS NOT NULL)
    $$
"""

EMAIL_ONLY_RECIPIENTS = """
    CREATE FUNCTION pono_alert_recipients(p_organization_id uuid)
    RETURNS TABLE (email text, locale text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
      SELECT p.email, p.locale
      FROM memberships m JOIN people p ON p.id = m.person_id
      WHERE m.organization_id = p_organization_id
        AND p_organization_id = ANY (pono_current_organizations())
        AND p.email IS NOT NULL
    $$
"""

GRANTS = [
    "REVOKE ALL ON FUNCTION pono_alert_recipients(uuid) FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION pono_alert_recipients(uuid) TO pono_app",
]

UPGRADE = [
    "ALTER TABLE people ADD COLUMN chat_id text",
    "ALTER TABLE people ADD COLUMN chat_link_digest bytea",
    "ALTER TABLE people ADD COLUMN chat_link_expires_at timestamptz",
    "ALTER TABLE alerts ADD COLUMN chat_sent_at timestamptz",
    # The return type changes, so the function is dropped and created again, not replaced.
    "DROP FUNCTION pono_alert_recipients(uuid)",
    RECIPIENTS,
    *GRANTS,
]

DOWNGRADE = [
    "DROP FUNCTION pono_alert_recipients(uuid)",
    EMAIL_ONLY_RECIPIENTS,
    *GRANTS,
    "ALTER TABLE alerts DROP COLUMN chat_sent_at",
    "ALTER TABLE people DROP COLUMN chat_link_expires_at",
    "ALTER TABLE people DROP COLUMN chat_link_digest",
    "ALTER TABLE people DROP COLUMN chat_id",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
