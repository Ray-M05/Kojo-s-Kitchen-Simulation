import csv
import json
import os
from datetime import datetime
from typing import Dict, List

import config
from src.metrics import summarize
from src.simulator import KojoSimulator


SCENARIOS = [
    {
        "name": "two_employees",
        "use_extra_employee": False,
    },
    {
        "name": "extra_employee_peak",
        "use_extra_employee": True,
    },
]


METRICS_TO_SUMMARIZE = [
    "delayed_percentage",
    "average_wait",
    "max_wait",
    "average_queue_length",
    "total_customers",
    "completed_customers",
    "delayed_customers",
    "employee_1_utilization",
    "employee_2_utilization",
    "employee_3_utilization",
]


PREFERRED_RAW_FIELD_ORDER = [
    "config_id",
    "mean_interarrival_normal",
    "mean_interarrival_peak",
    "replication",
    "scenario",
    "seed",
    "use_extra_employee",
    "simulation_end_time",
    "total_customers",
    "completed_customers",
    "delayed_customers",
    "delayed_percentage",
    "average_wait",
    "max_wait",
    "average_queue_length",
    "employee_1_busy_time",
    "employee_1_utilization",
    "employee_2_busy_time",
    "employee_2_utilization",
    "employee_3_busy_time",
    "employee_3_utilization",
]


def run_experiments(logger) -> List[Dict]:

    os.makedirs("results", exist_ok=True)

    raw_results = []

    logger.info(
        "Experiments started | configs=%s | replications=%s | scenarios=%s",
        [experiment_config["config_id"] for experiment_config in config.EXPERIMENT_CONFIGS],
        config.N_REPLICATIONS,
        [scenario["name"] for scenario in SCENARIOS],
    )

    for experiment_config in config.EXPERIMENT_CONFIGS:
        config_id = experiment_config["config_id"]

        logger.info(
            (
                "Experiment config started | config_id=%s | "
                "mean_interarrival_normal=%.2f | mean_interarrival_peak=%.2f"
            ),
            config_id,
            experiment_config["mean_interarrival_normal"],
            experiment_config["mean_interarrival_peak"],
        )

        for replication in range(1, config.N_REPLICATIONS + 1):
            seed = replication

            logger.info(
                "Replication started | config_id=%s | replication=%s | seed=%s",
                config_id,
                replication,
                seed,
            )

            for scenario_config in SCENARIOS:
                scenario_name = scenario_config["name"]
                use_extra_employee = scenario_config["use_extra_employee"]

                logger.info(
                    "Scenario started | config_id=%s | replication=%s | scenario=%s",
                    config_id,
                    replication,
                    scenario_name,
                )

                simulator = KojoSimulator(
                    seed=seed,
                    use_extra_employee=use_extra_employee,
                    logger=logger,
                    experiment_config=experiment_config,
                )

                result = simulator.run()

                result["replication"] = replication
                result["scenario"] = scenario_name

                raw_results.append(result)

                logger.info(
                    (
                        "Scenario finished | config_id=%s | replication=%s | scenario=%s | "
                        "total=%s | delayed_percentage=%.2f | average_wait=%.2f"
                    ),
                    config_id,
                    replication,
                    scenario_name,
                    result["total_customers"],
                    result["delayed_percentage"],
                    result["average_wait"],
                )

            logger.info(
                "Replication finished | config_id=%s | replication=%s",
                config_id,
                replication,
            )

        logger.info("Experiment config finished | config_id=%s", config_id)

    raw_csv_path = save_raw_results(raw_results)
    summary_csv_path = save_summary_results(raw_results)
    comparison_csv_path = save_comparison_results(raw_results)

    raw_json_path = save_raw_results_json(raw_results)
    config_json_path = save_experiment_configs_json()
    manifest_json_path = save_run_manifest_json(raw_results)

    logger.info("Raw CSV results saved | path=%s", raw_csv_path)
    logger.info("Summary CSV results saved | path=%s", summary_csv_path)
    logger.info("Comparison CSV results saved | path=%s", comparison_csv_path)

    logger.info("Raw JSON results saved | path=%s", raw_json_path)
    logger.info("Experiment configs JSON saved | path=%s", config_json_path)
    logger.info("Run manifest JSON saved | path=%s", manifest_json_path)

    log_main_comparison(raw_results, logger)

    logger.info("Experiments finished")

    return raw_results

def save_raw_results(raw_results: List[Dict]) -> str:

    path = "results/raw_results.csv"

    if not raw_results:
        return path

    fieldnames = build_fieldnames(raw_results)

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(raw_results)

    return path


def save_summary_results(raw_results: List[Dict]) -> str:

    path = "results/summary_results.csv"

    if not raw_results:
        return path

    rows = []

    config_ids = sorted(set(row["config_id"] for row in raw_results))

    for config_id in config_ids:
        config_rows = [
            row for row in raw_results
            if row["config_id"] == config_id
        ]

        scenarios = sorted(set(row["scenario"] for row in config_rows))

        for scenario in scenarios:
            scenario_rows = [
                row for row in config_rows
                if row["scenario"] == scenario
            ]

            for metric in METRICS_TO_SUMMARIZE:
                values = [
                    row[metric]
                    for row in scenario_rows
                    if metric in row
                ]

                stats = summarize(values)

                representative = scenario_rows[0]

                rows.append(
                    {
                        "config_id": config_id,
                        "mean_interarrival_normal": representative["mean_interarrival_normal"],
                        "mean_interarrival_peak": representative["mean_interarrival_peak"],
                        "scenario": scenario,
                        "metric": metric,
                        "count": stats["count"],
                        "mean": stats["mean"],
                        "std": stats["std"],
                        "min": stats["min"],
                        "max": stats["max"],
                        "ci95_low": stats["ci95_low"],
                        "ci95_high": stats["ci95_high"],
                    }
                )

    fieldnames = [
        "config_id",
        "mean_interarrival_normal",
        "mean_interarrival_peak",
        "scenario",
        "metric",
        "count",
        "mean",
        "std",
        "min",
        "max",
        "ci95_low",
        "ci95_high",
    ]

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return path

def save_comparison_results(raw_results: List[Dict]) -> str:

    path = "results/comparison_results.csv"

    if not raw_results:
        return path

    rows_by_replication = group_by_replication(raw_results)
    comparison_rows = []

    for (config_id, replication), rows in sorted(rows_by_replication.items()):
        base = rows.get("two_employees")
        extra = rows.get("extra_employee_peak")

        if base is None or extra is None:
            continue

        comparison_rows.append(
            {
                "config_id": config_id,
                "mean_interarrival_normal": base["mean_interarrival_normal"],
                "mean_interarrival_peak": base["mean_interarrival_peak"],
                "replication": replication,
                "seed": base["seed"],

                "base_total_customers": base["total_customers"],
                "extra_total_customers": extra["total_customers"],

                "base_delayed_percentage": base["delayed_percentage"],
                "extra_delayed_percentage": extra["delayed_percentage"],
                "delayed_percentage_improvement": (
                    base["delayed_percentage"] - extra["delayed_percentage"]
                ),

                "base_average_wait": base["average_wait"],
                "extra_average_wait": extra["average_wait"],
                "average_wait_improvement": (
                    base["average_wait"] - extra["average_wait"]
                ),

                "base_max_wait": base["max_wait"],
                "extra_max_wait": extra["max_wait"],
                "max_wait_improvement": (
                    base["max_wait"] - extra["max_wait"]
                ),

                "base_average_queue_length": base["average_queue_length"],
                "extra_average_queue_length": extra["average_queue_length"],
                "average_queue_length_improvement": (
                    base["average_queue_length"] - extra["average_queue_length"]
                ),

                "extra_employee_utilization": extra["employee_3_utilization"],
            }
        )

    if not comparison_rows:
        return path

    fieldnames = list(comparison_rows[0].keys())

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(comparison_rows)

    return path


def group_by_replication(raw_results: List[Dict]) -> Dict[tuple, Dict[str, Dict]]:

    grouped = {}

    for row in raw_results:
        config_id = row["config_id"]
        replication = int(row["replication"])
        scenario = row["scenario"]

        key = (config_id, replication)

        if key not in grouped:
            grouped[key] = {}

        grouped[key][scenario] = row

    return grouped


def build_fieldnames(raw_results: List[Dict]) -> List[str]:

    all_fields = set()

    for row in raw_results:
        all_fields.update(row.keys())

    ordered_fields = [
        field for field in PREFERRED_RAW_FIELD_ORDER
        if field in all_fields
    ]

    extra_fields = sorted(all_fields - set(ordered_fields))

    return ordered_fields + extra_fields


def log_main_comparison(raw_results: List[Dict], logger) -> None:

    rows_by_replication = group_by_replication(raw_results)

    improvements_by_config = {}

    for (config_id, replication), rows in rows_by_replication.items():
        base = rows.get("two_employees")
        extra = rows.get("extra_employee_peak")

        if base is None or extra is None:
            continue

        improvement = base["delayed_percentage"] - extra["delayed_percentage"]

        if config_id not in improvements_by_config:
            improvements_by_config[config_id] = []

        improvements_by_config[config_id].append(improvement)

    if not improvements_by_config:
        logger.warning("No comparison rows available")
        return

    for config_id, improvements in sorted(improvements_by_config.items()):
        stats = summarize(improvements)

        logger.info(
            (
                "Main comparison | config_id=%s | metric=delayed_percentage_improvement | "
                "mean=%.2f | ci95=[%.2f, %.2f] | min=%.2f | max=%.2f"
            ),
            config_id,
            stats["mean"],
            stats["ci95_low"],
            stats["ci95_high"],
            stats["min"],
            stats["max"],
        )


def save_raw_results_json(raw_results: List[Dict]) -> str:

    path = "results/raw_results.json"

    with open(path, "w", encoding="utf-8") as file:
        json.dump(raw_results, file, indent=4, ensure_ascii=False)

    return path

def save_experiment_configs_json() -> str:

    path = "results/experiment_configs.json"

    data = {
        "experiment_configs": config.EXPERIMENT_CONFIGS,
        "day_open": config.DAY_OPEN,
        "day_close": config.DAY_CLOSE,
        "peak_periods": config.PEAK_PERIODS,
        "day_segments": config.DAY_SEGMENTS,
        "p_sandwich": config.P_SANDWICH,
        "p_sushi": config.P_SUSHI,
        "service_time_ranges": config.SERVICE_TIME_RANGES,
        "wait_threshold": config.WAIT_THRESHOLD,
        "n_replications": config.N_REPLICATIONS,
    }

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

    return path

def save_run_manifest_json(raw_results: List[Dict]) -> str:

    path = "results/run_manifest.json"

    data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "n_rows": len(raw_results),
        "n_replications": config.N_REPLICATIONS,
        "scenarios": SCENARIOS,
        "experiment_configs": config.EXPERIMENT_CONFIGS,
        "outputs": {
            "raw_csv": "results/raw_results.csv",
            "summary_csv": "results/summary_results.csv",
            "comparison_csv": "results/comparison_results.csv",
            "raw_json": "results/raw_results.json",
            "experiment_configs_json": "results/experiment_configs.json",
        },
    }

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

    return path

