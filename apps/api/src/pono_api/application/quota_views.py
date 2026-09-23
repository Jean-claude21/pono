"""The quotas a project depends on, as stored by the last readings (FR-019, FR-024)."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def project_quotas(session: AsyncSession, project_id: UUID) -> list[dict[str, object]]:
    """The latest readings a project depends on: its database and the accounts that host it."""

    rows = await session.execute(
        text(
            'SELECT DISTINCT ON (q.connection_id, q.metric) q.metric, q.used, q."limit", '
            "q.limit_source, q.period_start, q.read_at FROM quota_readings q "
            "WHERE q.project_id = :project_id OR (q.project_id IS NULL AND q.connection_id IN "
            "(SELECT hosting_connection_id FROM environments WHERE project_id = :project_id)) "
            "ORDER BY q.connection_id, q.metric, q.period_start DESC"
        ),
        {"project_id": project_id},
    )
    quotas: list[dict[str, object]] = []
    for row in rows:
        limit = float(row.limit) if row.limit is not None else None
        quotas.append(
            {
                "metric": row.metric,
                "used": float(row.used),
                "limit": limit,
                "limitSource": row.limit_source,
                "readAt": row.read_at.isoformat(),
                "ratio": float(row.used) / limit if limit else None,
            }
        )
    quotas.sort(key=_ratio_key, reverse=True)
    return quotas


def _ratio_key(quota: dict[str, object]) -> float:
    ratio = quota["ratio"]
    return ratio if isinstance(ratio, float) else -1.0


__all__ = ["project_quotas"]
