"""A week of trading: June 20-26, 2025, with receipts chained across days.

    uv run commonwatt-week        # writes app/data/week.json and app/data/week.js (window.CW_WEEK)

Event days and their size come from the synthetic ConnectedSolutions-style schedule in
data/training_2025_2026/dr_events_2025.csv (picked from real ISO-NE peak load). The schedule's window is 3-6 PM;
every ask here uses the story's 5-7 PM window, when the Boston-zone price peaks. The ask is 60 kW on June 24 and
scales with each day's ISO-NE load (selection_load_mw). The library is not a member before June 24, joins live on
June 24 and is a member after. home_03's owner tightens its private limit on June 24 only. Every member's trust
guard keeps one signing key all week, and all receipts go into one hash-chained ledger.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from commonwatt import __version__, signing
from commonwatt.members import EVENT_DAY, ROOT, TRAIN, build_neighborhood
from commonwatt.scenario import KIND_LABEL, LATE_JOINER, run
from commonwatt.trust import Ledger

DAYS = [str(d.date()) for d in pd.date_range("2025-06-20", "2025-06-26")]
WINDOW = [17, 18]
ASK_KW_ON_EVENT_DAY = 60.0


def dr_schedule() -> pd.DataFrame:
    dr = pd.read_csv(TRAIN / "dr_events_2025.csv")
    return dr[dr["date"].isin(DAYS)].set_index("date")


def library_state(day: str) -> str:
    return "absent" if day < EVENT_DAY else ("joins" if day == EVENT_DAY else "member")


def receipt_record(r, day: str) -> dict:
    full = r.model_dump(mode="json")
    unsigned = r.model_dump(mode="json", exclude={"signature"})
    canon = signing.canonical(full).decode()
    return {**full, "day": day, "hash": signing.sha256(full), "canonical": canon,
            "signed_bytes": signing.canonical(unsigned).decode(),
            "sig_ok": signing.verify(unsigned, r.signature, r.guard_public_key)}


def run_week(tool_spec: str | None = None) -> dict:
    dr = dr_schedule()
    ref_load = float(dr.loc[EVENT_DAY, "selection_load_mw"])
    ledger, guard_keys = Ledger(), {}
    days, members = [], {}
    for k, day in enumerate(DAYS):
        lib = library_state(day)
        if day in dr.index:
            load_mw = float(dr.loc[day, "selection_load_mw"])
            ask_kw = round(ASK_KW_ON_EVENT_DAY * load_mw / ref_load, 1)
            n0 = len(ledger.receipts)
            out = run(ask_kw, WINDOW, tool_spec, day=day, ledger=ledger, library=lib,
                      override=(day == EVENT_DAY), guard_keys=guard_keys)
            S = out["summary"]
            reqs = [q for r in out["rounds"] for q in r["requests"]]
            rec = [receipt_record(r, day) for r in ledger.receipts[n0:]]
            days.append({
                "day": day, "event": True, "label": "simulated", "ask_kw": ask_kw, "window": WINDOW,
                "schedule_window_local": [dr.loc[day, "start_local"][11:16], dr.loc[day, "end_local"][11:16]],
                "iso_ne_load_mw": load_mw, "price_usd_per_kwh": out["ask"]["price_usd_per_kwh"],
                "reason": out["ask"]["reason"], "pooled_kw": S["pooled_kw"], "delivered_kwh": S["delivered_kwh"],
                "paid_usd": S["paid_usd"], "members_paid": S["members_paid"], "rounds": S["rounds"],
                "peak_kw": S["peak_kw"], "peak_hour": S["peak_hour"], "window_kw_mean": S["window_kw_mean"],
                "blocked": [{"member": q["member"], "reason": q["reason"]} for q in reqs if q["decision"] == "blocked"],
                "declined": [{"member": q["member"], "reason": q["reason"]} for q in reqs if q["decision"] == "decline"],
                "countered": [{"member": q["member"], "asked_kw": q["asked_kw"], "kw": q["kw"], "reason": q["reason"]}
                              for q in reqs if q["decision"] == "counter"],
                "library": lib, "tool": out["tool"], "trained_model_members": S["model"]["trained_members"],
                "series": {k2: out["series"][k2] for k2 in ("no_opt", "alone", "network")},
                "receipts": rec,
            })
            mem_list = out["members"]
        else:
            twins, _ = build_neighborhood(day)
            if lib == "absent":
                twins = [t for t in twins if t.member_id != LATE_JOINER]
            no_opt, alone = sum(t.planned_kw for t in twins), sum(t.alone() for t in twins)
            days.append({
                "day": day, "event": False, "label": "simulated", "ask_kw": 0.0, "window": None,
                "pooled_kw": 0.0, "delivered_kwh": 0.0, "paid_usd": 0.0, "members_paid": 0, "rounds": 0,
                "peak_kw": {"no_opt": round(float(no_opt.max()), 1), "alone": round(float(alone.max()), 1),
                            "network": None},
                "peak_hour": {"no_opt": int(no_opt.argmax()), "alone": int(alone.argmax()), "network": None},
                "blocked": [], "declined": [], "countered": [], "library": lib, "receipts": [],
                "series": {"no_opt": [round(float(x), 1) for x in no_opt],
                           "alone": [round(float(x), 1) for x in alone], "network": None},
            })
            mem_list = [{"id": t.member_id, "kind": t.kind, "kind_label": KIND_LABEL[t.kind]} for t in twins]
        for m in mem_list:
            e = members.setdefault(m["id"], {"kind": m["kind"], "kind_label": m["kind_label"],
                                             "daily_usd": [0.0] * len(DAYS), "daily_kwh": [0.0] * len(DAYS),
                                             "member_days": [False] * len(DAYS)})
            e["member_days"][k] = True
        for r in days[-1]["receipts"]:
            members[r["member_id"]]["daily_usd"][k] = round(r["payment_usd"], 2)
            members[r["member_id"]]["daily_kwh"][k] = round(r["delivered_kwh"], 3)
    ok, msg = ledger.verify()
    paid = round(sum(d["paid_usd"] for d in days), 2)
    return {
        "version": __version__, "label": "simulated", "days_list": DAYS, "window": WINDOW, "days": days,
        "members": members,
        "ledger": {"receipts": len(ledger.receipts), "verified": ok, "message": msg, "head": ledger.head},
        "totals": {"paid_usd": paid, "delivered_kwh": round(sum(d["delivered_kwh"] for d in days), 1),
                   "event_days": sum(d["event"] for d in days)},
        "notes": [
            "Demand-response days are a synthetic ConnectedSolutions-style schedule picked from real ISO-NE peak load.",
            "Asks use the 5-7 PM window (the schedule lists 3-6 PM); size scales with that day's ISO-NE load, 60 kW on June 24.",
            "The trained model's forecast cache covers June 24 only; on other days members use the labeled stand-in.",
            "Weather, HouseZero and Boston Public Library inputs are measured; members, batteries and payments are simulated or assumptions.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Simulate June 20-26, 2025 with receipts chained across days.")
    p.add_argument("--tool", type=str, default=None)
    args = p.parse_args()
    out = run_week(args.tool)
    d = ROOT / "app" / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / "week.json").write_text(json.dumps(out, indent=1))
    (d / "week.js").write_text("window.CW_WEEK = " + json.dumps(out) + ";\n")
    for day in out["days"]:
        pk = day["peak_kw"]
        print(f"{day['day']}  event={day['event']!s:5}  ask={day['ask_kw']:5.1f} kW  pooled={day['pooled_kw']:5.1f}  "
              f"paid=${day['paid_usd']:7.2f}  members_paid={day['members_paid']:2d}  peak alone {pk['alone']} "
              f"network {pk['network']}  blocked={[b['member'] for b in day['blocked']]}  library={day['library']}")
    L = out["ledger"]
    print(f"Ledger: {L['receipts']} receipts, verified={L['verified']} ({L['message']}); week paid ${out['totals']['paid_usd']}")
    print(f"Wrote {d / 'week.js'}")


if __name__ == "__main__":
    main()
