"""Validated, secret-safe service configuration."""

import base64
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Every credential is a SecretStr so it never prints by accident."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PONO_",
        extra="ignore",
    )

    environment: Literal["local", "test", "production"] = "local"

    # The owner role runs migrations; the app role serves requests under row-level security.
    database_owner_url: SecretStr | None = None
    database_app_url: SecretStr | None = None

    # Public URL of the console; the sign-in callback and cookie security derive from it.
    public_url: str = "http://localhost:3000"

    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None
    github_private_key: SecretStr | None = None

    allowed_logins: Annotated[frozenset[str], NoDecode] = frozenset()

    encryption_key: SecretStr | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None

    # Quota alerts by chat (D-015): the one bot the service speaks through.
    telegram_bot_token: SecretStr | None = None

    session_ttl_hours: int = 720

    @field_validator("allowed_logins", mode="before")
    @classmethod
    def _split_logins(cls, value: object) -> object:
        # Code host logins are case-insensitive: compare them lowercased everywhere.
        if isinstance(value, str):
            return frozenset(login.strip().lower() for login in value.split(",") if login.strip())
        return value

    @property
    def github_private_key_pem(self) -> SecretStr | None:
        """The App key, given as PEM or as base64 of the PEM (one line suits env files)."""

        if self.github_private_key is None:
            return None
        raw = self.github_private_key.get_secret_value().strip()
        if raw.startswith("-----BEGIN"):
            return SecretStr(raw)
        return SecretStr(base64.b64decode(raw).decode())

    @property
    def code_host_install_url(self) -> str | None:
        if not self.github_app_slug:
            return None
        return f"https://github.com/apps/{self.github_app_slug}/installations/new"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def chat_configured(self) -> bool:
        return self.telegram_bot_token is not None

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")

    @property
    def mcp_resource_url(self) -> str:
        """The tools server agents connect to, on the console's public address (003 R-07)."""

        return f"{self.public_url.rstrip('/')}/mcp"

    @property
    def oauth_consent_url(self) -> str:
        return f"{self.public_url.rstrip('/')}/oauth/consent"

    @property
    def auth_callback_url(self) -> str:
        return f"{self.public_url.rstrip('/')}/api/v1/auth/callback"

    def is_allowed(self, login: str) -> bool:
        return login.lower() in self.allowed_logins


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
