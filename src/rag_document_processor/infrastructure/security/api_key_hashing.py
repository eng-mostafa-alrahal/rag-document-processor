from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

API_KEY_PREFIX = "rag_"
_PREFIX_DISPLAY_LEN = 12


@dataclass(frozen=True, slots=True)
class GeneratedApiKey:
    raw_key: str
    key_prefix: str
    key_hash: str


def hash_api_key(raw_key: str) -> str:
    """Return a stable one-way hash of the raw key for storage/lookup."""
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def generate_api_key() -> GeneratedApiKey:
    """Create a new random API key.

    Returns the raw key (shown to the caller exactly once), a short non-secret
    display prefix, and the hash to persist.
    """
    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return GeneratedApiKey(
        raw_key=raw_key,
        key_prefix=raw_key[:_PREFIX_DISPLAY_LEN],
        key_hash=hash_api_key(raw_key),
    )
