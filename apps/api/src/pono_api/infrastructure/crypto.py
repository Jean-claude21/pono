"""Encryption at rest for provider credentials (Fernet, as in KYA-Platform's OAuth broker)."""

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class CredentialCipherError(RuntimeError):
    """A stored credential could not be decrypted: wrong key or tampered ciphertext."""


class CredentialCipher:
    """Encrypts and decrypts provider credentials. Plaintext never leaves this boundary as bytes."""

    def __init__(self, key: SecretStr) -> None:
        self._fernet = Fernet(key.get_secret_value().encode())

    def encrypt(self, plaintext: SecretStr) -> bytes:
        return self._fernet.encrypt(plaintext.get_secret_value().encode())

    def decrypt(self, ciphertext: bytes) -> SecretStr:
        try:
            return SecretStr(self._fernet.decrypt(ciphertext).decode())
        except InvalidToken as error:
            raise CredentialCipherError("stored credential cannot be decrypted") from error

    @staticmethod
    def generate_key() -> SecretStr:
        return SecretStr(Fernet.generate_key().decode())


__all__ = ["CredentialCipher", "CredentialCipherError"]
