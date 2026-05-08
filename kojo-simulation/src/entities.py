from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class Client:

    id: int
    arrival_time: float
    product: str
    service_time: float
    service_start_time: Optional[float] = None
    service_end_time: Optional[float] = None
    employee_id: Optional[int] = None

    def waiting_time(self) -> Optional[float]:

        if self.service_start_time is None:
            return None

        return self.service_start_time - self.arrival_time


    def total_time_in_system(self) -> Optional[float]:
        #Tiempo total = fin de servicio - llegada.

        if self.service_end_time is None:
            return None

        return self.service_end_time - self.arrival_time


@dataclass
class Employee:

    # El tercer empleado, en el escenario alternativo, se marca con: is_extra = True.

    id: int
    is_extra: bool = False
    active: bool = True
    can_take_new_clients: bool = True
    busy: bool = False
    current_client: Optional[Client] = None
    busy_time: float = 0.0
    last_service_start: Optional[float] = None

    def is_available(self) -> bool:
        return self.active and self.can_take_new_clients and not self.busy


    def start_service(self, client: Client, current_time: float) -> None:
        if self.busy:
            raise RuntimeError(f"El empleado {self.id} ya está ocupado.")

        self.busy = True
        self.current_client = client
        self.last_service_start = current_time

        client.service_start_time = current_time
        client.employee_id = self.id


    def finish_service(self, current_time: float) -> Client:

        if not self.busy:
            raise RuntimeError(f"El empleado {self.id} no está ocupado.")

        if self.current_client is None:
            raise RuntimeError(f"El empleado {self.id} no tiene cliente asignado.")

        if self.last_service_start is None:
            raise RuntimeError(
                f"El empleado {self.id} no tiene tiempo de inicio registrado."
            )

        finished_client = self.current_client
        finished_client.service_end_time = current_time

        self.busy_time += current_time - self.last_service_start

        self.busy = False
        self.current_client = None
        self.last_service_start = None

        return finished_client