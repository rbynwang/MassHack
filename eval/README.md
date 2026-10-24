# eval/

Reproducible experiments behind `EVALUATION.md`. Run from the repo root (data defaults to `data/model_inputs`, override with `MASSHACK_DATA`).

| Script | Runtime (2 CPUs) | Output |
|---|---|---|
| `planner_gap.py [cache]` | ~5 min | `planner_gap.csv`: perfect-forecast vs forecast planner, per battery |
| `planner_variants.py [cache]` | ~4 min | `planner_variants.csv`, `planner_summary.json`: one forecast line vs scenarios |
| `forecast_eval.py` | ~10 min | `forecast_eval.csv`, `effects_delta.csv`: per-building vs pooled LightGBM, calibration, paired-difference action model |
| `wm_eval.py` | ~3 min | world model trained on the evaluation split |
| `make_evaluation.py` | seconds | `EVALUATION.md` (before = `before_demo.json`, now = `app/public/demo.json`) |

`[cache]` defaults to `app/forecast_cache.pkl`.
