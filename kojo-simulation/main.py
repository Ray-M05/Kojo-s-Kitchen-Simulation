import config
from src.experiments import run_experiments
from src.logger import setup_logger


def main() -> None:
    """
    Punto de entrada del proyecto.

    Ejecuta el conjunto completo de experimentos:
    - escenario base
    - escenario con tercer empleado en horas pico
    - múltiples réplicas
    - exportación de resultados CSV
    """

    config.validate_config()

    logger = setup_logger(
        enabled=config.LOG_ENABLED,
        level=config.LOG_LEVEL,
        log_file=config.LOG_FILE,
    )

    logger.info("Kojo simulation project started")

    run_experiments(logger)

    logger.info("Kojo simulation project finished")


if __name__ == "__main__":
    main()