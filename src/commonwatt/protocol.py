"""The Commonwatt protocol: seven message types, carried in signed envelopes.

Any agent that produces and accepts these messages can join a commons. `export_schemas()` writes one JSON Schema
per message to `protocol/schemas/`, so agents written in other languages can implement the same format.

Hours are local clock hours (America/New_York) of the event day, 0-23, converted from UTC by the sender.
Power is kW (hourly mean), energy kWh, money USD.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Union

from pydantic import BaseModel, Field

MemberKind = Literal["large_building", "household", "small_business", "public_institution"]


class AgentCard(BaseModel):
    """Who I am, who owns me, what I have, which commons I belong to. Published to the registry."""
    type: Literal["agent_card"] = "agent_card"
    agent_id: str
    role: Literal["member", "coordinator", "grid", "guard"]
    kind: MemberKind | None = None
    display_name: str
    owner: str
    commons: str
    assets: list[str] = Field(default_factory=list, description="e.g. pv, battery, heat_pump, hvac")
    can_offer: list[Literal["reduce", "increase"]] = Field(default_factory=list)
    public_key: str = Field(description="Ed25519 public key (hex) of the agent")
    guard_public_key: str | None = Field(None, description="Key its trust guard signs receipts with")
    data_label: Literal["measured", "simulated", "assumption"] = "simulated"


class Ask(BaseModel):
    """Grid -> coordinator: reduce or increase a number of kW during a window."""
    type: Literal["ask"] = "ask"
    ask_id: str
    direction: Literal["reduce", "increase"]
    kw: float = Field(gt=0)
    window: list[int] = Field(description="Local hours, e.g. [17, 18] = 5 to 7 PM")
    price_usd_per_kwh: float = Field(ge=0)
    reason: str


class OfferHour(BaseModel):
    hour: int = Field(ge=0, le=23)
    planned_kw: float = Field(description="The member's own plan for grid draw this hour")
    can_reduce_kw: float = Field(ge=0, description="How much less it could draw in this hour alone")
    can_increase_kw: float = Field(ge=0, description="How much more it could draw in this hour alone")


class Offer(BaseModel):
    """Member -> coordinator: what I can spare, and what it costs me. Never raw data or private limits."""
    type: Literal["offer"] = "offer"
    ask_id: str
    member_id: str
    hours: list[OfferHour]
    cost_per_kwh: float = Field(ge=0, description="Lost savings / comfort cost per kWh shifted")
    prep_kwh_per_kwh: float = Field(ge=0, description="Energy needed before the window per kWh reduced")
    rebound_kwh_per_kwh: float = Field(ge=0, description="Extra energy drawn after the window per kWh reduced")
    max_recovery_kw: float = Field(ge=0)


class Request(BaseModel):
    """Coordinator -> member (through its trust guard): a specific change asked of one member."""
    type: Literal["request"] = "request"
    request_id: str
    ask_id: str
    member_id: str
    round: int
    reduce_kw: float = Field(gt=0, description="Held for every hour of the window")
    window: list[int]
    price_usd_per_kwh: float


class Response(BaseModel):
    """Member -> coordinator: accept, counter (with a new amount) or decline. `blocked` comes from the guard."""
    type: Literal["response"] = "response"
    request_id: str
    member_id: str
    decision: Literal["accept", "counter", "decline", "blocked"]
    kw: float = Field(ge=0)
    reason: str
    prep_kwh: float = Field(0.0, description="Schedulable energy needed before the window (battery pre-charge)")
    rebound_kwh: float = Field(0.0, description="Schedulable energy after the window (battery recharge)")
    max_recovery_kw: float = 0.0
    fixed_kw: dict[int, float] = Field(default_factory=dict,
                                       description="Changes outside the window it cannot move (pre-cool, rebound)")


class Assignment(BaseModel):
    """Coordinator -> member: the final committed plan, including staggered preparation and recovery."""
    type: Literal["assignment"] = "assignment"
    ask_id: str
    member_id: str
    reduce_kw: float
    window: list[int]
    prep_kw: dict[int, float] = Field(default_factory=dict, description="Extra draw per hour before the window")
    recovery_kw: dict[int, float] = Field(default_factory=dict, description="Extra draw per hour after the window")
    price_usd_per_kwh: float


class Receipt(BaseModel):
    """Trust guard -> member, coordinator, ledger: signed record of what was requested, delivered and paid."""
    type: Literal["receipt"] = "receipt"
    receipt_id: str
    ask_id: str
    member_id: str
    window: list[int]
    committed_kw: float
    delivered_kwh: float
    price_usd_per_kwh: float
    payment_usd: float
    indoor_f_range: list[float] | None = None
    battery_min_pct: float | None = None
    prev_hash: str
    guard_public_key: str
    signature: str = ""


Message = Union[AgentCard, Ask, Offer, Request, Response, Assignment, Receipt]
MESSAGE_TYPES = [AgentCard, Ask, Offer, Request, Response, Assignment, Receipt]


class Envelope(BaseModel):
    """Every message travels in an envelope signed by its sender."""
    msg_id: str
    sender: str
    to: str
    sent_at: str = Field(description="Local time of the event day, HH:MM")
    body: dict
    signature: str


def export_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for model in MESSAGE_TYPES + [Envelope]:
        name = model.model_fields["type"].default if "type" in model.model_fields else "envelope"
        p = out_dir / f"{name}.schema.json"
        p.write_text(json.dumps(model.model_json_schema(), indent=2))
        written.append(p)
    return written
