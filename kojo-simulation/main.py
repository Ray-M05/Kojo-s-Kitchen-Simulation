import config
from src.logger import setup_logger
from src.simulator import KojoSimulator

def run_single_replication(logger, seed: int, use_extra_employee: bool) -> dict:

    scenario = "extra_employee_peak" if use_extra_employee else "two_employees"
    logger.info(
        "Running single replication | scenario=%s | seed=%s", scenario, seed)

    simulator = KojoSimulator(
        seed=seed,
        use_extra_employee=use_extra_employee,
        logger=logger,
    )
    results = simulator.run()

    logger.info(
        (
            "RESULT | scenario=%s | total=%s | completed=%s | "
            "delayed=%s | delayed_percentage=%.2f | average_wait=%.2f | max_wait=%.2f"
        ),
        scenario,
        results["total_customers"],
        results["completed_customers"],
        results["delayed_customers"],
        results["delayed_percentage"],
        results["average_wait"],
        results["max_wait"],
    )

    logger.info(
        (
            "UTILIZATION | scenario=%s | emp1=%.3f | emp2=%.3f | emp3=%.3f"
        ),
        scenario,
        results["employee_1_utilization"],
        results["employee_2_utilization"],
        results["employee_3_utilization"],
    )
    return results


def main() -> None:
    """
    Se ejecuta una réplica de ambos escenarios usando la misma semilla para que la comparación sea reproducible.
    """
    config.validate_config()

    logger = setup_logger(
        enabled=config.LOG_ENABLED,
        level=config.LOG_LEVEL,
        log_file=config.LOG_FILE,
    )

    logger.info("Kojo simulation project")

    seed = config.DEFAULT_SEED

    base_results = run_single_replication(
        logger=logger,
        seed=seed,
        use_extra_employee=False,
    )

    extra_results = run_single_replication(
        logger=logger,
        seed=seed,
        use_extra_employee=True,
    )

    improvement = (
        base_results["delayed_percentage"]
        - extra_results["delayed_percentage"]
    )

    logger.info(
        "COMPARISON | base_delayed=%.2f | extra_delayed=%.2f | improvement_points=%.2f",
        base_results["delayed_percentage"],
        extra_results["delayed_percentage"],
        improvement,
    )

    logger.info("Kojo simulation project finalizado correctamente")

if __name__ == "__main__":
    main()