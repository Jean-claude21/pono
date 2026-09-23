"""T026 — every table carries forced row-level security, and the app role cannot bypass it."""

import pytest

from tests.conftest import owner_fetch, requires_database

pytestmark = [pytest.mark.security, requires_database]

# Migration bookkeeping only: the app role holds no privilege on it (checked below).
BOOKKEEPING = {"alembic_version"}


async def test_every_table_enables_and_forces_row_level_security(migrated_database: None) -> None:
    tables = await owner_fetch(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r'"
    )
    unprotected = [
        row["relname"]
        for row in tables
        if row["relname"] not in BOOKKEEPING
        and not (row["relrowsecurity"] and row["relforcerowsecurity"])
    ]
    assert tables, "no table found: migrations did not run"
    assert unprotected == []


async def test_app_role_is_neither_owner_nor_bypassing(migrated_database: None) -> None:
    role = await owner_fetch(
        "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = 'pono_app'"
    )
    owned = await owner_fetch(
        "SELECT c.relname FROM pg_class c JOIN pg_roles r ON r.oid = c.relowner "
        "WHERE r.rolname = 'pono_app'"
    )
    assert [(row["rolbypassrls"], row["rolsuper"]) for row in role] == [(False, False)]
    assert owned == []


async def test_security_definer_functions_are_owned_by_a_bypassing_role(
    migrated_database: None,
) -> None:
    """The session and person lookups run before anyone is known; they must see through RLS."""
    owners = await owner_fetch(
        "SELECT p.proname, r.rolbypassrls FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner "
        "WHERE p.prosecdef AND p.proname LIKE 'pono_%'"
    )
    assert {row["proname"] for row in owners} == {"pono_resolve_session", "pono_find_person"}
    assert all(row["rolbypassrls"] for row in owners)


async def test_app_role_has_no_access_to_bookkeeping(migrated_database: None) -> None:
    privileges = await owner_fetch(
        "SELECT has_table_privilege('pono_app', 'alembic_version', 'SELECT') AS can_read"
    )
    assert privileges[0]["can_read"] is False
