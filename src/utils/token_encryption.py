"""
Token Encryption Utility
========================

Provides encryption/decryption for tokens stored in database.

Uses Fernet (symmetric encryption) for encrypting tokens at rest.
Fernet is built on top of AES-128 in CBC mode with HMAC.

Security:
- Tokens are encrypted before storing in database
- Encryption key is stored in environment variable
- Tokens are decrypted only when needed
- Prevents token exposure if database is compromised
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Global Fernet instance (initialized on first use)
_fernet_instance: Optional[Fernet] = None


def _get_encryption_key() -> bytes:
    """
    Get or generate encryption key from environment.

    If TOKEN_ENCRYPTION_KEY is set, uses it directly (base64 encoded).
    Otherwise, generates a key from a passphrase (less secure, for development).

    Returns:
        Encryption key as bytes
    """
    key_env = os.getenv("TOKEN_ENCRYPTION_KEY")

    if key_env:
        # Use provided key (should be base64-encoded Fernet key)
        try:
            # Fernet.generate_key() returns base64-encoded bytes (44 bytes)
            # Fernet constructor expects base64-encoded bytes, NOT decoded bytes
            # So we just convert the string to bytes - Fernet will handle the decoding
            key_str = key_env.strip()

            # Fernet expects base64-encoded bytes (44 bytes), not raw 32 bytes
            # Convert string to bytes - Fernet will decode it internally
            key_bytes = key_str.encode("utf-8")

            # Validate it's the right length (44 bytes for base64-encoded 32-byte key)
            if len(key_bytes) != 44:
                raise ValueError(
                    f"Fernet key must be 44 bytes (base64-encoded), got {len(key_bytes)} bytes"
                )

            return key_bytes
        except Exception as e:
            logger.error(f"Failed to process TOKEN_ENCRYPTION_KEY: {e}")
            raise ValueError(f"Invalid TOKEN_ENCRYPTION_KEY format: {e}")

    # Fallback: Generate from passphrase (less secure, for development only)
    passphrase = os.getenv(
        "TOKEN_ENCRYPTION_PASSPHRASE", "default-dev-passphrase-change-in-production"
    )
    salt = os.getenv("TOKEN_ENCRYPTION_SALT", "default-salt").encode()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
    logger.warning(
        "⚠️ Using passphrase-based encryption key (less secure). Set TOKEN_ENCRYPTION_KEY for production."
    )
    return key


def _get_fernet() -> Fernet:
    """Get or create Fernet instance for encryption."""
    global _fernet_instance
    if _fernet_instance is None:
        key = _get_encryption_key()
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_token(token: str) -> str:
    """
    Encrypt a token for storage in database.

    Args:
        token: Plain text token to encrypt

    Returns:
        Encrypted token (base64-encoded bytes as string)
    """
    if not token:
        return token

    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(token.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Failed to encrypt token: {e}")
        raise ValueError(f"Token encryption failed: {e}")


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt a token from database.

    Args:
        encrypted_token: Encrypted token from database

    Returns:
        Decrypted token (plain text)
    """
    if not encrypted_token:
        return encrypted_token

    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}")
        raise ValueError(f"Token decryption failed: {e}")


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key (for initial setup).

    Returns:
        Base64-encoded Fernet key (safe to store in environment variable)
    """
    key = Fernet.generate_key()
    return key.decode()
