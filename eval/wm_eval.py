"""Train the current world model recipe on the evaluation split; save it; score baseline and action effects."""
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "eval"))
DATA = os.environ.get("MASSHACK_DATA", str(ROOT / "data" / "model_inputs"))
import sys, time, pickle, numpy as np, pandas as pd, torch
torch.set_num_threads(1)
from common import split, Dataset
from masshack.world_model import WorldModelForecaster
from run_all import member_type
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:6.1f}s]", *a, flush=True)
ds = Dataset(DATA); train, cal, test, peaks = split(ds)
mem = list(ds.members.index); types = {m: member_type(r) for m, r in ds.members.iterrows()}
modes = sorted({x for m in mem for x in ds.modes(m)})
wm = WorldModelForecaster(ds, mem, modes, member_types=types).fit(train, epochs=20, log=log)
wm.save("eval/wm_eval.pt"); pickle.dump(wm, open("eval/wm_eval.pkl", "wb")); log("saved")
