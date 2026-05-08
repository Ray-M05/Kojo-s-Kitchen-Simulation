import config
from src.entities import Client, Employee
from src.events import ARRIVAL, create_event
from src.logger import setup_logger
from src.random_generators import RandomGenerator

def main() -> None:

    config.validate_config()

    logger = setup_logger(
        enabled=config.LOG_ENABLED,
        level=config.LOG_LEVEL,
        log_file=config.LOG_FILE,
    )

    logger.info("Kojo simulation project - Etapa 1 iniciada")

    rng = RandomGenerator(seed=config.DEFAULT_SEED)

    product = rng.choose_product(config.P_SANDWICH)
    service_min, service_max = config.SERVICE_TIME_RANGES[product]
    service_time = rng.uniform(service_min, service_max)

    client = Client(
        id=1,
        arrival_time=0.0,
        product=product,
        service_time=service_time,
    )

    employee = Employee(id=1)

    logger.info(
        "Cliente de prueba creado | id=%s | product=%s | service_time=%.2f",
        client.id,
        client.product,
        client.service_time,
    )

    logger.info(
        "Empleado de prueba creado | id=%s | available=%s",
        employee.id,
        employee.is_available(),
    )

    event = create_event(
        time=client.arrival_time,
        event_type=ARRIVAL,
        sequence=0,
        payload=client,
    )

    logger.info(
        "Evento de prueba creado | time=%.2f | type=%s | priority=%s",
        event.time,
        event.event_type,
        event.priority,
    )

    employee.start_service(client, current_time=0.0)
    logger.info(
        "Servicio de prueba iniciado | employee=%s | client=%s",
        employee.id,
        client.id,
    )

    finished_client = employee.finish_service(current_time=client.service_time)
    logger.info(
        "Servicio de prueba terminado | client=%s | total_time=%.2f | employee_busy_time=%.2f",
        finished_client.id,
        finished_client.total_time_in_system(),
        employee.busy_time,
    )


if __name__ == "__main__":
    main()