"""
Security subsystem providing Argon2id password hashing, verification,
and secure credential management for database and user authorization.
"""

import base64
import os
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from src.core.exceptions import InvalidCredentialsError


# Industry standard parameters for Argon2id
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain_password: str) -> str:
    """Hashes a plaintext password using Argon2id."""
    if not plain_password:
        raise ValueError("Password cannot be empty.")
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Checks if password hash needs to be upgraded based on hasher parameters."""
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True


def generate_session_token() -> str:
    """Generates a cryptographically strong 32-byte session token."""
    return secrets.token_hex(32)


def generate_idempotency_key() -> str:
    """Generates a unique idempotency key for transactions."""
    return f"txn_{secrets.token_urlsafe(16)}"
