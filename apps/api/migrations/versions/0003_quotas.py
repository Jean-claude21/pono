"""Quotas: readings and alerts.

Revision ID: 0003_quotas
Revises: 0002_projects
Create Date: 2026-09-23

Row-level security is enabled and forced here, in the creating migration (constitution VI).
An alert is unique per resource, metric, threshold and billing period (FR-025): the database,
not the code, guarantees it is never raised twice.
"""

from alembic import op

revision = "0003_quotas"
down_revision = "0002_projects"
branch_labels = None
depends_on = None

NO_PROJECT = "'00000000-0000-0000-0000-000000000000'::uuid"


def _protect(table: str) -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"""
        CREATE POLICY {table}_member ON {table}
          USING (organization_id = ANY (pono_current_organizations()))
          WITH CHECK (organization_id = ANY (pono_current_organizations()))
        """,
    ]


UPGRADE = [
    """
    CREATE TABLE quota_readings (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      project_id uuid,
      connection_id uuid NOT NULL,
      metric text NOT NULL,
      used numeric NOT NULL,
      "limit" numeric,
      limit_source text NOT NULL CHECK (limit_source IN ('account_plan', 'free_tier_estimate')),
      period_start date NOT NULL,
      period_end date,
      read_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY (organization_id, project_id)
        REFERENCES projects (organization_id, id) ON DELETE CASCADE,
      FOREIGN KEY (organization_id, connection_id)
        REFERENCES connections (organization_id, id) ON DELETE CASCADE
    )
    """,
    # The latest reading per resource, metric and period: a new reading replaces it.
    "CREATE UNIQUE INDEX quota_readings_latest ON quota_readings "
    f"(connection_id, COALESCE(project_id, {NO_PROJECT}), metric, period_start)",
    *_protect("quota_readings"),
    """
    CREATE TABLE alerts (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      project_id uuid,
      connection_id uuid NOT NULL,
      metric text NOT NULL,
      threshold smallint NOT NULL CHECK (threshold IN (80, 95)),
      ratio numeric NOT NULL,
      period_start date NOT NULL,
      raised_at timestamptz NOT NULL DEFAULT now(),
      emailed_at timestamptz,
      FOREIGN KEY (organization_id, project_id)
        REFERENCES projects (organization_id, id) ON DELETE CASCADE,
      FOREIGN KEY (organization_id, connection_id)
        REFERENCES connections (organization_id, id) ON DELETE CASCADE
    )
    """,
    "CREATE UNIQUE INDEX alerts_once_per_period ON alerts "
    f"(organization_id, connection_id, COALESCE(project_id, {NO_PROJECT}), metric, threshold, "
    "period_start)",
    *_protect("alerts"),
    # Alert emails go to the organization's members. The worker acts for an organization, not a
    # person, so it cannot read people; this lookup answers only for the organization it acts for.
    """
    CREATE FUNCTION pono_alert_recipients(p_organization_id uuid)
    RETURNS TABLE (email text, locale text)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
      SELECT p.email, p.locale
      FROM memberships m JOIN people p ON p.id = m.person_id
      WHERE m.organization_id = p_organization_id
        AND p_organization_id = ANY (pono_current_organizations())
        AND p.email IS NOT NULL
    $$
    """,
    "REVOKE ALL ON FUNCTION pono_alert_recipients(uuid) FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION pono_alert_recipients(uuid) TO pono_app",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON quota_readings, alerts TO pono_app",
]

DOWNGRADE = [
    "DROP FUNCTION IF EXISTS pono_alert_recipients(uuid)",
    "DROP TABLE IF EXISTS alerts",
    "DROP TABLE IF EXISTS quota_readings",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
