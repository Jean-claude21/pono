"""Projects: connections, connection events, projects, environments, deployments.

Revision ID: 0002_projects
Revises: 0001_identity
Create Date: 2026-09-23

Row-level security is enabled and forced here, in the creating migration (constitution VI).
Every reference between organization-owned rows is a composite key that includes the
organization: a foreign key check ignores RLS, so this is what stops a row from pointing at another
organization's row even when its identifier is known.
"""

from alembic import op

revision = "0002_projects"
down_revision = "0001_identity"
branch_labels = None
depends_on = None

ORGANIZATION_TABLES = (
    "connections",
    "connection_events",
    "projects",
    "environments",
    "deployments",
)


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
    CREATE TABLE connections (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
      kind text NOT NULL CHECK (kind IN ('code_host', 'hosting', 'database')),
      provider text NOT NULL,
      external_ref text NOT NULL,
      endpoint text,
      secret_ciphertext bytea,
      status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'revoked')),
      status_checked_at timestamptz NOT NULL DEFAULT now(),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (organization_id, provider, external_ref),
      UNIQUE (organization_id, id)
    )
    """,
    *_protect("connections"),
    """
    CREATE TABLE connection_events (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      connection_id uuid NOT NULL,
      action text NOT NULL,
      occurred_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY (organization_id, connection_id)
        REFERENCES connections (organization_id, id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX connection_events_by_connection "
    "ON connection_events (connection_id, occurred_at)",
    *_protect("connection_events"),
    """
    CREATE TABLE projects (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
      code_connection_id uuid NOT NULL,
      repository text NOT NULL,
      name text NOT NULL,
      default_branch text NOT NULL,
      manifest jsonb NOT NULL,
      manifest_status text NOT NULL CHECK (manifest_status IN ('present', 'proposed', 'absent')),
      manifest_proposal_url text,
      database_status text CHECK (database_status IN ('found', 'missing', 'unknown')),
      state text NOT NULL DEFAULT 'healthy'
        CHECK (state IN ('healthy', 'active', 'warning', 'failing', 'idle')),
      state_reason text NOT NULL DEFAULT 'nominal',
      last_activity_at timestamptz,
      refreshed_at timestamptz,
      stale boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (organization_id, id),
      FOREIGN KEY (organization_id, code_connection_id)
        REFERENCES connections (organization_id, id)
    )
    """,
    # FR-017: a repository is imported once per organization, whatever its letter case.
    "CREATE UNIQUE INDEX projects_repository_once ON projects (organization_id, lower(repository))",
    *_protect("projects"),
    """
    CREATE TABLE environments (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      kind text NOT NULL CHECK (kind IN ('production', 'preview', 'development')),
      branch text,
      hosting_provider text,
      hosting_connection_id uuid,
      external_ref text NOT NULL,
      url text,
      resource_status text NOT NULL DEFAULT 'unknown'
        CHECK (resource_status IN ('found', 'missing', 'unknown')),
      link_status text NOT NULL DEFAULT 'unknown'
        CHECK (link_status IN ('up', 'down', 'unknown', 'missing')),
      link_checked_at timestamptz,
      opened_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (organization_id, id),
      UNIQUE (project_id, kind, external_ref),
      FOREIGN KEY (organization_id, project_id)
        REFERENCES projects (organization_id, id) ON DELETE CASCADE,
      FOREIGN KEY (organization_id, hosting_connection_id)
        REFERENCES connections (organization_id, id) ON DELETE SET NULL (hosting_connection_id)
    )
    """,
    *_protect("environments"),
    """
    CREATE TABLE deployments (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      environment_id uuid NOT NULL,
      external_ref text NOT NULL,
      status text NOT NULL CHECK (status IN ('building', 'succeeded', 'failed', 'cancelled')),
      commit_sha text,
      author text,
      started_at timestamptz NOT NULL,
      finished_at timestamptz,
      UNIQUE (environment_id, external_ref),
      FOREIGN KEY (organization_id, environment_id)
        REFERENCES environments (organization_id, id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX deployments_latest ON deployments (environment_id, started_at DESC)",
    *_protect("deployments"),
    # The worker reads every organization once per tick, then works inside each one under RLS.
    # It learns identifiers only, never a row.
    """
    CREATE FUNCTION pono_worker_organizations()
    RETURNS SETOF uuid
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
      SELECT id FROM organizations ORDER BY id
    $$
    """,
    "REVOKE ALL ON FUNCTION pono_worker_organizations() FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION pono_worker_organizations() TO pono_app",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON " + ", ".join(ORGANIZATION_TABLES) + " TO pono_app",
]

DOWNGRADE = [
    "DROP FUNCTION IF EXISTS pono_worker_organizations()",
    "DROP TABLE IF EXISTS deployments",
    "DROP TABLE IF EXISTS environments",
    "DROP TABLE IF EXISTS projects",
    "DROP TABLE IF EXISTS connection_events",
    "DROP TABLE IF EXISTS connections",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
