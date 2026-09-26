"""T011 — only additive migrations ship; what cannot be read is refused (FR-005, FR-008)."""

import pytest

from pono_api.application.guards.migrations import (
    destructive_operations,
    inspect_migrations,
    migration_files,
    split_statements,
)
from pono_api.application.ports import ChangedFile
from pono_api.domain.manifest import DeclaredDestruction, ManifestRelease
from pono_api.domain.releases import GuardStatus

# A real migration of nettio (supabase), which the SQL parser cannot fully read.
NETTIO_POLICY = """
create table if not exists public.memberships (
  organization_id uuid not null,
  user_id uuid not null,
  role text not null default 'member'
);
alter table public.memberships enable row level security;
create policy "members read" on public.memberships for select using (user_id = auth.uid());
create or replace function public.is_member(org uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.memberships m where m.organization_id = org);
$$;
"""


def _file(path: str, status: str = "added") -> ChangedFile:
    return ChangedFile(path, status, "")


@pytest.mark.parametrize(
    ("sql", "operation"),
    [
        ("ALTER TABLE notes DROP COLUMN body;", "drop_column"),
        ("ALTER TABLE notes DROP body;", "drop_column"),
        ("ALTER TABLE notes RENAME COLUMN a TO b;", "rename"),
        ("ALTER TABLE notes RENAME TO archive;", "rename"),
        ("ALTER TABLE notes ALTER COLUMN title TYPE varchar(10);", "alter_type"),
        ("DROP TABLE notes;", "drop_table"),
        ("drop schema legacy cascade;", "drop_table"),
        ("TRUNCATE notes;", "truncate"),
        ("DELETE FROM notes;", "delete_all"),
        ("DO $$ BEGIN EXECUTE 'DROP TABLE notes'; END $$;", "drop_table"),
    ],
)
def test_each_destructive_operation_is_found(sql: str, operation: str) -> None:
    assert [op for _, op in destructive_operations(sql)] == [operation]


@pytest.mark.parametrize(
    "sql",
    [
        'ALTER TABLE "books" ADD COLUMN "notes" text;',
        "CREATE TABLE notes (id uuid primary key);",
        "CREATE INDEX notes_by_book ON notes (book_id);",
        "ALTER TABLE notes ALTER COLUMN title SET NOT NULL;",
        "ALTER TABLE notes DROP CONSTRAINT notes_fk;",
        "DROP INDEX notes_by_book;",
        "DELETE FROM notes WHERE archived;",
        "INSERT INTO notes (body) VALUES ('drop table; rename to');",
        "-- DROP TABLE notes;\nSELECT 1;",
        NETTIO_POLICY,
    ],
)
def test_additive_and_harmless_statements_pass(sql: str) -> None:
    assert destructive_operations(sql) == []


def test_statements_are_split_outside_strings_comments_and_bodies() -> None:
    sql = "SELECT ';';\n/* ; */\nSELECT $$ ; $$;\n-- ;\nSELECT 3"
    assert [(s.line, s.text) for s in split_statements(sql)] == [
        (1, "SELECT ';'"),
        (3, "SELECT $$ ; $$"),
        (5, "SELECT 3"),
    ]


def test_a_destructive_migration_is_refused_with_file_line_and_operation() -> None:
    path = "drizzle/0003_drop_notes.sql"
    result = inspect_migrations(
        [_file(path), _file("src/app.ts")],
        {path: "ALTER TABLE books ADD COLUMN x int;\nALTER TABLE notes DROP COLUMN body;"},
        None,
    )

    assert result.status is GuardStatus.FAILED
    assert result.reason == "migrations.destructive"
    (finding,) = result.findings
    assert (finding.file, finding.line, finding.operation) == (path, 2, "drop_column")


def test_only_added_sql_under_migration_folders_is_read() -> None:
    files = [
        _file("drizzle/0003_add.sql"),
        _file("drizzle/meta/_journal.json"),
        _file("docs/schema.sql"),
        _file("supabase/migrations/2026_old.sql", "removed"),
    ]
    assert migration_files(files, None) == ["drizzle/0003_add.sql"]
    declared = ManifestRelease(migrations=["db/sql"])
    assert migration_files([_file("db/sql/1.sql"), _file("drizzle/2.sql")], declared) == [
        "db/sql/1.sql"
    ]


@pytest.mark.parametrize(
    ("changed", "contents", "code"),
    [
        (_file("migrations/0002.py"), {}, "migrations.unreadable"),
        (_file("drizzle/0003.sql"), {"drizzle/0003.sql": None}, "migrations.unreadable"),
        (_file("drizzle/0001.sql", "modified"), {}, "migrations.history_rewritten"),
        (_file("drizzle/0001.sql", "removed"), {}, "migrations.history_rewritten"),
    ],
)
def test_what_cannot_be_trusted_is_refused(
    changed: ChangedFile, contents: dict[str, str | None], code: str
) -> None:
    result = inspect_migrations([changed], contents, None)
    assert (result.status, result.reason) == (GuardStatus.FAILED, code)


def test_a_change_without_migration_passes() -> None:
    assert inspect_migrations([_file("src/app.ts")], {}, None).status is GuardStatus.PASSED


def test_a_declared_destruction_passes_only_when_it_ships_alone() -> None:
    path = "drizzle/0007_drop_legacy.sql"
    release = ManifestRelease(
        declared_destructions=[DeclaredDestruction(file=path, operation="drop_column")]
    )
    contents = {path: "ALTER TABLE notes DROP COLUMN legacy;"}

    alone = inspect_migrations(
        [_file(path), _file(".pono/project.json", "modified")], contents, release
    )
    mixed = inspect_migrations([_file(path), _file("src/app.ts")], contents, release)
    undeclared = inspect_migrations([_file(path)], {path: "DROP TABLE notes;"}, release)

    assert (alone.status, alone.reason) == (GuardStatus.PASSED, "migrations.destruction_declared")
    assert alone.findings[0].operation == "drop_column"
    assert (mixed.status, mixed.reason) == (
        GuardStatus.FAILED,
        "migrations.destruction_not_isolated",
    )
    assert (undeclared.status, undeclared.reason) == (GuardStatus.FAILED, "migrations.destructive")
