"""Ed25519 signatures over canonical JSON. Every envelope and receipt in the network is signed."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical(obj: Any) -> bytes:
    """Deterministic JSON bytes: sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def sha256(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()


class KeyPair:
    """An agent's signing identity. The private key never leaves the agent."""

    def __init__(self) -> None:
        self._key = Ed25519PrivateKey.generate()
        self.public_hex = self._key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ).hex()

    def sign(self, payload: dict[str, Any]) -> str:
        return self._key.sign(canonical(payload)).hex()


def verify(payload: dict[str, Any], signature_hex: str, public_hex: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(
            bytes.fromhex(signature_hex), canonical(payload)
        )
        return True
    except (InvalidSignature, ValueError):
        return False
