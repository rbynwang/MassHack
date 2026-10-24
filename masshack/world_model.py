"""A small JEPA-style world model shared by every member.

  encoder   E(history_24h, member_embedding)            -> z_t          (what state is this building in?)
  predictor z_{k+1} = z_k + f(z_k, weather_k, calendar_k, mode)          (imagine the next hour)
  heads     H(z_k) -> demand P10/P50/P90 (normalized by member mean)    (read the imagined state out in kW)
  JEPA term ||z_24 - E_target(actual next-day history)||^2              (predict in latent space, EMA target)

The member embedding is the building's "fingerprint": a new business gets one from a few weeks of data, which is
how the model scales from one building to many. Battery and bill math stay exact in physics.py.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

H = 24
QS = (0.1, 0.5, 0.9)


def calendar_features(idx: pd.DatetimeIndex, holidays: set | None = None) -> np.ndarray:
    hr = idx.hour.values
    wd = idx.weekday.values
    hol = np.array([d in holidays for d in idx.date]) if holidays else np.zeros(len(idx), bool)
    doy = idx.dayofyear.values
    return np.stack([np.sin(2 * np.pi * hr / 24), np.cos(2 * np.pi * hr / 24), (wd >= 5) | hol,
                     np.sin(2 * np.pi * doy / 365), np.cos(2 * np.pi * doy / 365)], 1).astype(np.float32)


def weather_features(w: pd.DataFrame) -> np.ndarray:
    t = w["outdoor_temp_c"].values
    return np.stack([(t - 10) / 12, np.clip(t - 18, 0, None) / 10, np.clip(12 - t, 0, None) / 10,
                     w["ghi_w_m2"].fillna(0).values / 800], 1).astype(np.float32)


class WorldModel(nn.Module):
    def __init__(self, n_members: int, n_modes: int, d_z: int = 32, d_emb: int = 8, d_w: int = 4, d_c: int = 5,
                 type_of=None, n_types: int = 1):
        super().__init__()
        self.member_emb = nn.Embedding(n_members, d_emb)
        self.type_emb = nn.Embedding(max(n_types, 1), d_emb)     # building-type fingerprint (cold start: type only)
        self.register_buffer("type_of", torch.as_tensor(type_of if type_of is not None else [0] * n_members, dtype=torch.long))
        self.encoder = nn.Sequential(nn.Linear(2 * H + H * d_w + d_emb, 128), nn.GELU(), nn.Linear(128, d_z))
        self.pred = nn.Sequential(nn.Linear(d_z + d_w + d_c + n_modes + d_emb, 128), nn.GELU(), nn.Linear(128, d_z))
        self.head = nn.Sequential(nn.Linear(d_z + d_c, 64), nn.GELU(), nn.Linear(64, len(QS)))
        self.n_modes = n_modes

    def emb(self, mid):
        return self.member_emb(mid) + self.type_emb(self.type_of[mid])

    def encode(self, hist, hist_w, mid, lastweek=None):
        e = self.emb(mid)
        lw = hist if lastweek is None else lastweek
        return self.encoder(torch.cat([hist, lw, hist_w.flatten(1), e], 1))

    def rollout(self, z, fut_w, fut_c, mode, mid):
        e = self.emb(mid)
        m = nn.functional.one_hot(mode, self.n_modes).float()
        zs, qs = [], []
        for k in range(fut_w.shape[1]):
            z = z + self.pred(torch.cat([z, fut_w[:, k], fut_c[:, k], m, e], 1))
            zs.append(z)
            qs.append(self.head(torch.cat([z, fut_c[:, k]], 1)))
        q = torch.stack(qs, 1)
        q = torch.cat([q[..., 1:2] - nn.functional.softplus(q[..., 0:1]), q[..., 1:2],
                       q[..., 1:2] + nn.functional.softplus(q[..., 2:3])], -1)  # keep P10 <= P50 <= P90
        return torch.stack(zs, 1), q


def quantile_loss(q, y):
    loss = 0
    for i, tau in enumerate(QS):
        e = y - q[..., i]
        loss = loss + torch.maximum(tau * e, (tau - 1) * e).mean()
    return loss


@dataclass
class Sample:
    hist: np.ndarray; hist_w: np.ndarray; fut_w: np.ndarray; fut_c: np.ndarray; lastweek: np.ndarray; next_lastweek: np.ndarray
    y: np.ndarray; next_hist: np.ndarray; next_hist_w: np.ndarray; mid: int; mode: int


class WorldModelForecaster:
    """Train once across members and modes; forecast any member's next 24 h under any mode."""

    def __init__(self, ds, member_ids: list[str], modes: list[str], seed: int = 0, member_types: dict | None = None):
        self.ds, self.member_ids, self.modes = ds, list(member_ids), list(modes)
        self.mid = {m: i for i, m in enumerate(self.member_ids)}
        self.mode_ix = {m: i for i, m in enumerate(self.modes)}
        member_types = member_types or {}
        self.types = sorted({member_types.get(m, "other") for m in self.member_ids})
        self.type_ix = {t: i for i, t in enumerate(self.types)}
        self.type_of = [self.type_ix[member_types.get(m, "other")] for m in self.member_ids]
        torch.manual_seed(seed); np.random.seed(seed)
        self.model = WorldModel(len(self.member_ids), len(self.modes), type_of=self.type_of, n_types=len(self.types))
        self.scale = {}
        self.wf = weather_features(ds.weather)
        self.cal = calendar_features(ds.weather.index)
        self.tindex = ds.weather.index

    def _arrays(self, member, mode):
        y = self.ds.series(member, mode).reindex(self.tindex)
        s = self.scale.setdefault(member, float(self.ds.series(member, "baseline").mean()) or 1.0)
        return (y / s).interpolate(limit=3).values.astype(np.float32)

    def _samples(self, days: list[pd.Timestamp], members=None):
        X = {k: [] for k in Sample.__dataclass_fields__}
        pos = {t: i for i, t in enumerate(self.tindex)}
        for m in members or self.member_ids:
            for mode in self.ds.modes(m):
                if mode not in self.mode_ix:
                    continue
                y = self._arrays(m, mode)
                yb = y if mode == "baseline" else self._arrays(m, "baseline")
                for d in days:
                    i = pos.get(d)
                    if i is None or i < 7 * H + H or i + 2 * H > len(y):
                        continue
                    # history is always the BASELINE run (that is all a building knows when it plans tomorrow);
                    # only the target day is under the candidate mode. Before, the mode run's own history leaked the mode.
                    seg = np.concatenate([yb[i - H:i], y[i:i + H], yb[i - 7 * H:i - 6 * H], yb[i - 6 * H:i - 5 * H]])
                    if np.isnan(seg).any() or np.isnan(self.wf[i - H:i + H]).any():
                        continue
                    X["hist"].append(yb[i - H:i]); X["hist_w"].append(self.wf[i - H:i])
                    X["fut_w"].append(self.wf[i:i + H]); X["fut_c"].append(self.cal[i:i + H])
                    X["y"].append(y[i:i + H]); X["next_hist"].append(y[i:i + H]); X["next_hist_w"].append(self.wf[i:i + H])
                    X["lastweek"].append(yb[i - 7 * H:i - 6 * H]); X["next_lastweek"].append(yb[i - 6 * H:i - 5 * H])
                    X["mid"].append(self.mid[m]); X["mode"].append(self.mode_ix[mode])
        return {k: torch.tensor(np.array(v)) for k, v in X.items()}

    @torch.no_grad()
    def per_type_error(self, days, members) -> pd.DataFrame:
        rows = []
        for m in members:
            for d in days:
                try:
                    f = self.forecast(m, d)
                except Exception:
                    continue
                y = self.ds.series(m).reindex(f.index).values
                if np.isnan(y).any():
                    continue
                rows.append({"member": m, "type": self.types[self.type_of[self.mid[m]]], "mae_pct": float(np.mean(np.abs(f.p50.values - y)) / max(np.mean(y), 1e-6) * 100)})
        return pd.DataFrame(rows)

    def fit(self, train_days, epochs: int = 25, batch: int = 512, lr: float = 3e-3, jepa_weight: float = 0.2, log=print):
        data = self._samples(train_days)
        n = len(data["y"])
        # balanced sampling: every building type gets the same weight, so 200 homes do not drown 25 civic buildings
        tid = torch.as_tensor(self.type_of)[data["mid"]]
        counts = torch.bincount(tid, minlength=len(self.types)).float()
        w = 1.0 / counts[tid]
        target = copy.deepcopy(self.model)
        for p in target.parameters():
            p.requires_grad_(False)
        opt = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        for ep in range(epochs):
            perm = torch.multinomial(w, n, replacement=True)
            tot = 0.0
            for b in range(0, n, batch):
                ix = perm[b:b + batch]
                z0 = self.model.encode(data["hist"][ix], data["hist_w"][ix], data["mid"][ix], data["lastweek"][ix])
                zs, q = self.model.rollout(z0, data["fut_w"][ix], data["fut_c"][ix], data["mode"][ix], data["mid"][ix])
                with torch.no_grad():
                    zt = target.encode(data["next_hist"][ix], data["next_hist_w"][ix], data["mid"][ix], data["next_lastweek"][ix])
                jepa = ((zs[:, -1] - zt) ** 2).mean()
                var = torch.relu(1 - zs[:, -1].std(0)).mean()        # keep the latent from collapsing
                loss = quantile_loss(q, data["y"][ix]) + jepa_weight * (jepa + var)
                opt.zero_grad(); loss.backward(); opt.step()
                with torch.no_grad():                                # EMA target encoder
                    for pt, p in zip(target.parameters(), self.model.parameters()):
                        pt.mul_(0.99).add_(0.01 * p)
                tot += float(loss) * len(ix)
            if log and (ep % 5 == 0 or ep == epochs - 1):
                log(f"world model epoch {ep:2d}  loss {tot / n:.4f}  samples {n}")
        return self

    @torch.no_grad()
    def forecast(self, member: str, day_start: pd.Timestamp, mode: str = "baseline", weather_fc: pd.DataFrame | None = None) -> pd.DataFrame:
        """Next-24h demand quantiles in kW, using history up to day_start and a weather forecast (no leakage)."""
        pos = self.tindex.get_loc(day_start)
        y = self._arrays(member, "baseline")
        hist = np.nan_to_num(y[pos - H:pos], nan=float(np.nanmean(y[pos - H:pos])))
        fw = self.wf[pos:pos + H] if weather_fc is None else weather_features(weather_fc)
        t = lambda a: torch.tensor(a[None])
        lw = np.nan_to_num(y[pos - 7 * H:pos - 6 * H], nan=float(np.nanmean(hist)))
        z0 = self.model.encode(t(hist), t(self.wf[pos - H:pos]), torch.tensor([self.mid[member]]), t(lw))
        zs, q = self.model.rollout(z0, t(fw), t(self.cal[pos:pos + H]), torch.tensor([self.mode_ix.get(mode, 0)]),
                                   torch.tensor([self.mid[member]]))
        q = q[0].numpy() * self.scale[member]
        idx = self.tindex[pos:pos + H]
        return pd.DataFrame({"p10": q[:, 0], "p50": q[:, 1], "p90": q[:, 2]}, index=idx).clip(lower=0)

    @torch.no_grad()
    def embeddings(self) -> pd.DataFrame:
        e = self.model.emb.weight.numpy()
        return pd.DataFrame(e, index=self.member_ids)

    @torch.no_grad()
    def daily_latents(self, member: str, days) -> pd.DataFrame:
        """Encoder state at midnight for each day (for the 'what the model learned' map)."""
        pos = {t: i for i, t in enumerate(self.tindex)}
        y = self._arrays(member, "baseline")
        rows, keep = [], []
        for d in days:
            i = pos.get(d)
            if i is None or i < 7 * H or np.isnan(y[i - 7 * H:i]).any() or np.isnan(self.wf[i - H:i]).any():
                continue
            z = self.model.encode(torch.tensor(y[None, i - H:i]), torch.tensor(self.wf[None, i - H:i]), torch.tensor([self.mid[member]]),
                                  torch.tensor(y[None, i - 7 * H:i - 6 * H]))
            rows.append(z[0].numpy()); keep.append(d)
        return pd.DataFrame(np.array(rows), index=keep)

    def save(self, path):
        torch.save({"state": self.model.state_dict(), "members": self.member_ids, "modes": self.modes, "scale": self.scale,
                    "types": self.types, "type_of": self.type_of}, path)
