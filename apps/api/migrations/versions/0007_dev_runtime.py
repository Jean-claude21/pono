"""Development runtimes: one per project, the writes waiting to be saved, the saved batches.

Revision ID: 0007_dev_runtime
Revises: 0006_agent_access
Create Date: 2026-09-26

Row-level security is enabled and forced here for every table (constitution VI). Each table belongs
to an organization and its foreign keys carry the organization, so no row can point elsewhere.
The token shared with the runtime's gate is stored encrypted; a write's content is erased once it
is saved to the development branch (004 data-model).
"""

from alembic import op

revision = "0007_dev_runtime"
down_revision = "0006_agent_access"
branch_labels = None
depends_on = None


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
    CREATE TABLE runtimes (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      hosting_connection_id uuid NOT NULL,
      state text NOT NULL CHECK (state IN ('awaiting_files', 'preparing', 'starting', 'ready',
        'sleeping', 'stopped', 'failed', 'unreachable')),
      reason text,
      development_branch text NOT NULL,
      proposal_url text,
      external_ref text,
      key_ref text,
      deploy_key_ref text,
      url text,
      token_ciphertext bytea,
      database_host text,
      production_database_host text,
      saved_head text,
      awake boolean NOT NULL DEFAULT false,
      errors jsonb NOT NULL DEFAULT '[]'::jsonb,
      conflicts text[] NOT NULL DEFAULT '{}',
      last_activity_at timestamptz,
      last_status_at timestamptz,
      requested_at timestamptz NOT NULL DEFAULT now(),
      started_at timestamptz,
      stopped_at timestamptz,
      UNIQUE (project_id),
      UNIQUE (organization_id, id),
      FOREIGN KEY (organization_id, project_id)
        REFERENCES projects (organization_id, id) ON DELETE CASCADE,
      FOREIGN KEY (organization_id, hosting_connection_id)
        REFERENCES connections (organization_id, id)
    )
    """,
    *_protect("runtimes"),
    """
    CREATE TABLE runtime_saves (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      runtime_id uuid NOT NULL,
      commit_sha text,
      paths text[] NOT NULL,
      conflicts text[] NOT NULL DEFAULT '{}',
      actor_kind text NOT NULL CHECK (actor_kind IN ('person', 'agent')),
      actor text NOT NULL,
      granted_by text,
      saved_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (organization_id, id),
      FOREIGN KEY (organization_id, runtime_id)
        REFERENCES runtimes (organization_id, id) ON DELETE CASCADE
    )
    """,
    *_protect("runtime_saves"),
    """
    CREATE TABLE runtime_writes (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      runtime_id uuid NOT NULL,
      path text NOT NULL,
      content bytea,
      deleted boolean NOT NULL DEFAULT false,
      actor_kind text NOT NULL CHECK (actor_kind IN ('person', 'agent')),
      actor text NOT NULL,
      granted_by text,
      state text NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'conflict', 'saved', 'superseded')),
      save_id uuid,
      written_at timestamptz NOT NULL DEFAULT now(),
      FOREIGN KEY (organization_id, runtime_id)
        REFERENCES runtimes (organization_id, id) ON DELETE CASCADE,
      FOREIGN KEY (organization_id, save_id) REFERENCES runtime_saves (organization_id, id)
    )
    """,
    "CREATE INDEX runtime_writes_waiting ON runtime_writes (runtime_id, written_at) "
    "WHERE state IN ('pending', 'conflict')",
    *_protect("runtime_writes"),
    "GRANT SELECT, INSERT, UPDATE ON runtimes, runtime_saves, runtime_writes TO pono_app",
]

DOWNGRADE = [
    "DROP TABLE IF EXISTS runtime_writes",
    "DROP TABLE IF EXISTS runtime_saves",
    "DROP TABLE IF EXISTS runtimes",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
