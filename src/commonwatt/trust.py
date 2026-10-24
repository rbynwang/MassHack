"""Trust guards and the receipt ledger.

A guard sits at each member's edge, in front of its agent. It holds the owner's private limits (the coordinator
never sees them), blocks requests that break them, checks the agent's planned action before it runs, measures
delivery against the member's own no-event forecast, and signs a receipt. Receipts form a hash chain, so a
changed or removed receipt is detectable by anyone holding the guards' public keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from commonwatt import signing
from commonwatt.protocol import Receipt, Request


@dataclass
class OwnerLimits:
    """Private to the member. The owner can change them at any time."""
    max_reduce_kw: float
    allowed_hours: set[int] = field(default_factory=lambda: set(range(24)))
    battery_reserve_pct: float | None = None
    comfort_max_c: float | None = None


@dataclass
class GuardVerdict:
    ok: bool
    reason: str


class Ledger:
    def __init__(self) -> None:
        self.receipts: list[Receipt] = []

    @property
    def head(self) -> str:
        return signing.sha256(self.receipts[-1].model_dump(mode="json")) if self.receipts else "sha256:genesis"

    def append(self, r: Receipt) -> None:
        self.receipts.append(r)

    def verify(self) -> tuple[bool, str]:
        """Check every signature and every link of the chain."""
        prev = "sha256:genesis"
        for r in self.receipts:
            body = r.model_dump(mode="json", exclude={"signature"})
            if r.prev_hash != prev:
                return False, f"{r.receipt_id}: chain broken"
            if not signing.verify(body, r.signature, r.guard_public_key):
                return False, f"{r.receipt_id}: bad signature"
            prev = signing.sha256(r.model_dump(mode="json"))
        return True, f"{len(self.receipts)} receipts verified"


class TrustGuard:
    def __init__(self, member_id: str, limits: OwnerLimits, ledger: Ledger) -> None:
        self.member_id = member_id
        self.limits = limits
        self.ledger = ledger
        self.keys = signing.KeyPair()

    def check_request(self, req: Request) -> GuardVerdict:
        lim = self.limits
        if req.member_id != self.member_id:
            return GuardVerdict(False, "addressed to another member")
        if req.reduce_kw > lim.max_reduce_kw + 1e-6:
            return GuardVerdict(False, f"exceeds {self.member_id}'s limit")
        if not set(req.window) <= lim.allowed_hours:
            return GuardVerdict(False, "outside the owner's allowed hours")
        return GuardVerdict(True, "within limits")

    def check_plan(self, predicted: dict) -> GuardVerdict:
        lim = self.limits
        if lim.battery_reserve_pct is not None and predicted.get("battery_min_pct") is not None:
            if predicted["battery_min_pct"] < lim.battery_reserve_pct - 0.5:
                return GuardVerdict(False, "plan would drain the battery below the owner's reserve")
        if lim.comfort_max_c is not None and predicted.get("indoor_c_range"):
            if predicted["indoor_c_range"][1] > lim.comfort_max_c + 0.05:
                return GuardVerdict(False, "plan would leave the owner's comfort band")
        return GuardVerdict(True, "plan within limits")

    def settle(self, ask_id: str, window: list[int], committed_kw: float, counterfactual_kw: list[float],
               actual_kw: list[float], price: float, indoor_f: list[float] | None,
               battery_min_pct: float | None) -> Receipt:
        """Delivered energy = no-event forecast minus metered draw in the window, capped at the commitment."""
        delivered = sum(max(0.0, counterfactual_kw[h] - actual_kw[h]) for h in window)
        eligible = min(delivered, committed_kw * len(window))
        unsigned = Receipt(
            receipt_id=f"r-{ask_id}-{self.member_id}", ask_id=ask_id, member_id=self.member_id, window=window,
            committed_kw=round(committed_kw, 3), delivered_kwh=round(eligible, 3), price_usd_per_kwh=price,
            payment_usd=round(eligible * price, 2), indoor_f_range=indoor_f, battery_min_pct=battery_min_pct,
            prev_hash=self.ledger.head, guard_public_key=self.keys.public_hex)
        sig = self.keys.sign(unsigned.model_dump(mode="json", exclude={"signature"}))
        r = unsigned.model_copy(update={"signature": sig})
        self.ledger.append(r)
        return r
