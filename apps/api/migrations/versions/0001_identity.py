"""Identity: people, sessions, organizations, memberships.

Revision ID: 0001_identity
Revises:
Create Date: 2026-09-23

Row-level security is enabled and forced here, in the creating migration (constitution VI).
The only ways around it are two SECURITY DEFINER lookups needed before the person is known:
resolving a session token and finding a person by their code host identity.
"""

from alembic import op

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None

# One statement per entry: asyncpg prepares each statement and refuses multi-command strings.
UPGRADE = [
    """
    CREATE FUNCTION pono_current_person() RETURNS uuid
    LANGUAGE sql STABLE AS $$
      SELECT NULLIF(current_setting('pono.person_id', true), '')::uuid
    $$
    """,
    """
    CREATE FUNCTION pono_current_organizations() RETURNS uuid[]
    LANGUAGE sql STABLE AS $$
      SELECT COALESCE(NULLIF(current_setting('pono.organization_ids', true), ''), '{}')::uuid[]
    $$
    """,
    """
    CREATE TABLE people (
      id uuid PRIMARY KEY,
      code_host_user_id text NOT NULL UNIQUE,
      login text NOT NULL,
      email text,
      locale text CHECK (locale IN ('fr', 'en')),
      created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "ALTER TABLE people ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE people FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY people_self ON people
      USING (id = pono_current_person())
      WITH CHECK (id = pono_current_person())
    """,
    """
    CREATE TABLE sessions (
      id uuid PRIMARY KEY,
      person_id uuid NOT NULL REFERENCES people (id) ON DELETE CASCADE,
      token_hash bytea NOT NULL UNIQUE,
      created_at timestamptz NOT NULL DEFAULT now(),
      expires_at timestamptz NOT NULL,
      revoked_at timestamptz
    )
    """,
    "ALTER TABLE sessions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE sessions FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY sessions_own ON sessions
      USING (person_id = pono_current_person())
      WITH CHECK (person_id = pono_current_person())
    """,
    """
    CREATE TABLE organizations (
      id uuid PRIMARY KEY,
      name text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "ALTER TABLE organizations ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE organizations FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY organizations_member ON organizations
      USING (id = ANY (pono_current_organizations()))
      WITH CHECK (id = ANY (pono_current_organizations()))
    """,
    """
    CREATE TABLE memberships (
      organization_id uuid NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
      person_id uuid NOT NULL REFERENCES people (id) ON DELETE CASCADE,
      role text NOT NULL CHECK (role IN ('owner')),
      created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (organization_id, person_id)
    )
    """,
    "ALTER TABLE memberships ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE memberships FORCE ROW LEVEL SECURITY",
    """
    CREATE POLICY memberships_member ON memberships
      USING (organization_id = ANY (pono_current_organizations()))
      WITH CHECK (organization_id = ANY (pono_current_organizations()))
    """,
    """
    CREATE FUNCTION pono_resolve_session(p_token_hash bytea)
    RETURNS TABLE (person_id uuid, organization_ids uuid[])
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
      SELECT s.person_id,
             COALESCE(
               array_agg(m.organization_id) FILTER (WHERE m.organization_id IS NOT NULL), '{}'
             )
      FROM sessions s
      LEFT JOIN memberships m ON m.person_id = s.person_id
      WHERE s.token_hash = p_token_hash
        AND s.revoked_at IS NULL
        AND s.expires_at > now()
      GROUP BY s.person_id
    $$
    """,
    """
    CREATE FUNCTION pono_find_person(p_code_host_user_id text)
    RETURNS TABLE (person_id uuid, organization_ids uuid[])
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
      SELECT p.id,
             COALESCE(
               array_agg(m.organization_id) FILTER (WHERE m.organization_id IS NOT NULL), '{}'
             )
      FROM people p
      LEFT JOIN memberships m ON m.person_id = p.id
      WHERE p.code_host_user_id = p_code_host_user_id
      GROUP BY p.id
    $$
    """,
    "REVOKE ALL ON FUNCTION pono_resolve_session(bytea) FROM PUBLIC",
    "REVOKE ALL ON FUNCTION pono_find_person(text) FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION pono_resolve_session(bytea) TO pono_app",
    "GRANT EXECUTE ON FUNCTION pono_find_person(text) TO pono_app",
    "GRANT EXECUTE ON FUNCTION pono_current_person() TO pono_app",
    "GRANT EXECUTE ON FUNCTION pono_current_organizations() TO pono_app",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON people, sessions, organizations, memberships "
    "TO pono_app",
]

DOWNGRADE = [
    "DROP FUNCTION IF EXISTS pono_find_person(text)",
    "DROP FUNCTION IF EXISTS pono_resolve_session(bytea)",
    "DROP TABLE IF EXISTS memberships",
    "DROP TABLE IF EXISTS organizations",
    "DROP TABLE IF EXISTS sessions",
    "DROP TABLE IF EXISTS people",
    "DROP FUNCTION IF EXISTS pono_current_organizations()",
    "DROP FUNCTION IF EXISTS pono_current_person()",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
