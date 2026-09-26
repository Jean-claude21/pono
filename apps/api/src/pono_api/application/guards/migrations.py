"""The migrations guard (002 FR-005, FR-008, research R-04): only additive migrations ship.

SQL migration files are split into statements here (strings, comments and `$$` bodies kept whole),
then each statement is parsed. A statement the parser cannot read is examined as text for the same
destructive operations, strings and function bodies included. A migration written in a programming
language, or one that cannot be read at all, is refused.
"""

import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from pono_api.application.ports import ChangedFile
from pono_api.domain.manifest import ManifestRelease
from pono_api.domain.projects import MANIFEST_PATH
from pono_api.domain.releases import Finding, Guard, GuardResult

DEFAULT_FOLDERS = (
    "drizzle",
    "supabase/migrations",
    "prisma/migrations",
    "migrations",
    "db/migrations",
)
CODE_SUFFIXES = frozenset({".py", ".ts", ".js", ".mjs", ".cjs", ".rb", ".go", ".java", ".kt"})

# The parser warns on every statement it falls back on; the guard handles those itself.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

_TEXT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("drop_table", re.compile(r"(?is)\bdrop\s+(?:table|schema|database)\b")),
    ("drop_column", re.compile(r"(?is)\bdrop\s+column\b")),
    (
        "drop_column",
        re.compile(
            r"(?is)\balter\s+table\b[^;]*?\bdrop\s+(?!constraint\b|default\b|not\s+null\b|"
            r"identity\b|expression\b|column\b)[\"\w]"
        ),
    ),
    (
        "rename",
        re.compile(r"(?is)\brename\s+(?:column\s+|constraint\s+)?[\"\w.]*\s*to\b|\brename\s+to\b"),
    ),
    ("alter_type", re.compile(r"(?is)\balter\s+(?:column\s+)?[\"\w]+\s+(?:set\s+data\s+)?type\b")),
    ("truncate", re.compile(r"(?is)\btruncate\b")),
    (
        "delete_all",
        re.compile(
            r"(?is)\bdelete\s+from\s+[\"\w.]+(?:\s+(?:as\s+)?\w+)?\s*(?:;|\)|'|$|returning\b)"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class Statement:
    line: int
    text: str


def split_statements(sql: str) -> list[Statement]:
    """Split on `;` outside strings, quoted names, comments and dollar-quoted bodies."""

    statements: list[Statement] = []
    buffer: list[str] = []
    start_line, line, index = 1, 1, 0
    while index < len(sql):
        char = sql[index]
        if not "".join(buffer).strip() and not char.isspace():
            start_line = line
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = len(sql) if end == -1 else end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            end = len(sql) if end == -1 else end + 2
            line += sql.count("\n", index, end)
            index = end
            continue
        dollar = re.match(r"\$[A-Za-z_]*\$", sql[index:])
        if dollar:
            tag = dollar.group(0)
            end = sql.find(tag, index + len(tag))
            end = len(sql) if end == -1 else end + len(tag)
            chunk = sql[index:end]
        elif char in ("'", '"'):
            end = index + 1
            while end < len(sql):
                if sql[end] == char and sql.startswith(char * 2, end):
                    end += 2
                    continue
                if sql[end] == char:
                    end += 1
                    break
                end += 1
            chunk = sql[index:end]
        elif char == ";":
            if "".join(buffer).strip():
                statements.append(Statement(start_line, "".join(buffer).strip()))
            buffer = []
            index += 1
            continue
        else:
            chunk = char
            end = index + 1
        buffer.append(chunk)
        line += chunk.count("\n")
        index = end
    if "".join(buffer).strip():
        statements.append(Statement(start_line, "".join(buffer).strip()))
    return statements


def _from_tree(tree: exp.Expr) -> list[str]:
    operations: list[str] = []
    if isinstance(tree, exp.Drop) and str(tree.args.get("kind") or "").upper() in {
        "TABLE",
        "SCHEMA",
        "DATABASE",
    }:
        operations.append("drop_table")
    elif isinstance(tree, exp.TruncateTable):
        operations.append("truncate")
    elif isinstance(tree, exp.Delete) and tree.args.get("where") is None:
        operations.append("delete_all")
    elif isinstance(tree, exp.Alter):
        for action in tree.args.get("actions") or []:
            if isinstance(action, exp.Drop) and str(action.args.get("kind") or "").upper() in {
                "COLUMN",
                "",
            }:
                operations.append("drop_column")
            elif isinstance(action, exp.RenameColumn | exp.AlterRename):
                operations.append("rename")
            elif isinstance(action, exp.AlterColumn) and action.args.get("dtype") is not None:
                operations.append("alter_type")
    return operations


def _from_text(statement: str) -> list[str]:
    return list(dict.fromkeys(kind for kind, rule in _TEXT_RULES if rule.search(statement)))


def destructive_operations(sql: str) -> list[tuple[int, str]]:
    """(line, operation) for every destructive operation of a SQL migration."""

    found: list[tuple[int, str]] = []
    for statement in split_statements(sql):
        try:
            trees = [tree for tree in sqlglot.parse(statement.text, read="postgres") if tree]
        except SqlglotError:
            trees = []
        # A tree that kept any part as raw text was not understood: read the text instead.
        readable = [tree for tree in trees if tree.find(exp.Command) is None]
        operations = (
            [op for tree in readable for op in _from_tree(tree)]
            if readable and len(readable) == len(trees)
            else _from_text(statement.text)
        )
        found.extend((statement.line, operation) for operation in operations)
    return found


def migration_folders(release: ManifestRelease | None) -> tuple[str, ...]:
    declared = release.migrations if release and release.migrations else None
    return tuple(folder.strip("/") for folder in (declared or DEFAULT_FOLDERS))


def is_migration(path: str, folders: Iterable[str]) -> bool:
    return any(path.startswith(f"{folder}/") for folder in folders)


def migration_files(files: Iterable[ChangedFile], release: ManifestRelease | None) -> list[str]:
    """The added SQL migrations whose content the guard needs."""

    folders = migration_folders(release)
    return [
        changed.path
        for changed in files
        if changed.status == "added"
        and is_migration(changed.path, folders)
        and PurePosixPath(changed.path).suffix.lower() == ".sql"
    ]


def inspect_migrations(
    files: Iterable[ChangedFile],
    contents: Mapping[str, str | None],
    release: ManifestRelease | None,
) -> GuardResult:
    changed = list(files)
    folders = migration_folders(release)
    failures: list[Finding] = []
    destructive: list[Finding] = []
    for item in changed:
        if not is_migration(item.path, folders):
            continue
        suffix = PurePosixPath(item.path).suffix.lower()
        if suffix in CODE_SUFFIXES:
            failures.append(Finding("migrations.unreadable", file=item.path))
            continue
        if suffix != ".sql":
            continue  # snapshots, journals and notes that tools keep next to migrations
        if item.status != "added":
            failures.append(
                Finding("migrations.history_rewritten", file=item.path, operation=item.status)
            )
            continue
        content = contents.get(item.path)
        if content is None:
            failures.append(Finding("migrations.unreadable", file=item.path))
            continue
        destructive.extend(
            Finding("migrations.destructive", file=item.path, line=line, operation=operation)
            for line, operation in destructive_operations(content)
        )
    if failures:
        return GuardResult.failed(Guard.MIGRATIONS, failures[0].code, *failures, *destructive)
    if not destructive:
        return GuardResult.passed(Guard.MIGRATIONS)
    return _declared(changed, destructive, release)


def _declared(
    changed: list[ChangedFile], destructive: list[Finding], release: ManifestRelease | None
) -> GuardResult:
    """A destruction passes only when the repository declared it and the change holds nothing else
    (clarification FR-008)."""

    declared = {
        (item.file, item.operation)
        for item in (release.declared_destructions or [] if release else [])
    }
    if not all((finding.file, finding.operation) in declared for finding in destructive):
        return GuardResult.failed(Guard.MIGRATIONS, "migrations.destructive", *destructive)
    allowed = {finding.file for finding in destructive} | {MANIFEST_PATH}
    if any(item.path not in allowed for item in changed):
        return GuardResult.failed(
            Guard.MIGRATIONS,
            "migrations.destruction_not_isolated",
            Finding("migrations.destruction_not_isolated"),
            *destructive,
        )
    return GuardResult.passed(Guard.MIGRATIONS).with_findings(
        "migrations.destruction_declared",
        *(
            Finding(
                "migrations.destruction_declared", finding.file, finding.line, finding.operation
            )
            for finding in destructive
        ),
    )


__all__ = [
    "DEFAULT_FOLDERS",
    "destructive_operations",
    "inspect_migrations",
    "is_migration",
    "migration_files",
    "split_statements",
]
