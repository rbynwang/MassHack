"""Message bus and registry. For the demo the bus is in memory; every message is still a signed envelope,
checked against the sender's registered key on arrival, and written to the message log the demo replays."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from commonwatt import signing
from commonwatt.protocol import AgentCard, Envelope


class SignatureError(Exception):
    pass


@dataclass
class Registry:
    """Agent cards by id. Any agent that publishes a valid card can be found by the coordinator."""
    cards: dict[str, AgentCard] = field(default_factory=dict)

    def register(self, card: AgentCard) -> None:
        self.cards[card.agent_id] = card

    def key(self, agent_id: str) -> str:
        return self.cards[agent_id].public_key

    def members(self, commons: str) -> list[AgentCard]:
        return [c for c in self.cards.values() if c.role == "member" and c.commons == commons]


@dataclass
class Bus:
    registry: Registry
    handlers: dict[str, Callable[[Envelope], BaseModel | None]] = field(default_factory=dict)
    log: list[dict[str, Any]] = field(default_factory=list)
    clock: str = "00:00"
    _ids: Any = field(default_factory=lambda: itertools.count(1))

    def at(self, hhmm: str) -> None:
        self.clock = hhmm

    def note(self, actor: str, text: str, kind: str = "note", **extra) -> None:
        self.log.append({"t": self.clock, "from": actor, "to": "", "type": kind, "text": text, **extra})

    def envelope(self, sender: str, keys: signing.KeyPair, to: str, msg: BaseModel) -> Envelope:
        body = msg.model_dump(mode="json")
        mid = f"m{next(self._ids):04d}"
        unsigned = {"msg_id": mid, "sender": sender, "to": to, "sent_at": self.clock, "body": body}
        return Envelope(**unsigned, signature=keys.sign(unsigned))

    def check(self, env: Envelope) -> None:
        unsigned = env.model_dump(exclude={"signature"})
        if not signing.verify(unsigned, env.signature, self.registry.key(env.sender)):
            raise SignatureError(f"bad signature on {env.msg_id} from {env.sender}")

    def send(self, sender: str, keys: signing.KeyPair, to: str, msg: BaseModel, text: str,
             handler_to: str | None = None) -> BaseModel | None:
        """Sign, check on arrival, log, and hand to the receiver's handler. Returns the handler's reply."""
        env = self.envelope(sender, keys, to, msg)
        self.check(env)
        self.log.append({"t": self.clock, "from": sender, "to": to, "type": env.body["type"], "text": text,
                         "msg_id": env.msg_id, "sig": env.signature[:16]})
        h = self.handlers.get(handler_to or to)
        return h(env) if h else None
