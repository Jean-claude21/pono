"""The production wiring of the provider ports, shared by the service and the worker."""

from pono_api.application.refresh_project import Providers
from pono_api.config import Settings
from pono_api.infrastructure.chat import TelegramMessenger
from pono_api.infrastructure.crypto import CredentialCipher
from pono_api.infrastructure.link_checker import HttpLinkChecker
from pono_api.infrastructure.mailer import SmtpMailer
from pono_api.infrastructure.manifests import RepositoryManifests
from pono_api.infrastructure.providers.github import GitHubCodeHost
from pono_api.infrastructure.providers.registry import ProviderRegistry


def default_providers(settings: Settings) -> Providers:
    private_key = settings.github_private_key_pem
    return Providers(
        code_host=GitHubCodeHost(app_id=settings.github_app_id, private_key=private_key)
        if settings.github_app_id and private_key
        else None,
        factory=ProviderRegistry(
            CredentialCipher(settings.encryption_key) if settings.encryption_key else None
        ),
        manifests=RepositoryManifests(),
        links=HttpLinkChecker(),
        mailer=SmtpMailer(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_username,
            settings.smtp_password,
            settings.smtp_from,
        ),
        messenger=TelegramMessenger(settings.telegram_bot_token),
    )


__all__ = ["default_providers"]
