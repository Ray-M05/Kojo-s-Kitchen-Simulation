from dataclasses import dataclass, field
from typing import Any

ARRIVAL = "arrival"
SERVICE_END = "service_end"
PEAK_START = "peak_start"
PEAK_END = "peak_end"
CLOSE = "close"

SUPPORTED_EVENTS = {
    ARRIVAL,
    SERVICE_END,
    PEAK_START,
    PEAK_END,
    CLOSE,
}


# Prioridades
EVENT_PRIORITY = {
    SERVICE_END: 1,
    PEAK_START: 2,
    PEAK_END: 3,
    ARRIVAL: 4,
    CLOSE: 5,
}


@dataclass(order=True)
class Event:
    """
    Evento discreto dentro de la simulación.
    Se ordena por:
    1. time
    2. priority
    3. sequence
    """

    time: float
    priority: int
    sequence: int
    event_type: str = field(compare=False)
    payload: Any = field(default=None, compare=False)


def create_event(
    time: float,
    event_type: str,
    sequence: int,
    payload: Any = None,
) -> Event:

    if event_type not in SUPPORTED_EVENTS:
        raise ValueError(f"Tipo de evento no soportado: {event_type}")

    if time < 0:
        raise ValueError("El tiempo de un evento no puede ser negativo.")

    return Event(
        time=time,
        priority=EVENT_PRIORITY[event_type],
        sequence=sequence,
        event_type=event_type,
        payload=payload,
    )