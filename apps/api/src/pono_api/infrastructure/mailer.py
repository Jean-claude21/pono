"""Alert emails over generic SMTP (research R-10). No provider SDK, no coupling.

Without SMTP settings the mailer is unconfigured: alerts stay visible in the workshop and the
health probe says email is not configured.
"""

import asyncio
import smtplib
from email.message import EmailMessage

from pydantic import SecretStr

from pono_api.application.ports import RaisedAlert, Recipient

METRIC_NAMES = {
    "fr": {
        "hosting_bandwidth_bytes": "bande passante de l'hébergement",
        "db_compute_seconds": "temps de calcul de la base",
        "db_storage_bytes": "stockage de la base",
        "db_transfer_bytes": "transfert de la base",
    },
    "en": {
        "hosting_bandwidth_bytes": "hosting bandwidth",
        "db_compute_seconds": "database compute time",
        "db_storage_bytes": "database storage",
        "db_transfer_bytes": "database transfer",
    },
}
SOURCES = {
    "fr": {
        "account_plan": "l'offre de ton compte",
        "free_tier_estimate": "l'offre gratuite (estimée)",
    },
    "en": {
        "account_plan": "your account's plan",
        "free_tier_estimate": "the free tier (estimated)",
    },
}


def compose(recipient: Recipient, alert: RaisedAlert, sender: str) -> EmailMessage:
    """The alert in the recipient's language; French when they never chose one."""

    locale = recipient.locale if recipient.locale in ("fr", "en") else "fr"
    metric = METRIC_NAMES[locale].get(alert.metric, alert.metric)
    source = SOURCES[locale].get(alert.limit_source, alert.limit_source)
    percent = round(alert.used / alert.limit * 100) if alert.limit else alert.threshold
    subject_target = alert.project_name or metric
    if locale == "fr":
        subject = f"Pono · {subject_target} : {metric} à {percent} %"
        body = (
            f"Le quota « {metric} » a dépassé {alert.threshold} % de {source}.\n"
            f"Consommation actuelle : {percent} %.\n\n"
            "Au-delà de la limite, le fournisseur peut mettre le service en pause.\n"
            "Le détail est dans ton atelier Pono.\n"
        )
    else:
        subject = f"Pono · {subject_target}: {metric} at {percent}%"
        body = (
            f'The "{metric}" quota passed {alert.threshold}% of {source}.\n'
            f"Current usage: {percent}%.\n\n"
            "Beyond the limit, the provider may pause the service.\n"
            "The detail is in your Pono workshop.\n"
        )
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient.email
    message["Subject"] = subject
    message.set_content(body)
    return message


class SmtpMailer:
    def __init__(
        self,
        host: str | None,
        port: int,
        username: str | None,
        password: SecretStr | None,
        sender: str | None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender

    @property
    def configured(self) -> bool:
        return bool(self._host and self._sender)

    async def send_alert(self, recipient: Recipient, alert: RaisedAlert) -> None:
        if not self.configured:
            return
        assert self._sender is not None
        message = compose(recipient, alert, self._sender)
        await asyncio.to_thread(self._send, message)

    def _send(self, message: EmailMessage) -> None:
        assert self._host is not None
        with smtplib.SMTP(self._host, self._port, timeout=20) as client:
            client.starttls()
            if self._username and self._password:
                client.login(self._username, self._password.get_secret_value())
            client.send_message(message)


__all__ = ["SmtpMailer", "compose"]
