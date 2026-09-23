"""Sign-in with the code host identity, and sign-out."""

import secrets
from datetime import timedelta
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, Query, Response
from fastapi.responses import RedirectResponse

from pono_api.api.dependencies import IdentityDep, PrincipalDep, SessionsDep, SettingsDep
from pono_api.application.identity import IdentityProviderError
from pono_api.application.sessions import SESSION_COOKIE, resolve_session, revoke_session
from pono_api.application.sign_in import saved_locale, sign_in
from pono_api.errors import ApiError

STATE_COOKIE = "pono_oauth_state"
STATE_TTL_SECONDS = 600
# Read by the console's language negotiation (Paraglide, `cookie` strategy).
LOCALE_COOKIE = "pono_locale"
LOCALE_COOKIE_MAX_AGE = 400 * 24 * 3600

router = APIRouter(prefix="/auth", tags=["auth"])


def _console_redirect(public_url: str, path: str, error: str | None = None) -> RedirectResponse:
    target = f"{public_url.rstrip('/')}{path}"
    if error:
        target = f"{target}?{urlencode({'error': error})}"
    return RedirectResponse(target, status_code=302)


@router.get("/login")
async def login(
    settings: SettingsDep,
    sessions: SessionsDep,
    identity: IdentityDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> RedirectResponse:
    # A session that still holds opens the workshop at once: no round trip to the code host
    # when someone comes back to their projects (SC-002).
    principal = await resolve_session(sessions, token)
    if principal is not None and principal.organization_ids:
        return _console_redirect(settings.public_url, "/workshop")
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(
        identity.authorization_url(state, settings.auth_callback_url), status_code=302
    )
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/api/v1/auth",
    )
    return response


@router.get("/callback")
async def callback(
    settings: SettingsDep,
    sessions: SessionsDep,
    identity: IdentityDep,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    expected_state: Annotated[str | None, Cookie(alias=STATE_COOKIE)] = None,
) -> RedirectResponse:
    if not expected_state or not secrets.compare_digest(state, expected_state):
        return _console_redirect(settings.public_url, "/", "auth.state_mismatch")
    try:
        user_token = await identity.exchange_code(code, settings.auth_callback_url)
        user = await identity.fetch_user(user_token)
        principal, issued = await sign_in(
            sessions,
            user,
            allowed_logins=settings.allowed_logins,
            session_ttl=timedelta(hours=settings.session_ttl_hours),
        )
    except IdentityProviderError:
        return _console_redirect(settings.public_url, "/", "auth.provider_refused")
    except ApiError as error:
        return _console_redirect(settings.public_url, "/", error.code)

    response = _console_redirect(settings.public_url, "/workshop")
    response.delete_cookie(STATE_COOKIE, path="/api/v1/auth")
    # The language chosen earlier follows the person to any browser (FR-003, research R-05).
    locale = await saved_locale(sessions, principal)
    if locale:
        response.set_cookie(
            LOCALE_COOKIE,
            locale,
            max_age=LOCALE_COOKIE_MAX_AGE,
            secure=settings.secure_cookies,
            samesite="lax",
            path="/",
        )
    response.set_cookie(
        SESSION_COOKIE,
        issued.token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout", status_code=204)
async def logout(
    sessions: SessionsDep,
    principal: PrincipalDep,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    if token:
        await revoke_session(sessions, principal, token)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


__all__ = ["router"]
