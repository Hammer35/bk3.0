from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet():
    key = settings.PINTEREST_TOKEN_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("PINTEREST_TOKEN_ENCRYPTION_KEY is required for Pinterest OAuth.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise ImproperlyConfigured("PINTEREST_TOKEN_ENCRYPTION_KEY must be a valid Fernet key.") from error


def encrypt_token(value):
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_token(value):
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError) as error:
        raise ValueError("Pinterest token cannot be decrypted with the configured key.") from error
