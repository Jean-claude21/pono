"""T031 — link checker: 10 s per attempt, two attempts, HEAD then GET (FR-020)."""

import httpx
import pytest

from pono_api.domain.projects import LinkStatus
from pono_api.infrastructure.link_checker import ATTEMPTS, TIMEOUT_SECONDS, HttpLinkChecker

pytestmark = pytest.mark.unit

URL = "https://app.example.test/"


def checker(*answers: int | Exception) -> tuple[HttpLinkChecker, list[str]]:
    """A checker whose server gives the scripted answers, in order, one per request."""

    script = list(answers)
    seen: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        answer = script.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(answer)

    return HttpLinkChecker(transport=httpx.MockTransport(handle)), seen


def test_the_contract_is_ten_seconds_and_two_attempts() -> None:
    assert (TIMEOUT_SECONDS, ATTEMPTS) == (10.0, 2)


async def test_a_link_answering_head_is_up() -> None:
    links, seen = checker(200)
    assert await links.check(URL) is LinkStatus.UP
    assert seen == ["HEAD"]


@pytest.mark.parametrize("refused", [403, 405, 501])
async def test_a_server_refusing_head_is_asked_with_get(refused: int) -> None:
    links, seen = checker(refused, 200)
    assert await links.check(URL) is LinkStatus.UP
    assert seen == ["HEAD", "GET"]


async def test_a_client_error_still_means_the_service_answers() -> None:
    links, _ = checker(404)
    assert await links.check(URL) is LinkStatus.UP


async def test_one_slow_attempt_is_not_enough_to_call_a_link_down() -> None:
    links, seen = checker(httpx.ReadTimeout("slow"), 200)
    assert await links.check(URL) is LinkStatus.UP
    assert seen == ["HEAD", "HEAD"]


async def test_two_failed_attempts_make_a_link_down() -> None:
    links, seen = checker(httpx.ConnectTimeout("asleep"), httpx.ReadTimeout("still asleep"))
    assert await links.check(URL) is LinkStatus.DOWN
    assert seen == ["HEAD", "HEAD"]


async def test_server_errors_twice_make_a_link_down() -> None:
    links, _ = checker(503, 502)
    assert await links.check(URL) is LinkStatus.DOWN


async def test_a_get_fallback_error_counts_as_a_failed_attempt() -> None:
    links, seen = checker(405, httpx.ConnectError("refused"), 405, 500)
    assert await links.check(URL) is LinkStatus.DOWN
    assert seen == ["HEAD", "GET", "HEAD", "GET"]
