"""Row-level security context: every unit of work states who is acting and for which organizations.

Policies read `pono.person_id` and `pono.organization_ids` (research R-02). Both are set with
`set_config(..., is_local => true)`, so they die with the transaction and never leak to the next
request sharing the pooled connection.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated person and the organizations they belong to."""

    person_id: UUID
    organization_ids: tuple[UUID, ...] = field(default_factory=tuple)

    @property
    def organization_id(self) -> UUID:
        """The organization acted for. Phase 1 has one per person: their personal organization."""

        return self.organization_ids[0]

    @classmethod
    def for_organization(cls, organization_id: UUID) -> Principal:
        """The worker's principal: no person, one organization (research R-09)."""

        return cls(person_id=UUID(int=0), organization_ids=(organization_id,))


def _organizations_literal(organization_ids: tuple[UUID, ...]) -> str:
    return "{" + ",".join(str(organization_id) for organization_id in organization_ids) + "}"


async def apply_principal(session: AsyncSession, principal: Principal | None) -> None:
    """Bind the principal to the current transaction; `None` means nobody (every policy denies)."""

    await session.execute(
        text(
            "SELECT set_config('pono.person_id', :person_id, true), "
            "set_config('pono.organization_ids', :organization_ids, true)"
        ),
        {
            "person_id": str(principal.person_id) if principal else "",
            "organization_ids": _organizations_literal(principal.organization_ids)
            if principal
            else "{}",
        },
    )


@asynccontextmanager
async def unit_of_work(
    sessions: async_sessionmaker[AsyncSession], principal: Principal | None
) -> AsyncIterator[AsyncSession]:
    """One transaction, bound to one principal, committed on success and rolled back on error."""

    async with sessions() as session, session.begin():
        await apply_principal(session, principal)
        yield session


__all__ = ["Principal", "apply_principal", "unit_of_work"]
