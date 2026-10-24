"""Grid agent: turns ISO-NE conditions into an ask (measured data: RT LMP .Z.NEMASSBOST, system load)."""

from __future__ import annotations

import pandas as pd

from commonwatt import LOCAL_TZ, signing
from commonwatt.members import EVENT_DAY, TRAIN
from commonwatt.protocol import AgentCard, Ask


class GridAgent:
    id = "grid"

    def __init__(self, commons: str) -> None:
        self.keys = signing.KeyPair()
        self.commons = commons
        g = pd.read_parquet(TRAIN / "grid.parquet")
        g["timestamp_utc"] = pd.to_datetime(g["timestamp_utc"], utc=True)
        d = g.set_index("timestamp_utc").tz_convert(LOCAL_TZ).loc[EVENT_DAY]
        h = d[["lmp_usd_mwh", "system_load_mw"]].resample("h").mean()
        self.lmp = h["lmp_usd_mwh"].round(1).tolist()
        self.load_mw = h["system_load_mw"].round(0).tolist()

    def card(self) -> AgentCard:
        return AgentCard(agent_id=self.id, role="grid", display_name="Grid agent (ISO-NE NEMA/Boston)",
                         owner="grid operator (mock)", commons=self.commons, public_key=self.keys.public_hex,
                         data_label="measured")

    def make_ask(self, kw: float, window: list[int]) -> Ask:
        price = sum(self.lmp[h] for h in window) / len(window) / 1000.0
        peak_h = max(range(24), key=lambda h: self.load_mw[h])
        reason = (f"ISO-NE system load peaks at {self.load_mw[peak_h]:,.0f} MW at {peak_h}:00; Boston-zone "
                  f"real-time price ${self.lmp[window[0]]:,.0f}-{max(self.lmp[h] for h in window):,.0f}/MWh")
        return Ask(ask_id="ask-2025-06-24", direction="reduce", kw=kw, window=window,
                   price_usd_per_kwh=round(price, 3), reason=reason)
