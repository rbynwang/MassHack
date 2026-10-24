# data_build/: provenance of data/model_inputs

These scripts built `data/model_inputs` from raw sources. Raw downloads (HouseZero minute files, ISO-NE via gridstatus, NREL ComStock 2025 R3 timeseries, BERDO xlsx, BPL meter, homesim output) are **not** in the repo. Set `MASSHACK_WORK` to a folder that contains them (default `data_build/_work`); outputs go to `$MASSHACK_WORK/unified`.

Order: `build_weather.py` → `build_grid.py` → `build_hz_may.py` → `build_templates_fast.py` → `build_members.py` → `build_civic.py` → `build_final_members.py` → `fix_modes.py` → `build_stock.py`, `build_qa.py`.

`fix_modes.py` matters for the model: it rebuilds every action run (load_shift_33, precool_42) as *baseline + effect fitted on the paired source simulations*. Before, each action run was a separate fit, and their difference was mostly fitting noise (see `EVALUATION.md` §3 and `data/model_inputs/mode_fix_report.csv`).
