"""Property-based tests for the Commonwatt agent network (spec R3, R4).

1. No agent ever accepts a request beyond its own limits (guard and member decisions).
2. The pooled commitment never exceeds the sum of accepted amounts.
3. Payouts add up to settled earnings; receipts never pay for more than was committed.
4. A changed receipt or envelope is detected.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from commonwatt import signing
from commonwatt.members import build_neighborhood
from commonwatt.network import Bus, Registry, SignatureError
from commonwatt.protocol import AgentCard, Ask, Request
from commonwatt.scenario import run
from commonwatt.tools.mock import MockModelTool
from commonwatt.trust import Ledger, OwnerLimits, TrustGuard

WINDOW = [17, 18]
FAST = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
SLOW = settings(max_examples=4, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


@pytest.fixture(scope="module")
def twins():
    tw, _ = build_neighborhood()
    return tw


@pytest.fixture(scope="module")
def days():
    """A few full runs of the day with different ask sizes (each builds the neighborhood again)."""
    return [run(kw, WINDOW) for kw in (20.0, 60.0, 120.0)]


# ---------------------------------------------------------------- 1. limits
@FAST
@given(limit=st.floats(0, 50), kw=st.floats(0.01, 80), start=st.integers(0, 22),
       allowed=st.sets(st.integers(0, 23), min_size=1))
def test_guard_never_passes_a_request_over_the_owner_limit(limit, kw, start, allowed):
    g = TrustGuard("m1", OwnerLimits(max_reduce_kw=limit, allowed_hours=allowed), Ledger())
    window = [start, start + 1]
    req = Request(request_id="q", ask_id="a", member_id="m1", round=1, reduce_kw=kw, window=window,
                  price_usd_per_kwh=0.5)
    v = g.check_request(req)
    if v.ok:
        assert kw <= limit + 1e-6 and set(window) <= allowed
    else:
        assert kw > limit + 1e-6 or not set(window) <= allowed


@FAST
@given(i=st.integers(0, 18), kw=st.floats(0.05, 80), price=st.floats(0, 2))
def test_member_never_accepts_more_than_it_can_hold(twins, i, kw, price):
    tw = twins[i]
    tool = MockModelTool()

    class Ctx:
        twin = tw
    d = tool.decide(Ctx, kw, WINDOW, price)
    feasible = tw.plan(kw, WINDOW).kw
    assert d.decision in ("accept", "counter", "decline")
    if d.decision == "accept":
        assert d.kw <= kw + 1e-6 and d.kw <= feasible + 0.011
    if d.decision == "counter":
        assert d.kw < kw and d.kw <= feasible + 1e-6
    if price < tw.cost_per_kwh:
        assert d.decision == "decline"
    if d.decision != "decline" and tw.battery:
        assert d.predicted["battery_min_pct"] >= tw.battery["reserve_pct"] - 0.5


def test_guard_blocks_a_plan_that_breaks_comfort_or_reserve():
    g = TrustGuard("m1", OwnerLimits(max_reduce_kw=5, battery_reserve_pct=20, comfort_max_c=25.5), Ledger())
    assert not g.check_plan({"battery_min_pct": 12.0}).ok
    assert not g.check_plan({"indoor_c_range": [22.0, 26.4]}).ok
    assert g.check_plan({"battery_min_pct": 25.0, "indoor_c_range": [22.0, 25.0]}).ok


# ---------------------------------------------------------------- 2. pooling
def test_pooled_commitment_never_exceeds_accepted_amounts(days):
    for d in days:
        answered = {}
        for r in d["rounds"]:
            for q in r["requests"]:
                if q["decision"] in ("accept", "counter"):
                    answered[q["member"]] = q["kw"]          # the latest answer per member stands
        assert d["summary"]["pooled_kw"] <= sum(answered.values()) + 1e-6
        committed = sum(m["committed_kw"] for m in d["members"])
        assert abs(committed - d["summary"]["pooled_kw"]) < 1e-6
        for m in d["members"]:
            if m["committed_kw"] > 0:
                assert m["committed_kw"] <= m["offer_window_kw"] + 1e-6
                assert all(s["decision"] != "blocked" or s["kw"] == 0 for s in m["steps"])


def test_blocked_and_declined_members_are_never_assigned(days):
    for d in days:
        for m in d["members"]:
            final = m["steps"][-1]["decision"] if m["steps"] else None
            if final in ("blocked", "decline") and all(s["decision"] in ("blocked", "decline") for s in m["steps"]):
                assert m["assignment"] is None and m["receipt"] is None


# ---------------------------------------------------------------- 3. settlement
def test_payouts_add_up_to_settled_earnings(days):
    for d in days:
        price = d["ask"]["price_usd_per_kwh"]
        receipts = [m["receipt"] for m in d["members"] if m["receipt"]]
        paid = sum(r["payment_usd"] for r in receipts)
        assert abs(paid - d["summary"]["paid_usd"]) < 0.011
        assert abs(paid - sum(r["delivered_kwh"] for r in receipts) * price) <= 0.006 * len(receipts) + 1e-9
        for r in receipts:
            assert r["delivered_kwh"] <= r["committed_kw"] * len(r["window"]) + 1e-6
            assert r["payment_usd"] >= 0


@SLOW
@given(kw=st.floats(5, 150))
def test_commons_never_promises_more_than_asked_plus_margin(kw):
    d = run(kw, WINDOW)
    assert d["summary"]["pooled_kw"] <= kw * 1.1 + 0.5
    assert d["summary"]["ledger"].endswith("receipts verified")


# ---------------------------------------------------------------- 4. tampering
def test_changed_receipt_is_detected(days):
    led = Ledger()
    g = TrustGuard("m1", OwnerLimits(max_reduce_kw=5), led)
    g.settle("a", WINDOW, 2.0, [5.0] * 24, [3.0] * 24, 0.9, None, None)
    g.settle("b", WINDOW, 1.0, [5.0] * 24, [4.0] * 24, 0.9, None, None)
    assert led.verify()[0]
    led.receipts[0] = led.receipts[0].model_copy(update={"payment_usd": 99.0})
    ok, why = led.verify()
    assert not ok and "bad signature" in why


def test_envelope_with_wrong_key_is_rejected():
    reg = Registry()
    real, fake = signing.KeyPair(), signing.KeyPair()
    reg.register(AgentCard(agent_id="grid", role="grid", display_name="g", owner="o", commons="c",
                           public_key=real.public_hex))
    bus = Bus(reg)
    ask = Ask(ask_id="a", direction="reduce", kw=10, window=WINDOW, price_usd_per_kwh=0.5, reason="t")
    bus.send("grid", real, "coordinator", ask, "ok")
    with pytest.raises(SignatureError):
        bus.send("grid", fake, "coordinator", ask, "forged")
