"""homesim command line: generate a synthetic single-family home dataset.

Example:
    uv run homesim --n-homes 200 --mode balanced --out data/synthetic/dev-balanced
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from homesim import __version__, load_config
from homesim.behavior import simulate_behavior
from homesim.calibration import CalibrationAccumulator, format_checks, run_checks
from homesim.inputs import load_inputs
from homesim.physics import simulate_physics
from homesim.plots import plot_home_weeks
from homesim.population import sample_homes
from homesim.writer import write_homes, write_hourly_batch, write_inputs

NOT_YET_GENERATED = [
    "flex_down_kw", "flex_up_kw", "flex_duration_h", "event_id", "responded", "delivered_kw",
    "actual_load_kw", "counterfactual_load_kw", "oracle_battery_kw", "is_missing", "is_anomaly",
]


def _pick_plot_home(homes: pd.DataFrame) -> str:
    pref = homes[(homes["heating_type"] == "heat_pump") & (homes["pv_kw_dc"] > 0) & (homes["n_ev"] > 0)]
    return (pref if len(pref) else homes)["home_id"].iloc[0]


def _datacard(cfg: dict, args, homes: pd.DataFrame, checks: dict, runtime_s: float) -> str:
    counts = homes["home_type"].value_counts().to_string()
    return f"""# homesim dataset card — {args.out.name}

**Synthetic data. Only weather and PV inputs are measured (HouseZero).**

- homesim version: {__version__}; config version: {cfg['version']}; seed: {cfg['seed']}
- Mode: {args.mode}; homes: {len(homes)}; hours per home: 9,504 (2025-05-01 to 2026-05-31 local)
- Generated in {runtime_s:.0f} s. Build order steps 1-2 of the guideline (simulator + population + calibration).

## Inputs
- HouseZero hourly outdoor temperature, solar radiation and PV (Harvard CGBC, CC BY 4.0;
  DOIs 10.6084/m9.figshare.30260233.v1 and 10.6084/m9.figshare.32790984.v1).
- Gaps in inputs are filled (short gaps interpolated, long gaps from a same-hour climatology,
  PV gaps from irradiance). Filled hours are flagged in `weather_inputs.parquet`.
- PV is HouseZero PV / 15 kW nameplate x home kW_dc x (derate / {cfg['inputs']['pv_reference_derate']}) x (1 + per-home noise).

## Files
- `homes.parquet`: one row per home (guideline columns plus `capacitance_kwh_per_c`,
  `cooling_capacity_kw`, `pv_noise_frac`, `has_electric_water_heater`, `internal_gain_occupied_kw`,
  `window_aperture_m2`, `furnace_blower_kw`, `window_ac_fraction`).
- `hourly/`: Parquet partitioned by `home_type` and `month` (local). Power in kW (hourly mean).
  `base_kw` = all non-HVAC, non-EV household load. `heat_pump_kw` covers heat-pump heating and cooling.
  `blower_kw` = gas furnace blower (not in the guideline schema). `grid_export_kw` is a positive magnitude.
  Battery is not dispatched.
- `weather_inputs.parquet`, `config.yaml` (resolved), `calibration.json`, `home_<id>_weeks.png`.
- Not generated yet (guideline steps 3-5, section 7): {', '.join(NOT_YET_GENERATED)}; `events.parquet`.

## Splits
Home split stored in `homes.split` ({cfg['splits']['home_fractions']}). Apply the time split on top:
train homes {cfg['splits']['months']['train']}, val homes {cfg['splits']['months']['val']},
test homes {cfg['splits']['months']['test']} (inclusive months).

## Home types
```
{counts}
```

## Calibration
```
{format_checks(checks)}
```
Full values: `calibration.json`. Baselines: National Grid R-1 load shape (same dates), EIA 2024 Table 5A,
NREL ResStock 2024.2 MA single-family detached (2018 weather). See `data/baseline/README.md`.
"""


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic single-family homes (homesim).")
    p.add_argument("--n-homes", type=int, default=200)
    p.add_argument("--mode", choices=["representative", "balanced"], default="balanced")
    p.add_argument("--seed", type=int, default=None, help="Overrides config seed.")
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    t0 = time.time()
    cfg = load_config(args.config)
    if args.seed is not None:
        cfg["seed"] = args.seed
    seed = int(cfg["seed"])
    if args.out is None:
        args.out = args.root / "data" / "synthetic" / f"{cfg['version']}-{args.mode}-{args.n_homes}"
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / "hourly").exists() and any((args.out / "hourly").iterdir()):
        raise SystemExit(f"{args.out}/hourly already has data; choose a new --out.")
    comp = cfg["output"]["compression"]

    inp = load_inputs(cfg, args.root)
    rng = np.random.default_rng(seed)
    homes = sample_homes(cfg, args.n_homes, args.mode, rng)
    plot_id = _pick_plot_home(homes)
    acc = CalibrationAccumulator(inp.n_hours)

    bs = int(cfg["output"]["batch_size"])
    batch_seeds = np.random.SeedSequence(seed).spawn((len(homes) + bs - 1) // bs)
    plot_frame = None
    for b, start in enumerate(range(0, len(homes), bs)):
        batch = homes.iloc[start:start + bs].reset_index(drop=True)
        brng = np.random.default_rng(batch_seeds[b])
        beh = simulate_behavior(cfg, batch, inp, brng)
        phy = simulate_physics(cfg, batch, inp, beh)

        total = beh.base_kw + phy.heat_pump_kw + phy.backup_heat_kw + phy.ac_kw + phy.blower_kw + beh.ev_kw
        net = total - phy.pv_kw
        cols = {
            "temp_out_c": np.broadcast_to(inp.temp_out_c, total.shape),
            "t_in_c": phy.t_in_c,
            "base_kw": beh.base_kw,
            "heat_pump_kw": phy.heat_pump_kw,
            "backup_heat_kw": phy.backup_heat_kw,
            "ac_kw": phy.ac_kw,
            "blower_kw": phy.blower_kw,
            "ev_kw": beh.ev_kw,
            "pv_kw": phy.pv_kw,
            "total_load_kw": total,
            "grid_net_kw": net,
            "grid_import_kw": np.maximum(net, 0.0),
            "grid_export_kw": np.maximum(-net, 0.0),
        }
        write_hourly_batch(b, batch, inp, cols, beh.occupied, args.out, comp)
        acc.add(batch, inp, total, phy.heat_pump_kw, net)

        if plot_id in set(batch["home_id"]):
            i = int(np.flatnonzero(batch["home_id"].to_numpy() == plot_id)[0])
            plot_frame = pd.DataFrame({c: np.asarray(v[i]) for c, v in cols.items()},
                                      index=pd.DatetimeIndex(inp.frame["timestamp_local"]))
        print(f"batch {b + 1}: homes {start}-{start + len(batch) - 1} done ({time.time() - t0:.0f} s)")

    write_homes(homes, args.out, comp)
    write_inputs(inp, args.out, comp)

    checks = run_checks(acc, inp, args.root)
    (args.out / "calibration.json").write_text(json.dumps(checks, indent=2))
    resolved = dict(cfg)
    resolved["run"] = {"n_homes": args.n_homes, "mode": args.mode, "seed": seed, "homesim_version": __version__}
    (args.out / "config.yaml").write_text(yaml.safe_dump(resolved, sort_keys=False))

    if plot_frame is not None:
        home_row = homes.loc[homes["home_id"] == plot_id].iloc[0]
        plot_home_weeks(plot_frame, home_row, args.out / f"home_{plot_id}_weeks.png")

    runtime = time.time() - t0
    (args.out / "DATACARD.md").write_text(_datacard(cfg, args, homes, checks, runtime))
    print()
    print(format_checks(checks))
    print(f"\nWrote {args.out} in {runtime:.0f} s")


if __name__ == "__main__":
    main()
