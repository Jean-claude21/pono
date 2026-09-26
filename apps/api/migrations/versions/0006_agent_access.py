"""Agent access: registered clients, authorization requests, grants, tokens, rollback requests.

Revision ID: 0006_agent_access
Revises: 0005_guarded_release
Create Date: 2026-09-23

Row-level security is enabled and forced here for every table (constitution VI). A client registers
and asks for access before anyone is known, so `agent_clients` and `agent_requests` carry no policy
at all: only the SECURITY DEFINER functions below reach them, and each returns only what its step
needs. Grants, tokens and rollback requests belong to an organization and live under its policy.
Tokens and codes are stored as SHA-256 digests only (003 research R-02, SC-005).
"""

from alembic import op

revision = "0006_agent_access"
down_revision = "0005_guarded_release"
branch_labels = None
depends_on = None


def _lock(table: str) -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
    ]


def _protect(table: str) -> list[str]:
    return [
        *_lock(table),
        f"""
        CREATE POLICY {table}_member ON {table}
          USING (organization_id = ANY (pono_current_organizations()))
          WITH CHECK (organization_id = ANY (pono_current_organizations()))
        """,
    ]


def _function(signature: str, returns: str, body: str, language: str = "sql") -> list[str]:
    name = signature.split("(", 1)[0]
    arguments = "(" + signature.split("(", 1)[1]
    types = ", ".join(
        part.strip().split(" ", 1)[1] for part in arguments.strip("()").split(",") if part.strip()
    )
    volatility = "" if language == "plpgsql" else "VOLATILE "
    return [
        f"""
        CREATE FUNCTION {signature}
        RETURNS {returns}
        LANGUAGE {language} {volatility}SECURITY DEFINER SET search_path = public, pg_temp AS $$
        {body}
        $$
        """,
        f"REVOKE ALL ON FUNCTION {name}({types}) FROM PUBLIC",
        f"GRANT EXECUTE ON FUNCTION {name}({types}) TO pono_app",
    ]


TABLES = [
    """
    CREATE TABLE agent_clients (
      client_id text PRIMARY KEY,
      metadata jsonb NOT NULL,
      secret_ciphertext bytea,
      created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    *_lock("agent_clients"),
    """
    CREATE TABLE agent_requests (
      id uuid PRIMARY KEY,
      request_digest bytea NOT NULL UNIQUE,
      client_id text NOT NULL REFERENCES agent_clients (client_id) ON DELETE CASCADE,
      redirect_uri text NOT NULL,
      redirect_uri_explicit boolean NOT NULL,
      code_challenge text NOT NULL,
      scopes text[] NOT NULL,
      state text,
      resource text NOT NULL,
      code_digest bytea UNIQUE,
      person_id uuid REFERENCES people (id) ON DELETE CASCADE,
      organization_id uuid REFERENCES organizations (id) ON DELETE CASCADE,
      grant_id uuid,
      approved_at timestamptz,
      denied_at timestamptz,
      consumed_at timestamptz,
      expires_at timestamptz NOT NULL
    )
    """,
    *_lock("agent_requests"),
    """
    CREATE TABLE agent_grants (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
      person_id uuid NOT NULL REFERENCES people (id) ON DELETE CASCADE,
      client_id text NOT NULL REFERENCES agent_clients (client_id) ON DELETE CASCADE,
      client_name text NOT NULL,
      scopes text[] NOT NULL,
      granted_at timestamptz NOT NULL DEFAULT now(),
      last_used_at timestamptz,
      revoked_at timestamptz,
      UNIQUE (organization_id, id)
    )
    """,
    *_protect("agent_grants"),
    """
    CREATE TABLE agent_tokens (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      grant_id uuid NOT NULL,
      token_digest bytea NOT NULL UNIQUE,
      kind text NOT NULL CHECK (kind IN ('access', 'refresh')),
      expires_at timestamptz NOT NULL,
      revoked_at timestamptz,
      FOREIGN KEY (organization_id, grant_id)
        REFERENCES agent_grants (organization_id, id) ON DELETE CASCADE
    )
    """,
    *_protect("agent_tokens"),
    """
    CREATE TABLE rollback_requests (
      id uuid PRIMARY KEY,
      organization_id uuid NOT NULL,
      project_id uuid NOT NULL,
      grant_id uuid NOT NULL,
      status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'dismissed', 'expired')),
      requested_at timestamptz NOT NULL DEFAULT now(),
      decided_at timestamptz,
      decided_by uuid REFERENCES people (id),
      rollback_id uuid REFERENCES rollbacks (id),
      FOREIGN KEY (organization_id, project_id)
        REFERENCES projects (organization_id, id) ON DELETE CASCADE,
      FOREIGN KEY (organization_id, grant_id)
        REFERENCES agent_grants (organization_id, id) ON DELETE CASCADE
    )
    """,
    "CREATE UNIQUE INDEX rollback_requests_one_pending ON rollback_requests (project_id) "
    "WHERE status = 'pending'",
    *_protect("rollback_requests"),
    "GRANT SELECT, INSERT, UPDATE ON agent_grants, agent_tokens, rollback_requests TO pono_app",
]

FUNCTIONS = [
    # A client registers before anyone is known.
    *_function(
        "pono_agent_register(p_client_id text, p_metadata jsonb, p_secret bytea)",
        "void",
        "INSERT INTO agent_clients (client_id, metadata, secret_ciphertext) "
        "VALUES (p_client_id, p_metadata, p_secret)",
    ),
    *_function(
        "pono_agent_client(p_client_id text)",
        "TABLE (metadata jsonb, secret_ciphertext bytea)",
        "SELECT metadata, secret_ciphertext FROM agent_clients WHERE client_id = p_client_id",
    ),
    # The authorization request opens before anyone consents.
    *_function(
        "pono_agent_open_request(p_id uuid, p_digest bytea, p_client_id text, "
        "p_redirect_uri text, p_explicit boolean, p_challenge text, p_scopes text[], "
        "p_state text, p_resource text, p_expires timestamptz)",
        "void",
        "INSERT INTO agent_requests (id, request_digest, client_id, redirect_uri, "
        "redirect_uri_explicit, code_challenge, scopes, state, resource, expires_at) "
        "VALUES (p_id, p_digest, p_client_id, p_redirect_uri, p_explicit, p_challenge, "
        "p_scopes, p_state, p_resource, p_expires)",
    ),
    # The consent page reads what is asked, and nothing else.
    *_function(
        "pono_agent_request(p_digest bytea)",
        "TABLE (client_name text, scopes text[], expires_at timestamptz)",
        "SELECT COALESCE(c.metadata ->> 'client_name', c.client_id), r.scopes, r.expires_at "
        "FROM agent_requests r JOIN agent_clients c ON c.client_id = r.client_id "
        "WHERE r.request_digest = p_digest AND r.approved_at IS NULL AND r.denied_at IS NULL "
        "AND r.expires_at > now()",
    ),
    # A person decides, for their own organization only; an approval creates the grant.
    *_function(
        "pono_agent_decide(p_digest bytea, p_approve boolean, p_code_digest bytea, "
        "p_scopes text[], p_grant_id uuid, p_code_expires timestamptz)",
        "TABLE (redirect_uri text, state text)",
        """
        DECLARE
          request agent_requests%ROWTYPE;
          person uuid := pono_current_person();
          organization uuid := (pono_current_organizations())[1];
        BEGIN
          IF person IS NULL OR organization IS NULL THEN
            RETURN;
          END IF;
          SELECT * INTO request FROM agent_requests
            WHERE request_digest = p_digest AND approved_at IS NULL AND denied_at IS NULL
              AND expires_at > now()
            FOR UPDATE;
          IF NOT FOUND THEN
            RETURN;
          END IF;
          IF NOT p_approve THEN
            UPDATE agent_requests SET denied_at = now() WHERE id = request.id;
            RETURN QUERY SELECT request.redirect_uri, request.state;
            RETURN;
          END IF;
          IF NOT (p_scopes <@ request.scopes) THEN
            RETURN;
          END IF;
          INSERT INTO agent_grants (id, organization_id, person_id, client_id, client_name, scopes)
            SELECT p_grant_id, organization, person, c.client_id,
                   COALESCE(c.metadata ->> 'client_name', c.client_id), p_scopes
            FROM agent_clients c WHERE c.client_id = request.client_id;
          UPDATE agent_requests SET approved_at = now(), code_digest = p_code_digest,
                 person_id = person, organization_id = organization, grant_id = p_grant_id,
                 scopes = p_scopes, expires_at = p_code_expires
            WHERE id = request.id;
          RETURN QUERY SELECT request.redirect_uri, request.state;
        END
        """,
        language="plpgsql",
    ),
    # The client redeems its code at the token endpoint, before anyone is known.
    *_function(
        "pono_agent_code(p_code_digest bytea, p_client_id text)",
        "TABLE (grant_id uuid, scopes text[], code_challenge text, redirect_uri text, "
        "redirect_uri_explicit boolean, resource text, expires_at timestamptz, person_id uuid)",
        "SELECT grant_id, scopes, code_challenge, redirect_uri, redirect_uri_explicit, resource, "
        "expires_at, person_id FROM agent_requests WHERE code_digest = p_code_digest "
        "AND client_id = p_client_id AND approved_at IS NOT NULL AND consumed_at IS NULL "
        "AND expires_at > now()",
    ),
    *_function(
        "pono_agent_issue(p_code_digest bytea, p_client_id text, p_access bytea, p_refresh bytea, "
        "p_access_expires timestamptz, p_refresh_expires timestamptz)",
        "boolean",
        """
        DECLARE
          request agent_requests%ROWTYPE;
        BEGIN
          UPDATE agent_requests SET consumed_at = now()
            WHERE code_digest = p_code_digest AND client_id = p_client_id
              AND approved_at IS NOT NULL AND consumed_at IS NULL AND expires_at > now()
            RETURNING * INTO request;
          IF NOT FOUND THEN
            RETURN false;
          END IF;
          INSERT INTO agent_tokens (id, organization_id, grant_id, token_digest, kind, expires_at)
          VALUES (gen_random_uuid(), request.organization_id, request.grant_id, p_access, 'access',
                  p_access_expires),
                 (gen_random_uuid(), request.organization_id, request.grant_id, p_refresh,
                  'refresh', p_refresh_expires);
          RETURN true;
        END
        """,
        language="plpgsql",
    ),
    # A presented token becomes a principal only while token, grant and client all hold.
    *_function(
        "pono_agent_token(p_digest bytea, p_kind text)",
        "TABLE (grant_id uuid, organization_id uuid, person_id uuid, client_id text, "
        "client_name text, scopes text[], expires_at timestamptz)",
        "SELECT g.id, g.organization_id, g.person_id, g.client_id, g.client_name, g.scopes, "
        "t.expires_at FROM agent_tokens t JOIN agent_grants g ON g.id = t.grant_id "
        "WHERE t.token_digest = p_digest AND t.kind = p_kind AND t.revoked_at IS NULL "
        "AND t.expires_at > now() AND g.revoked_at IS NULL",
    ),
    *_function(
        "pono_agent_rotate(p_refresh bytea, p_client_id text, p_access bytea, p_new_refresh bytea, "
        "p_access_expires timestamptz, p_refresh_expires timestamptz)",
        "boolean",
        """
        DECLARE
          old agent_tokens%ROWTYPE;
        BEGIN
          UPDATE agent_tokens t SET revoked_at = now()
            FROM agent_grants g
            WHERE t.token_digest = p_refresh AND t.kind = 'refresh' AND t.revoked_at IS NULL
              AND t.expires_at > now() AND g.id = t.grant_id AND g.client_id = p_client_id
              AND g.revoked_at IS NULL
            RETURNING t.* INTO old;
          IF NOT FOUND THEN
            RETURN false;
          END IF;
          INSERT INTO agent_tokens (id, organization_id, grant_id, token_digest, kind, expires_at)
          VALUES (gen_random_uuid(), old.organization_id, old.grant_id, p_access, 'access',
                  p_access_expires),
                 (gen_random_uuid(), old.organization_id, old.grant_id, p_new_refresh, 'refresh',
                  p_refresh_expires);
          RETURN true;
        END
        """,
        language="plpgsql",
    ),
    # A client revokes its own tokens; the whole grant's tokens go with them.
    *_function(
        "pono_agent_revoke(p_digest bytea)",
        "void",
        "UPDATE agent_tokens SET revoked_at = now() WHERE revoked_at IS NULL AND grant_id IN "
        "(SELECT grant_id FROM agent_tokens WHERE token_digest = p_digest)",
    ),
    # Last use, at most once a minute: shown in the console, never a secret.
    *_function(
        "pono_agent_touch(p_grant_id uuid)",
        "void",
        "UPDATE agent_grants SET last_used_at = now() WHERE id = p_grant_id "
        "AND (last_used_at IS NULL OR last_used_at < now() - interval '1 minute')",
    ),
]

UPGRADE = [*TABLES, *FUNCTIONS]

DOWNGRADE = [
    "DROP FUNCTION IF EXISTS pono_agent_touch(uuid)",
    "DROP FUNCTION IF EXISTS pono_agent_revoke(bytea)",
    "DROP FUNCTION IF EXISTS pono_agent_rotate(bytea, text, bytea, bytea, timestamptz, "
    "timestamptz)",
    "DROP FUNCTION IF EXISTS pono_agent_token(bytea, text)",
    "DROP FUNCTION IF EXISTS pono_agent_issue(bytea, text, bytea, bytea, timestamptz, timestamptz)",
    "DROP FUNCTION IF EXISTS pono_agent_code(bytea, text)",
    "DROP FUNCTION IF EXISTS pono_agent_decide(bytea, boolean, bytea, text[], uuid, timestamptz)",
    "DROP FUNCTION IF EXISTS pono_agent_request(bytea)",
    "DROP FUNCTION IF EXISTS pono_agent_open_request(uuid, bytea, text, text, boolean, text, "
    "text[], text, text, timestamptz)",
    "DROP FUNCTION IF EXISTS pono_agent_client(text)",
    "DROP FUNCTION IF EXISTS pono_agent_register(text, jsonb, bytea)",
    "DROP TABLE IF EXISTS rollback_requests",
    "DROP TABLE IF EXISTS agent_tokens",
    "DROP TABLE IF EXISTS agent_grants",
    "DROP TABLE IF EXISTS agent_requests",
    "DROP TABLE IF EXISTS agent_clients",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
