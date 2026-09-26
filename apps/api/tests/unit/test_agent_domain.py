"""T004 — what an access allows, and who an action is attributed to (003 FR-003, FR-009, FR-012)."""

import pytest

from pono_api.domain.agents import ACT_SCOPE, READ_SCOPE, Access, Actor
from pono_api.domain.releases import ActorKind


def test_read_only_grants_reading_and_nothing_else() -> None:
    assert Access.READ.scopes == (READ_SCOPE,)
    assert Access.ACT.scopes == (READ_SCOPE, ACT_SCOPE)


@pytest.mark.parametrize(
    ("scopes", "access"),
    [
        ([READ_SCOPE], Access.READ),
        ([READ_SCOPE, ACT_SCOPE], Access.ACT),
        ((ACT_SCOPE,), Access.ACT),
        ([], Access.READ),
    ],
)
def test_the_access_is_read_back_from_the_scopes(scopes: list[str], access: Access) -> None:
    assert Access.of(scopes) is access


def test_an_unknown_access_is_refused() -> None:
    with pytest.raises(ValueError, match="admin"):
        Access("admin")


def test_a_person_acts_under_their_own_name() -> None:
    actor = Actor.person("alice")

    assert (actor.kind, actor.name, actor.detail()) == (ActorKind.PERSON, "alice", {})


def test_an_agent_acts_under_its_name_and_the_person_who_granted_it() -> None:
    actor = Actor.agent("Claude", "alice")

    assert (actor.kind, actor.name) == (ActorKind.AGENT, "Claude")
    assert actor.detail() == {"grantedBy": "alice"}
