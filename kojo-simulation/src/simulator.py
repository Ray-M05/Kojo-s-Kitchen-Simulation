from __future__ import annotations
import heapq
from collections import deque
from typing import Deque, List, Optional
import config
from src.entities import Client, Employee
from src.events import (
    ARRIVAL,
    SERVICE_END,
    PEAK_START,
    PEAK_END,
    CLOSE,
    create_event,
)
from src.random_generators import RandomGenerator

class KojoSimulator:

    def __init__(
        self, seed: Optional[int], use_extra_employee: bool, logger, experiment_config: Optional[dict] = None):

        self.seed = seed
        self.use_extra_employee = use_extra_employee
        self.logger = logger
        self.experiment_config = experiment_config or config.EXPERIMENT_CONFIGS[0]

        config.validate_experiment_config(self.experiment_config)

        self.config_id = self.experiment_config["config_id"]
        self.mean_interarrival_normal = self.experiment_config["mean_interarrival_normal"]
        self.mean_interarrival_peak = self.experiment_config["mean_interarrival_peak"]

        self.rng = RandomGenerator(seed)

        self.clock = config.DAY_OPEN
        self.event_queue = []
        self.sequence = 0

        self.waiting_queue: Deque[Client] = deque()
        self.employees: List[Employee] = self.create_employees()

        self.total_customers = 0
        self.completed_customers = 0
        self.delayed_customers = 0

        self.total_waiting_time = 0.0
        self.max_waiting_time = 0.0
        self.area_queue = 0.0

        self.generated_customers = 0


    def get_mean_interarrival(self, segment_type: str) -> float:
        """
        Devuelve la media entre llegadas según el tipo de segmento.

        Esta función permite que cada configuración experimental tenga
        diferentes valores de llegada normal y llegada en hora pico.
        """

        if segment_type == config.NORMAL:
            return self.mean_interarrival_normal

        if segment_type == config.PEAK:
            return self.mean_interarrival_peak

        raise ValueError(f"Tipo de segmento desconocido: {segment_type}")

    def create_employees(self) -> List[Employee]:

        employees = [
            Employee(id=1),
            Employee(id=2),
        ]

        if self.use_extra_employee:
            employees.append(
                Employee(
                    id=config.EXTRA_EMPLOYEE_ID,
                    is_extra=True,
                    active=False,
                    can_take_new_clients=False,
                )
            )
        return employees


    def schedule_event(self, time: float, event_type: str, payload=None) -> None:

        event = create_event(
            time=time,
            event_type=event_type,
            sequence=self.sequence,
            payload=payload,
        )
        self.sequence += 1
        heapq.heappush(self.event_queue, event)


    def schedule_initial_events(self) -> None:

        clients = self.generate_clients()
        self.generated_customers = len(clients)

        for client in clients:
            self.schedule_event(client.arrival_time, ARRIVAL, client)

        if self.use_extra_employee:
            for start, end in config.PEAK_PERIODS:
                self.schedule_event(start, PEAK_START)
                self.schedule_event(end, PEAK_END)

        self.schedule_event(config.DAY_CLOSE, CLOSE)

        self.logger.info(
            "Initial events scheduled | generated_customers=%s | extra_employee=%s", self.generated_customers, self.use_extra_employee,)


    def generate_clients(self) -> List[Client]:
        """
        Genera todos los clientes del día.
        En cada segmento, el tiempo entre llegadas distribuye exponencialmente con la media configurada para ese tipo de segmento.
        """

        clients: List[Client] = []
        client_id = 1

        for start, end, segment_type in config.DAY_SEGMENTS:
            mean_interarrival = self.get_mean_interarrival(segment_type)

            t = start
            while True:
                interarrival_time = self.rng.exponential_by_mean(mean_interarrival)
                t += interarrival_time

                if t >= end:
                    break

                product = self.rng.choose_product(config.P_SANDWICH)
                service_time = self.generate_service_time(product)

                client = Client(
                    id=client_id,
                    arrival_time=t,
                    product=product,
                    service_time=service_time,
                )
                clients.append(client)
                client_id += 1

        return sorted(clients, key=lambda client: client.arrival_time)


    def generate_service_time(self, product: str) -> float:
        """
        Genera el tiempo de servicio según el producto pedido
        """

        if product not in config.SERVICE_TIME_RANGES:
            raise ValueError(f"Producto desconocido: {product}")

        minimum, maximum = config.SERVICE_TIME_RANGES[product]
        return self.rng.uniform(minimum, maximum)


    def run(self) -> dict:
        """
        Ejecuta una réplica completa.
        El ciclo principal toma siempre el evento más próximo en el tiempo,
        mueve el reloj hasta ese instante y ejecuta la lógica correspondiente.
        """

        self.logger.info(
            ("Simulation started | seed=%s | config_id=%s | "
                "normal_arrival_mean=%.2f | peak_arrival_mean=%.2f | extra_employee=%s"),
            self.seed,
            self.config_id,
            self.mean_interarrival_normal,
            self.mean_interarrival_peak,
            self.use_extra_employee)

        self.schedule_initial_events()

        while self.event_queue:
            event = heapq.heappop(self.event_queue)

            self.advance_clock(event.time)

            if event.event_type == ARRIVAL:
                self.handle_arrival(event.payload)

            elif event.event_type == SERVICE_END:
                self.handle_service_end(event.payload)

            elif event.event_type == PEAK_START:
                self.handle_peak_start()

            elif event.event_type == PEAK_END:
                self.handle_peak_end()

            elif event.event_type == CLOSE:
                self.handle_close()

            else:
                raise RuntimeError(f"Evento no reconocido: {event.event_type}")

        self.validate_end_state()

        results = self.build_results()

        self.logger.info(
            "Simulation finished | total=%s | completed=%s | delayed=%s | delayed_percentage=%.2f",
            results["total_customers"],
            results["completed_customers"],
            results["delayed_customers"],
            results["delayed_percentage"],
        )
        return results


    def advance_clock(self, new_time: float) -> None:
        """
        Avanza el reloj de simulación.

        Antes de mover el reloj, se actualiza el área bajo la curva de longitud
        de cola. Esta área sirve para calcular la longitud promedio de la cola.

        Solo acumulamos área hasta DAY_CLOSE, porque la jornada observable
        termina a las 9:00 p.m. Aunque se terminen servicios después del cierre,
        eso no debe inflar artificialmente la cola promedio del horario abierto.
        """

        if new_time < self.clock:
            raise RuntimeError(
                f"No se puede retroceder el reloj: clock={self.clock}, new_time={new_time}"
            )

        observable_start = min(self.clock, config.DAY_CLOSE)
        observable_end = min(new_time, config.DAY_CLOSE)

        if observable_end > observable_start:
            elapsed = observable_end - observable_start
            self.area_queue += len(self.waiting_queue) * elapsed

        self.clock = new_time


    def handle_arrival(self, client: Client) -> None:
        """
        Procesa la llegada de un cliente.
        El cliente siempre entra primero a la cola FIFO.
        Luego se intenta iniciar servicio.

        Esto evita duplicar lógica: la asignación de empleados se centraliza
        en try_start_services().
        """

        if client.arrival_time > config.DAY_CLOSE:
            raise RuntimeError(
                f"Cliente generado después del cierre: client={client.id}, arrival={client.arrival_time}"
            )

        self.total_customers += 1
        self.waiting_queue.append(client)

        self.logger.debug(
            "t=%.2f | ARRIVAL | client=%s | product=%s | service_time=%.2f | queue=%s",
            self.clock,
            client.id,
            client.product,
            client.service_time,
            len(self.waiting_queue),
        )
        self.try_start_services()


    def handle_service_end(self, employee: Employee) -> None:
        """
        Procesa el fin de servicio de un empleado.
        El empleado termina con su cliente actual, se libera y luego se intenta
        atender al próximo cliente de la cola.

        Si el empleado es el extra y ya terminó la hora pico, se desactiva
        después de terminar el cliente actual.
        """

        if employee.current_client is None:
            raise RuntimeError(
                f"Evento SERVICE_END inválido: empleado {employee.id} sin cliente."
            )

        finished_client = employee.finish_service(self.clock)
        self.completed_customers += 1

        self.logger.debug(
            "t=%.2f | SERVICE_END | client=%s | employee=%s | system_time=%.2f",
            self.clock,
            finished_client.id,
            employee.id,
            finished_client.total_time_in_system(),
        )

        if employee.is_extra and not employee.can_take_new_clients:
            employee.active = False

            self.logger.debug(
                "t=%.2f | EXTRA_EMPLOYEE_DEACTIVATED | employee=%s",
                self.clock,
                employee.id,
            )
        self.try_start_services()


    def handle_peak_start(self) -> None:
        """
        Procesa el inicio de una hora pico.
        Si existe tercer empleado, se activa y puede tomar nuevos clientes.
        Luego se intenta iniciar servicio por si había cola acumulada.
        """

        extra = self.get_extra_employee()

        if extra is None:
            self.logger.debug(
                "t=%.2f | PEAK_START ignored | no extra employee in this scenario",
                self.clock,
            )
            return

        extra.active = True
        extra.can_take_new_clients = True

        self.logger.info(
            "t=%.2f | PEAK_START | extra_employee=%s activated",
            self.clock,
            extra.id,
        )
        self.try_start_services()


    def handle_peak_end(self) -> None:
        """
        Procesa el fin de una hora pico.
        El tercer empleado deja de tomar nuevos clientes.
        Si está libre, se desactiva inmediatamente.
        Si está ocupado, termina su servicio actual y se desactiva al finalizar.
        """

        extra = self.get_extra_employee()

        if extra is None:
            self.logger.debug(
                "t=%.2f | PEAK_END ignored | no extra employee in this scenario",
                self.clock,
            )
            return

        extra.can_take_new_clients = False

        if not extra.busy:
            extra.active = False

        self.logger.info(
            "t=%.2f | PEAK_END | extra_employee=%s | busy=%s | active=%s",
            self.clock,
            extra.id,
            extra.busy,
            extra.active,
        )


    def handle_close(self) -> None:
        """
        Procesa el cierre del local.
        El cierre no elimina clientes ni cancela servicios.
        """
        self.logger.info(
            "t=%.2f | CLOSE | queue=%s | customers_arrived=%s | completed=%s",
            self.clock,
            len(self.waiting_queue),
            self.total_customers,
            self.completed_customers,
        )


    def get_available_employee(self) -> Optional[Employee]:
        """
        Un empleado está disponible si:
        - está activo
        - puede tomar nuevos clientes
        - no está ocupado
        """
        for employee in self.employees:
            if employee.is_available():
                return employee
        return None


    def try_start_services(self) -> None:
        """
        Mientras haya clientes esperando y empleados disponibles:
        - toma el primer cliente de la cola
        - lo asigna al empleado libre
        - programa el fin de servicio
        """
        while self.waiting_queue:
            employee = self.get_available_employee()

            if employee is None:
                break
            client = self.waiting_queue.popleft()
            self.start_service(employee, client)


    def start_service(self, employee: Employee, client: Client) -> None:
        """
        Inicia el servicio de un cliente con un empleado.
        Aquí se calcula la espera: espera = inicio_servicio - llegada
        """
        if client.service_time <= 0:
            raise RuntimeError(
                f"Tiempo de servicio inválido para cliente {client.id}: {client.service_time}"
            )

        employee.start_service(client, current_time=self.clock)

        waiting_time = client.waiting_time()

        if waiting_time is None:
            raise RuntimeError(f"No se pudo calcular la espera del cliente {client.id}.")

        if waiting_time < -1e-9:
            raise RuntimeError(
                f"Espera negativa detectada: client={client.id}, wait={waiting_time}"
            )

        waiting_time = max(0.0, waiting_time)

        self.total_waiting_time += waiting_time
        self.max_waiting_time = max(self.max_waiting_time, waiting_time)

        if waiting_time > config.WAIT_THRESHOLD:
            self.delayed_customers += 1

        service_end_time = self.clock + client.service_time
        self.schedule_event(service_end_time, SERVICE_END, employee)

        self.logger.debug(
            "t=%.2f | SERVICE_START | client=%s | employee=%s | wait=%.2f | service_end=%.2f",
            self.clock,
            client.id,
            employee.id,
            waiting_time,
            service_end_time,
        )


    def get_extra_employee(self) -> Optional[Employee]:
        for employee in self.employees:
            if employee.is_extra:
                return employee
        return None


    def build_results(self) -> dict:
        """
        Construye el diccionario de resultados de la réplica.
        """
        if self.total_customers > 0:
            delayed_percentage = (
                100.0 * self.delayed_customers / self.total_customers
            )
            average_wait = self.total_waiting_time / self.total_customers
        else:
            delayed_percentage = 0.0
            average_wait = 0.0

        day_duration = config.DAY_CLOSE - config.DAY_OPEN
        average_queue_length = self.area_queue / day_duration if day_duration > 0 else 0.0

        # Máximo entre duración de jornada y tiempo final real.
        # Así la utilización no se infla si algunos servicios terminan después del cierre.
        simulation_duration = max(day_duration, self.clock - config.DAY_OPEN)

        results = {
            "seed": self.seed,
            "config_id": self.config_id,
            "mean_interarrival_normal": self.mean_interarrival_normal,
            "mean_interarrival_peak": self.mean_interarrival_peak,
            "use_extra_employee": self.use_extra_employee,
            "simulation_end_time": self.clock,
            "total_customers": self.total_customers,
            "completed_customers": self.completed_customers,
            "delayed_customers": self.delayed_customers,
            "delayed_percentage": delayed_percentage,
            "average_wait": average_wait,
            "max_wait": self.max_waiting_time,
            "average_queue_length": average_queue_length,
        }

        # En el escenario base, el empleado 3 tendrá utilización 0.
        for employee_id in range(1, config.EXTRA_EMPLOYEE_ID + 1):
            employee = self.find_employee_by_id(employee_id)

            busy_time = employee.busy_time if employee is not None else 0.0
            utilization = (
                busy_time / simulation_duration if simulation_duration > 0 else 0.0
            )

            results[f"employee_{employee_id}_busy_time"] = busy_time
            results[f"employee_{employee_id}_utilization"] = utilization

        return results


    def find_employee_by_id(self, employee_id: int) -> Optional[Employee]:
        for employee in self.employees:
            if employee.id == employee_id:
                return employee
        return None


    def validate_end_state(self) -> None:

        if len(self.waiting_queue) != 0:
            raise RuntimeError(
                f"La simulación terminó con clientes en cola: {len(self.waiting_queue)}"
            )

        busy_employees = [employee.id for employee in self.employees if employee.busy]

        if busy_employees:
            raise RuntimeError(
                f"La simulación terminó con empleados ocupados: {busy_employees}"
            )

        if self.completed_customers != self.total_customers:
            raise RuntimeError(
                "Clientes completados no coincide con clientes llegados: "
                f"completed={self.completed_customers}, total={self.total_customers}"
            )

        if self.total_customers != self.generated_customers:
            raise RuntimeError(
                "Clientes procesados no coincide con clientes generados: "
                f"processed={self.total_customers}, generated={self.generated_customers}"
            )