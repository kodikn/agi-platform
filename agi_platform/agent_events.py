from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    kind: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time.time)
    visible_to_llm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MessageEvent(Event):
    role: Literal["user", "assistant", "system"] = "user"
    visible_to_llm: bool = True


@dataclass(frozen=True)
class ActionEvent(Event):
    action: str = "execute"
    visible_to_llm: bool = True


@dataclass(frozen=True)
class ObservationEvent(Event):
    action_id: str = ""
    status: Literal["ok", "error"] = "ok"
    visible_to_llm: bool = True


@dataclass
class EventLog:
    events: list[Event] = field(default_factory=list)

    def append(self, event: Event) -> Event:
        self.events.append(event)
        return event

    def extend(self, events: list[Event]) -> None:
        self.events.extend(events)

    def llm_visible(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events if event.visible_to_llm]

    def all(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]
