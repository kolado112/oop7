from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import weakref

@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any] = None
    visited: tuple[int, ...] = ()      

class Observer:
    """self - наблюдатель, subject - наблюдаемый объект, event - событие."""
    def update(self, subject: Any, event: Event) -> None:
        raise NotImplementedError

class Object:
    def __init__(self):
        self._observers: weakref.WeakSet = weakref.WeakSet()

    def get_observers(self) -> list[Observer]:
        return list(self._observers)

    def add_observer(self, obs: Observer) -> None:
        self._observers.add(obs)

    def remove_observer(self, obs: Observer) -> None:
        self._observers.discard(obs)

    def notify(self, event: Event) -> None:
        visited_ids = set(event.visited or ())
        my_id = id(self)

        # если этот subject уже участвовал в цепочке – выходим
        if my_id in visited_ids:
            print('Skip notify for', my_id, visited_ids)
            return

        print('Debug:', my_id, visited_ids)
        visited_ids.add(my_id)

        new_event = Event(
            type=event.type,
            payload=event.payload,
            visited=tuple(visited_ids),
        )

        for obs in list(self._observers):
            obs.update(self, new_event)
