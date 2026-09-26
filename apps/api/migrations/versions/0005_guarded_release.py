"""Guarded release: release attempts, guard results, approvals, rollbacks, the evidence journal.

Revision ID: 0005_guarded_release
Revises: 0004_chat_alerts
Create Date: 2026-09-23

Row-level security is enabled and forced here, in the creating migration, for every table
(constitution VI). The journal is append-only twice over: the app role is granted no UPDATE or
DELETE, and a trigger refuses both for every role, the owner included (002 research R-09).
"""

from alembic import op

revision = "0005_guarded_release"
down_revision = "0004_chat_alerts"
branch_labels = None
depends_on = None

TABLES = ("releases", "release_checks", "release_approvals", "rollbacks", "project_events")


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
    "ALTER TABLE projects ADD COLUMN protection_status text NOT NULL DEFAULT 'unknown' "
    "CHECK (protection_status IN ('protected', 'unprotected', 'unavailable_on_plan', 'unknown'))",
    "ALTER TABLE projects ADD COLUMN protection_checked_at timestamptz",
    """
    CREATE TABLE releases (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      change_number integer NOT NULL,
      change_url text NOT NULL,
      title text NOT NULL,
      author text NOT NULL,
      head_sha text NOT NULL,
      head_branch text,
      head_seen_at timestamptz NOT NULL DEFAULT now(),
      reported_check text CHECK (reported_check IN ('pending', 'failure', 'success')),
      verdict text NOT NULL DEFAULT 'evaluating'
        CHECK (verdict IN ('evaluating', 'refused', 'awaiting_approval', 'approved')),
      state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'merged', 'closed')),
      opened_at timestamptz NOT NULL DEFAULT now(),
      evaluated_at timestamptz,
      closed_at timestamptz,
      UNIQUE (organization_id, id),
      UNIQUE (project_id, change_number),
      FOREIGN KEY (organization_id, project_id)
        REFERENCES projects (organization_id, id) ON DELETE CASCADE
    )
    """,
    *_protect("releases"),
    """
    CREATE TABLE release_checks (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      release_id uuid NOT NULL,
      head_sha text NOT NULL,
      guard text NOT NULL CHECK (guard IN ('secrets', 'migrations', 'preview')),
      status text NOT NULL CHECK (status IN ('pending', 'passed', 'failed')),
      reason text,
      findings jsonb NOT NULL DEFAULT '[]'::jsonb,
      checked_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (release_id, head_sha, guard),
      FOREIGN KEY (organization_id, release_id)
        REFERENCES releases (organization_id, id) ON DELETE CASCADE
    )
    """,
    *_protect("release_checks"),
    """
    CREATE TABLE release_approvals (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      release_id uuid NOT NULL,
      head_sha text NOT NULL,
      person_id uuid NOT NULL REFERENCES people (id),
      approved_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (release_id, head_sha),
      FOREIGN KEY (organization_id, release_id)
        REFERENCES releases (organization_id, id) ON DELETE CASCADE
    )
    """,
    *_protect("release_approvals"),
    """
    CREATE TABLE rollbacks (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      environment_id uuid NOT NULL,
      from_ref text,
      to_ref text NOT NULL,
      to_commit text,
      requested_by uuid NOT NULL REFERENCES people (id),
      status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'succeeded', 'failed')),
      requested_at timestamptz NOT NULL DEFAULT now(),
      finished_at timestamptz,
      FOREIGN KEY (organization_id, project_id)
        REFERENCES projects (organization_id, id) ON DELETE CASCADE,
      FOREIGN KEY (organization_id, environment_id)
        REFERENCES environments (organization_id, id) ON DELETE CASCADE
    )
    """,
    *_protect("rollbacks"),
    """
    CREATE TABLE project_events (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      occurred_at timestamptz NOT NULL DEFAULT now(),
      kind text NOT NULL,
      actor_kind text NOT NULL CHECK (actor_kind IN ('person', 'agent', 'pono')),
      actor text,
      release_id uuid,
      head_sha text,
      detail jsonb NOT NULL DEFAULT '{}'::jsonb,
      FOREIGN KEY (organization_id, project_id) REFERENCES projects (organization_id, id)
    )
    """,
    "CREATE INDEX project_events_by_project ON project_events (project_id, id DESC)",
    *_protect("project_events"),
    """
    CREATE FUNCTION pono_journal_is_append_only() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'the evidence journal is append-only'
        USING ERRCODE = 'insufficient_privilege';
    END
    $$
    """,
    """
    CREATE TRIGGER project_events_append_only
      BEFORE UPDATE OR DELETE ON project_events
      FOR EACH ROW EXECUTE FUNCTION pono_journal_is_append_only()
    """,
    "GRANT SELECT, INSERT, UPDATE ON releases, release_checks, rollbacks TO pono_app",
    "GRANT SELECT, INSERT ON release_approvals, project_events TO pono_app",
]

DOWNGRADE = [
    "DROP TABLE IF EXISTS project_events",
    "DROP FUNCTION IF EXISTS pono_journal_is_append_only()",
    "DROP TABLE IF EXISTS rollbacks",
    "DROP TABLE IF EXISTS release_approvals",
    "DROP TABLE IF EXISTS release_checks",
    "DROP TABLE IF EXISTS releases",
    "ALTER TABLE projects DROP COLUMN IF EXISTS protection_checked_at",
    "ALTER TABLE projects DROP COLUMN IF EXISTS protection_status",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
