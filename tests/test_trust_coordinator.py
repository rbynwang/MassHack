import numpy as np

from masshack.trust import TrustLayer, Limits, Command, verify_receipt
from masshack.coordinator import Offer, Signal, assign, split_revenue


def test_out_of_limit_command_is_blocked():
    t = TrustLayer(seed=b"\x01" * 32)
    lim = Limits(max_down_kw=3, max_up_kw=2, min_soc=0.3)
    too_big = Command("m1", "2026-01-20T08:00", "use_less", 5.0, "battery", 1.0)
    d = t.execute_or_block(too_big, lim, hour_of_day=8, soc_after=0.6)
    assert not d.accepted and "exceeds" in d.reason
    drains = Command("m1", "2026-01-20T08:00", "use_less", 2.0, "battery", 1.0)
    assert not t.execute_or_block(drains, lim, hour_of_day=8, soc_after=0.2).accepted
    ok = Command("m1", "2026-01-20T08:00", "use_less", 2.0, "battery", 1.0)
    assert t.execute_or_block(ok, lim, hour_of_day=8, soc_after=0.5).accepted


def test_receipt_signature_verifies_and_detects_tampering():
    t = TrustLayer(seed=b"\x02" * 32)
    cmd = Command("m2", "2025-07-29T16:00", "use_less", 4.0, "battery", 20.0)
    r = t.sign_receipt(cmd, delivered_kw=3.8, payment_usd=19.0)
    assert verify_receipt(r, t.public_key_hex())
    bad = dict(r, delivered_kw=10.0)
    assert not verify_receipt(bad, t.public_key_hex())


def test_merit_order_and_rebound_rejection():
    fc = np.array([10, 10, 20, 12, 10.0])
    sig = Signal(2, "use_less", 6.0, 5.0, ["test"])
    cheap_rebound = Offer("a", 2, "use_less", 5, 2.0, "precool", rebound_kw=np.array([0, 12, 0, 0, 0.0]))
    battery = Offer("b", 2, "use_less", 4, 4.0, "battery")
    pricier = Offer("c", 2, "use_less", 4, 12.0, "battery")
    acc, rej = assign([cheap_rebound, battery, pricier], sig, fc, current_peak_kw=20)
    ids = [o.member_id for o, _ in acc]
    assert "a" not in ids and ids[0] == "b"
    assert any(o.member_id == "a" and "peak" in why for o, why in rej)


def test_split_is_pro_rata_after_costs():
    s = split_revenue({"a": 3, "b": 1}, revenue_usd=100, member_costs={"a": 10, "b": 10})
    assert abs(s["a"] - (10 + 60)) < 1e-9 and abs(s["b"] - (10 + 20)) < 1e-9


def test_payout_never_exceeds_revenue():
    s = split_revenue({"a": 3, "b": 1}, revenue_usd=10, member_costs={"a": 30, "b": 10})
    assert abs(sum(s.values()) - 10) < 1e-9
