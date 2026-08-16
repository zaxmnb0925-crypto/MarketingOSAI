from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class OAuthTokenDecryptionError(RuntimeError):
    pass


class OAuthTokenCipher:
    def __init__(self) -> None:
        key = settings.oauth_token_encryption_key.encode()
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise ValueError("OAuth token cannot be empty")

        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            raise ValueError("OAuth ciphertext cannot be empty")

        try:
            plaintext = self._fernet.decrypt(ciphertext.encode())
        except InvalidToken as exc:
            raise OAuthTokenDecryptionError(
                "Unable to decrypt OAuth token"
            ) from exc

        return plaintext.decode()


oauth_token_cipher = OAuthTokenCipher()
