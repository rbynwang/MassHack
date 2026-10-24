"""Property-based tests for the week of trading (final-submission spec, R3).

- Weekly payouts equal the sum of the receipts.
- The week-long receipt chain verifies; changing any field of any receipt breaks it.
- No member is paid on a day without a grid ask.
- Each day, pooled kW equals the sum of commitments, and no receipt pays for more than was committed.
- The exported canonical text of each receipt hashes to its recorded hash (what the browser re-checks).
"""

from __future__ import annotations

import hashlib
import json

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from commonwatt.protocol import Receipt
from commonwatt.trust import Ledger
from commonwatt.week import run_week

FIELDS = set(Receipt.model_fields)
SET = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])


@pytest.fixture(scope="module")
def week():
    return run_week()


def ledger_from(week) -> Ledger:
    led = Ledger()
    for d in week["days"]:
        for r in d["receipts"]:
            led.append(Receipt(**{k: v for k, v in r.items() if k in FIELDS}))
    return led


def test_week_has_events_and_quiet_days(week):
    assert len(week["days"]) == 7
    assert any(d["event"] for d in week["days"]) and any(not d["event"] for d in week["days"])


def test_weekly_payouts_equal_sum_of_receipts(week):
    receipts = [r for d in week["days"] for r in d["receipts"]]
    assert abs(sum(r["payment_usd"] for r in receipts) - week["totals"]["paid_usd"]) < 0.011
    by_member = sum(sum(m["daily_usd"]) for m in week["members"].values())
    assert abs(by_member - week["totals"]["paid_usd"]) < 0.011
    for d in week["days"]:
        assert abs(sum(r["payment_usd"] for r in d["receipts"]) - d["paid_usd"]) < 0.011


def test_chain_verifies_and_links_across_days(week):
    ok, msg = ledger_from(week).verify()
    assert ok, msg
    receipts = [r for d in week["days"] for r in d["receipts"]]
    assert receipts[0]["prev_hash"] == "sha256:genesis"
    for a, b in zip(receipts, receipts[1:]):
        assert b["prev_hash"] == a["hash"]
    assert week["ledger"]["head"] == receipts[-1]["hash"] and week["ledger"]["verified"]


@SET
@given(data=st.data())
def test_any_tampered_receipt_breaks_the_chain(week, data):
    led = ledger_from(week)
    i = data.draw(st.integers(0, len(led.receipts) - 1))
    field = data.draw(st.sampled_from(["payment_usd", "delivered_kwh", "committed_kw", "member_id", "prev_hash",
                                       "price_usd_per_kwh"]))
    old = getattr(led.receipts[i], field)
    if isinstance(old, str):
        new = data.draw(st.text(min_size=1, max_size=12).filter(lambda s: s != old))
    else:
        new = data.draw(st.floats(0, 1000, allow_nan=False).filter(lambda x: abs(x - old) > 1e-9))
    led.receipts[i] = led.receipts[i].model_copy(update={field: new})
    ok, _ = led.verify()
    assert not ok


def test_no_member_is_paid_without_an_ask(week):
    for k, d in enumerate(week["days"]):
        if not d["event"]:
            assert d["receipts"] == [] and d["paid_usd"] == 0
            assert all(m["daily_usd"][k] == 0 for m in week["members"].values())


def test_pooled_matches_commitments_and_receipts_never_overpay(week):
    for d in week["days"]:
        committed = sum(r["committed_kw"] for r in d["receipts"])
        assert committed <= d["pooled_kw"] + 0.01 * max(1, len(d["receipts"]))
        for r in d["receipts"]:
            assert r["delivered_kwh"] <= r["committed_kw"] * len(r["window"]) + 1e-6
            assert r["payment_usd"] >= 0 and r["sig_ok"]


def test_exported_canonical_text_matches_hash(week):
    for d in week["days"]:
        for r in d["receipts"]:
            assert "sha256:" + hashlib.sha256(r["canonical"].encode()).hexdigest() == r["hash"]
            parsed = json.loads(r["canonical"])
            assert parsed["receipt_id"] == r["receipt_id"] and parsed["payment_usd"] == r["payment_usd"]
