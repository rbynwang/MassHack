"""Trust layer: member limits enforced in code, signed receipts, hash-chained log.

Every command from the coordinator passes `TrustLayer.execute_or_block`. A command outside the member's limits
is refused and logged; it never reaches the member's battery or building controls.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
import hashlib
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


@dataclass
class Limits:
    max_down_kw: float            # most the member lets the coordinator reduce its grid import
    max_up_kw: float              # most it lets the coordinator increase import (soak up surplus)
    min_soc: float = 0.20         # battery never drained below this for the collective
    allowed_hours: tuple = tuple(range(24))
    comfort_band_c: tuple = (20.0, 25.5)
    allow_building_modes: bool = True


@dataclass
class Command:
    member_id: str
    hour: str                     # ISO local hour
    direction: str                # "use_less" or "soak_up"
    kw: float                     # positive magnitude
    source: str                   # "battery" or a building mode name
    price_usd: float              # what the coordinator pays for delivery


@dataclass
class Decision:
    command: Command
    accepted: bool
    reason: str


class TrustLayer:
    def __init__(self, seed: bytes | None = None):
        self._key = Ed25519PrivateKey.from_private_bytes(seed) if seed else Ed25519PrivateKey.generate()
        self.public_key = self._key.public_key()
        self.log: list[dict] = []
        self._prev = "0" * 64

    def public_key_hex(self) -> str:
        return self.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def check(self, cmd: Command, limits: Limits, hour_of_day: int, soc_after: float | None, indoor_c: float | None = None) -> Decision:
        if hour_of_day not in limits.allowed_hours:
            return Decision(cmd, False, f"hour {hour_of_day} not allowed by member")
        cap = limits.max_down_kw if cmd.direction == "use_less" else limits.max_up_kw
        if cmd.kw > cap + 1e-9:
            return Decision(cmd, False, f"{cmd.kw:.2f} kW exceeds member limit {cap:.2f} kW")
        if cmd.source == "battery" and soc_after is not None and soc_after < limits.min_soc - 1e-9:
            return Decision(cmd, False, f"battery would fall to {soc_after:.0%}, below member minimum {limits.min_soc:.0%}")
        if cmd.source != "battery" and not limits.allow_building_modes:
            return Decision(cmd, False, "member does not allow building-mode control")
        if indoor_c is not None and not (limits.comfort_band_c[0] <= indoor_c <= limits.comfort_band_c[1]):
            return Decision(cmd, False, f"indoor {indoor_c:.1f} C outside comfort band")
        return Decision(cmd, True, "within limits")

    def execute_or_block(self, cmd: Command, limits: Limits, hour_of_day: int, soc_after=None, indoor_c=None) -> Decision:
        d = self.check(cmd, limits, hour_of_day, soc_after, indoor_c)
        self._append({"type": "command", "accepted": d.accepted, "reason": d.reason, **asdict(cmd)})
        return d

    def sign_receipt(self, cmd: Command, delivered_kw: float, payment_usd: float) -> dict:
        body = {
            "type": "receipt", "member_id": cmd.member_id, "hour": cmd.hour, "direction": cmd.direction,
            "source": cmd.source, "promised_kw": round(cmd.kw, 4), "delivered_kw": round(delivered_kw, 4),
            "payment_usd": round(payment_usd, 4), "prev_hash": self._prev,
        }
        msg = json.dumps(body, sort_keys=True).encode()
        body["signature"] = self._key.sign(msg).hex()
        body["hash"] = hashlib.sha256(msg).hexdigest()
        self._prev = body["hash"]
        self.log.append(body)
        return body

    def _append(self, entry: dict):
        msg = json.dumps({**entry, "prev_hash": self._prev}, sort_keys=True, default=str).encode()
        h = hashlib.sha256(msg).hexdigest()
        self.log.append({**entry, "prev_hash": self._prev, "hash": h})
        self._prev = h


def verify_receipt(receipt: dict, public_key_hex: str) -> bool:
    body = {k: v for k, v in receipt.items() if k not in ("signature", "hash")}
    msg = json.dumps(body, sort_keys=True).encode()
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    try:
        pub.verify(bytes.fromhex(receipt["signature"]), msg)
        return True
    except InvalidSignature:
        return False
