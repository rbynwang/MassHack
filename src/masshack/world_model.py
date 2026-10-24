"""Path 2 — JEPA-style latent world model for building + weather.

Architecture (~200k params, trains on CPU/MPS):
  - Context encoder   : (weather + load history) → latent z  [Transformer encoder, 4L]
  - EMA target encoder: slow-moving copy for stable targets
  - Predictor         : (z, action sequence) → predicted future z
  - Read-out heads    : predicted z → demand_kw, pv_kw, soc_kwh
  - Planner interface : imagine_cost(actions, soc0, context)
"""

from __future__ import annotations

import numpy as np

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Model hyper-parameters
# ---------------------------------------------------------------------------
D_MODEL: int = 64
N_HEADS: int = 4
N_LAYERS: int = 4
D_ACTION: int = 1
HISTORY_LEN: int = 24   # hours of history fed to the encoder
HORIZON: int = 24       # planning horizon


# ---------------------------------------------------------------------------
# Helper blocks
# ---------------------------------------------------------------------------

def _mlp(in_dim: int, hidden: int, out_dim: int) -> "nn.Sequential":
    return nn.Sequential(
        nn.Linear(in_dim, hidden),
        nn.GELU(),
        nn.Linear(hidden, out_dim),
    )


# ---------------------------------------------------------------------------
# World model
# ---------------------------------------------------------------------------

if _TORCH_AVAILABLE:

    class WorldModel(nn.Module):
        """JEPA-style world model for the HouseZero building."""

        def __init__(
            self,
            n_input_features: int = 8,
            d_model: int = D_MODEL,
            n_heads: int = N_HEADS,
            n_layers: int = N_LAYERS,
            horizon: int = HORIZON,
        ) -> None:
            super().__init__()
            self.d_model = d_model
            self.horizon = horizon

            # Context encoder
            self.input_proj = nn.Linear(n_input_features, d_model)
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=n_heads,
                dim_feedforward=d_model * 4,
                dropout=0.1,
                batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)

            # EMA target encoder (weights copied, not updated by gradient)
            self.target_encoder = nn.TransformerEncoder(
                nn.TransformerEncoderLayer(
                    d_model=d_model,
                    nhead=n_heads,
                    dim_feedforward=d_model * 4,
                    dropout=0.0,
                    batch_first=True,
                ),
                num_layers=n_layers,
            )
            # Disable gradients for target encoder
            for p in self.target_encoder.parameters():
                p.requires_grad_(False)

            # Action predictor: takes z + action → predicted next z
            self.action_proj = nn.Linear(D_ACTION, d_model)
            self.predictor = _mlp(d_model * 2, d_model * 2, d_model)

            # Read-out heads
            self.head_demand = _mlp(d_model, d_model, 1)
            self.head_pv = _mlp(d_model, d_model, 1)
            self.head_soc = _mlp(d_model, d_model, 1)

        # ------------------------------------------------------------------

        def encode(self, x: "torch.Tensor") -> "torch.Tensor":
            """Encode a context window of shape (B, T, F) → (B, T, D)."""
            h = self.input_proj(x)
            return self.encoder(h)

        @torch.no_grad()
        def target_encode(self, x: "torch.Tensor") -> "torch.Tensor":
            h = self.input_proj(x)
            return self.target_encoder(h)

        def predict_step(
            self,
            z: "torch.Tensor",
            action: "torch.Tensor",
        ) -> "torch.Tensor":
            """Single-step prediction: (B, D) × (B, 1) → (B, D)."""
            a_emb = self.action_proj(action)
            return self.predictor(torch.cat([z, a_emb], dim=-1))

        def forward(
            self,
            context: "torch.Tensor",
            actions: "torch.Tensor",
        ) -> dict[str, "torch.Tensor"]:
            """Roll out the model over the planning horizon.

            Parameters
            ----------
            context : (B, HISTORY_LEN, F)
            actions : (B, HORIZON, 1)

            Returns
            -------
            dict with predicted demand, pv, soc trajectories.
            """
            B = context.size(0)
            z_seq = self.encode(context)
            z = z_seq[:, -1, :]  # last timestep as the current state

            demands, pvs, socs = [], [], []
            for t in range(self.horizon):
                a = actions[:, t, :]
                z = self.predict_step(z, a)
                demands.append(self.head_demand(z))
                pvs.append(self.head_pv(z))
                socs.append(self.head_soc(z))

            return {
                "demand_kw": torch.cat(demands, dim=1),
                "pv_kw": torch.cat(pvs, dim=1),
                "soc_kwh": torch.cat(socs, dim=1),
            }

        # ------------------------------------------------------------------
        # EMA update

        @torch.no_grad()
        def update_target(self, ema_decay: float = 0.996) -> None:
            """Exponential moving average update of the target encoder."""
            for p_online, p_target in zip(
                self.encoder.parameters(),
                self.target_encoder.parameters(),
            ):
                p_target.data.mul_(ema_decay).add_(p_online.data, alpha=1.0 - ema_decay)

        # ------------------------------------------------------------------
        # Planning interface (called by CEMPlanner)

        def imagine_cost(
            self,
            actions_kw: np.ndarray,
            soc0_kwh: float,
            context_np: np.ndarray,
        ) -> float:
            """Evaluate a candidate action plan; returns a scalar cost."""
            import torch
            from masshack.battery import energy_rate, DEMAND_CHARGE

            self.eval()
            ctx = torch.tensor(context_np[None], dtype=torch.float32)
            act = torch.tensor(actions_kw[None, :, None], dtype=torch.float32)

            with torch.no_grad():
                out = self.forward(ctx, act)

            demand = out["demand_kw"][0].numpy().flatten()
            pv = out["pv_kw"][0].numpy().flatten()
            # Grid import = demand - pv + battery action (charging)
            grid_kw = demand - pv + actions_kw
            grid_kw = np.maximum(grid_kw, 0.0)

            # Simplified cost (ignores demand charge for speed in CEM)
            cost = float(np.sum(grid_kw * 0.20))
            return cost

else:
    class WorldModel:  # type: ignore[no-redef]
        """Stub — install torch to use the world model."""

        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("torch is not installed.")
