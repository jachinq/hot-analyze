"""API Key Fernet 加解密。"""

from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = os.getenv("ENCRYPT_KEY", "").strip()
    if not key:
        return None
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        logger.warning("invalid ENCRYPT_KEY, api_key will store plaintext: %s", e)
        return None
    return _fernet


def encrypt_secret(plain: str) -> str:
    if not plain:
        return plain
    f = _get_fernet()
    if f is None:
        return plain
    return f.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher: str) -> str:
    if not cipher:
        return cipher
    f = _get_fernet()
    if f is None:
        return cipher
    try:
        return f.decrypt(cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # 可能是明文历史数据
        return cipher


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    return "****"
