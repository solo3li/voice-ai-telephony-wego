"""Symmetric encryption and decryption utilities for sensitive credentials."""
import base64
import hashlib
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet_instance() -> Fernet:
    """Generate or retrieve Fernet instance derived deterministically from DJANGO_SECRET_KEY."""
    raw_secret = getattr(settings, 'SECRET_KEY', 'default-django-secret-key')
    key_32 = hashlib.sha256(raw_secret.encode('utf-8')).digest()
    b64_key = base64.urlsafe_b64encode(key_32)
    return Fernet(b64_key)


def encrypt_secret(plain_text: str) -> str:
    """Encrypt plain text string into Fernet ciphertext token. If empty, return empty."""
    if not plain_text:
        return ""
    fernet = _get_fernet_instance()
    encrypted_bytes = fernet.encrypt(plain_text.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')


def decrypt_secret(cipher_text: str) -> str:
    """
    Decrypt Fernet ciphertext token back to plain text.
    If input is not valid ciphertext (e.g. legacy plain text password), gracefully returns it unchanged.
    """
    if not cipher_text:
        return ""
    try:
        fernet = _get_fernet_instance()
        decrypted_bytes = fernet.decrypt(cipher_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except (InvalidToken, Exception):
        # Fallback for legacy unencrypted records
        return cipher_text
