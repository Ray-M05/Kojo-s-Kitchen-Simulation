from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


RAW_RESULTS_FILENAME = "raw_results.csv"
COMPARISON_RESULTS_FILENAME = "comparison_results.csv"
VALIDATION_REPORT_FILENAME = "validation_report.txt"


ERROR = "ERROR"
WARNING = "WARNING"


def main() -> None:
    """
    Punto de entrada del validador.

    Uso:

        py -m src.validation

    o:

        py -m src.validation results/run_2026_05_09_104500

    Si no se pasa una carpeta, se intenta validar automáticamente
    la corrida más reciente dentro de results/.
    """

    run_dir = get_run_dir_from_args()

    if run_dir is None:
        print("No se encontró una carpeta de resultados para validar.")
        sys.exit(1)

    print(f"Validando resultados en: {run_dir}")

    issues = validate_run_directory(run_dir)

    report_path = write_validation_report(run_dir, issues)

    print()
    print(f"Reporte generado en: {report_path}")

    error_count = count_issues(issues, ERROR)
    warning_count = count_issues(issues, WARNING)

    print()
    print("Resumen de validación")
    print("---------------------")
    print(f"Errores:      {error_count}")
    print(f"Advertencias: {warning_count}")

    if error_count > 0:
        print()
        print("La validación terminó con errores. Revisa validation_report.txt.")
        sys.exit(1)

    print()
    print("Validación finalizada correctamente.")


# ------------------------------------------------------------
# Localización de archivos
# ------------------------------------------------------------

def get_run_dir_from_args() -> Optional[Path]:
    """
    Obtiene la carpeta de resultados a validar.

    Si el usuario pasa una ruta por consola, se usa esa ruta.
    Si no pasa nada, se busca la última carpeta results/run_*.
    Si no existen carpetas run_*, se intenta usar results/.
    """

    if len(sys.argv) >= 2:
        candidate = Path(sys.argv[1])

        if not candidate.exists():
            print(f"La ruta no existe: {candidate}")
            return None

        if not candidate.is_dir():
            print(f"La ruta no es una carpeta: {candidate}")
            return None

        return candidate

    results_dir = Path("results")

    if not results_dir.exists():
        return None

    run_dirs = [
        path for path in results_dir.iterdir()
        if path.is_dir() and path.name.startswith("run_")
    ]

    if run_dirs:
        return max(run_dirs, key=lambda path: path.stat().st_mtime)

    # Compatibilidad con la versión anterior, donde los CSV estaban
    # directamente dentro de results/.
    if (results_dir / RAW_RESULTS_FILENAME).exists():
        return results_dir

    return None


def read_csv(path: Path) -> List[Dict[str, str]]:
    """
    Lee un archivo CSV y devuelve una lista de diccionarios.
    """

    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader)


# ------------------------------------------------------------
# Validación principal
# ------------------------------------------------------------

def validate_run_directory(run_dir: Path) -> List[Dict[str, str]]:
    """
    Ejecuta todas las validaciones sobre una carpeta de resultados.
    """

    issues: List[Dict[str, str]] = []

    raw_path = run_dir / RAW_RESULTS_FILENAME
    comparison_path = run_dir / COMPARISON_RESULTS_FILENAME

    if not raw_path.exists():
        add_issue(
            issues,
            ERROR,
            "missing_file",
            f"No existe {RAW_RESULTS_FILENAME} en {run_dir}.",
        )
        return issues

    raw_rows = read_csv(raw_path)

    if not raw_rows:
        add_issue(
            issues,
            ERROR,
            "empty_raw_results",
            f"{RAW_RESULTS_FILENAME} está vacío.",
        )
        return issues

    validate_required_columns(raw_rows, issues)
    validate_numeric_ranges(raw_rows, issues)
    validate_customer_consistency(raw_rows, issues)
    validate_employee_utilization(raw_rows, issues)
    validate_duplicate_rows(raw_rows, issues)
    validate_paired_scenarios(raw_rows, issues)

    if comparison_path.exists():
        comparison_rows = read_csv(comparison_path)
        validate_comparison_results(raw_rows, comparison_rows, issues)
    else:
        add_issue(
            issues,
            WARNING,
            "missing_comparison_file",
            f"No se encontró {COMPARISON_RESULTS_FILENAME}. Se omite validación de comparación.",
        )

    add_summary_information(raw_rows, issues)

    return issues


# ------------------------------------------------------------
# Validaciones específicas
# ------------------------------------------------------------

def validate_required_columns(rows: List[Dict[str, str]], issues: List[Dict[str, str]]) -> None:
    """
    Verifica que raw_results.csv tenga las columnas mínimas esperadas.
    """

    required_columns = [
        "config_id",
        "replication",
        "scenario",
        "seed",
        "total_customers",
        "completed_customers",
        "delayed_customers",
        "delayed_percentage",
        "average_wait",
        "max_wait",
        "employee_1_utilization",
        "employee_2_utilization",
        "employee_3_utilization",
    ]

    available_columns = set(rows[0].keys())

    for column in required_columns:
        if column not in available_columns:
            add_issue(
                issues,
                ERROR,
                "missing_column",
                f"Falta la columna obligatoria en raw_results.csv: {column}",
            )


def validate_numeric_ranges(rows: List[Dict[str, str]], issues: List[Dict[str, str]]) -> None:
    """
    Valida que los valores numéricos básicos estén en rangos razonables.
    """

    non_negative_columns = [
        "total_customers",
        "completed_customers",
        "delayed_customers",
        "average_wait",
        "max_wait",
        "average_queue_length",
        "employee_1_busy_time",
        "employee_2_busy_time",
        "employee_3_busy_time",
        "employee_1_utilization",
        "employee_2_utilization",
        "employee_3_utilization",
        "mean_interarrival_normal",
        "mean_interarrival_peak",
    ]

    percentage_columns = [
        "delayed_percentage",
    ]

    utilization_columns = [
        "employee_1_utilization",
        "employee_2_utilization",
        "employee_3_utilization",
    ]

    for index, row in enumerate(rows, start=2):
        row_id = describe_row(row, index)

        for column in non_negative_columns:
            if column not in row:
                continue

            value = to_float(row[column])

            if value is None:
                add_issue(
                    issues,
                    ERROR,
                    "invalid_number",
                    f"{row_id}: valor no numérico en {column}: {row[column]}",
                )
                continue

            if value < 0:
                add_issue(
                    issues,
                    ERROR,
                    "negative_value",
                    f"{row_id}: {column} no puede ser negativo. Valor={value}",
                )

        for column in percentage_columns:
            if column not in row:
                continue

            value = to_float(row[column])

            if value is None:
                add_issue(
                    issues,
                    ERROR,
                    "invalid_percentage",
                    f"{row_id}: valor no numérico en {column}: {row[column]}",
                )
                continue

            if value < 0 or value > 100:
                add_issue(
                    issues,
                    ERROR,
                    "percentage_out_of_range",
                    f"{row_id}: {column} debe estar entre 0 y 100. Valor={value}",
                )

        for column in utilization_columns:
            if column not in row:
                continue

            value = to_float(row[column])

            if value is None:
                continue

            if value > 1.25:
                add_issue(
                    issues,
                    WARNING,
                    "high_utilization",
                    (
                        f"{row_id}: {column} es mayor que 1.25. "
                        f"Valor={value}. Revisa si la utilización se está calculando "
                        "contra la jornada o contra la duración real de la simulación."
                    ),
                )


def validate_customer_consistency(rows: List[Dict[str, str]], issues: List[Dict[str, str]]) -> None:
    """
    Valida consistencia entre clientes totales, completados y demorados.
    """

    for index, row in enumerate(rows, start=2):
        row_id = describe_row(row, index)

        total = to_int(row.get("total_customers"))
        completed = to_int(row.get("completed_customers"))
        delayed = to_int(row.get("delayed_customers"))
        average_wait = to_float(row.get("average_wait"))
        max_wait = to_float(row.get("max_wait"))

        if total is None or completed is None or delayed is None:
            continue

        if completed != total:
            add_issue(
                issues,
                ERROR,
                "customers_not_completed",
                f"{row_id}: completed_customers={completed} pero total_customers={total}.",
            )

        if delayed > total:
            add_issue(
                issues,
                ERROR,
                "delayed_greater_than_total",
                f"{row_id}: delayed_customers={delayed} es mayor que total_customers={total}.",
            )

        if average_wait is not None and max_wait is not None:
            if max_wait + 1e-9 < average_wait:
                add_issue(
                    issues,
                    ERROR,
                    "max_wait_less_than_average",
                    f"{row_id}: max_wait={max_wait} es menor que average_wait={average_wait}.",
                )


def validate_employee_utilization(rows: List[Dict[str, str]], issues: List[Dict[str, str]]) -> None:
    """
    Valida la utilización del empleado extra en cada escenario.
    """

    for index, row in enumerate(rows, start=2):
        row_id = describe_row(row, index)

        scenario = row.get("scenario")
        emp3_utilization = to_float(row.get("employee_3_utilization"))

        if emp3_utilization is None:
            continue

        if scenario == "two_employees":
            if abs(emp3_utilization) > 1e-9:
                add_issue(
                    issues,
                    ERROR,
                    "employee_3_used_in_base_scenario",
                    (
                        f"{row_id}: employee_3_utilization debe ser 0 en escenario base. "
                        f"Valor={emp3_utilization}"
                    ),
                )

        elif scenario == "extra_employee_peak":
            if emp3_utilization <= 0:
                add_issue(
                    issues,
                    WARNING,
                    "employee_3_not_used_in_extra_scenario",
                    (
                        f"{row_id}: employee_3_utilization es 0 o negativa en escenario con "
                        f"empleado extra. Valor={emp3_utilization}"
                    ),
                )


def validate_duplicate_rows(rows: List[Dict[str, str]], issues: List[Dict[str, str]]) -> None:
    """
    Detecta filas duplicadas por configuración, réplica y escenario.
    """

    seen = set()

    for index, row in enumerate(rows, start=2):
        key = (
            row.get("config_id"),
            row.get("replication"),
            row.get("scenario"),
        )

        if key in seen:
            add_issue(
                issues,
                ERROR,
                "duplicate_result_row",
                (
                    f"Fila {index}: resultado duplicado para "
                    f"config_id={key[0]}, replication={key[1]}, scenario={key[2]}."
                ),
            )

        seen.add(key)


def validate_paired_scenarios(rows: List[Dict[str, str]], issues: List[Dict[str, str]]) -> None:
    """
    Valida que cada configuración y réplica tenga ambos escenarios:
    - two_employees
    - extra_employee_peak

    También revisa que ambos escenarios tengan la misma cantidad de clientes,
    porque se supone que usan la misma semilla y la misma demanda.
    """

    grouped = group_raw_rows(rows)

    for key, scenarios in grouped.items():
        config_id, replication = key

        base = scenarios.get("two_employees")
        extra = scenarios.get("extra_employee_peak")

        if base is None:
            add_issue(
                issues,
                ERROR,
                "missing_base_scenario",
                f"Falta escenario two_employees para config_id={config_id}, replication={replication}.",
            )

        if extra is None:
            add_issue(
                issues,
                ERROR,
                "missing_extra_scenario",
                f"Falta escenario extra_employee_peak para config_id={config_id}, replication={replication}.",
            )

        if base is None or extra is None:
            continue

        base_total = to_int(base.get("total_customers"))
        extra_total = to_int(extra.get("total_customers"))

        if base_total is not None and extra_total is not None:
            if base_total != extra_total:
                add_issue(
                    issues,
                    WARNING,
                    "different_demand_between_scenarios",
                    (
                        f"config_id={config_id}, replication={replication}: "
                        f"total_customers base={base_total}, extra={extra_total}. "
                        "Si se usa la misma semilla, normalmente deberían coincidir."
                    ),
                )

        base_seed = base.get("seed")
        extra_seed = extra.get("seed")

        if base_seed != extra_seed:
            add_issue(
                issues,
                WARNING,
                "different_seed_between_scenarios",
                (
                    f"config_id={config_id}, replication={replication}: "
                    f"seed base={base_seed}, seed extra={extra_seed}."
                ),
            )


def validate_comparison_results(
    raw_rows: List[Dict[str, str]],
    comparison_rows: List[Dict[str, str]],
    issues: List[Dict[str, str]],
) -> None:
    """
    Valida que comparison_results.csv sea coherente con raw_results.csv.
    """

    raw_grouped = group_raw_rows(raw_rows)

    comparison_keys = set()

    for index, row in enumerate(comparison_rows, start=2):
        config_id = row.get("config_id")
        replication = row.get("replication")
        key = (config_id, replication)

        comparison_keys.add(key)

        scenarios = raw_grouped.get(key)

        if scenarios is None:
            add_issue(
                issues,
                ERROR,
                "comparison_without_raw_pair",
                (
                    f"Fila {index} de comparison_results.csv no tiene par correspondiente "
                    f"en raw_results.csv: config_id={config_id}, replication={replication}."
                ),
            )
            continue

        base = scenarios.get("two_employees")
        extra = scenarios.get("extra_employee_peak")

        if base is None or extra is None:
            continue

        expected_delayed_improvement = (
            to_float(base.get("delayed_percentage")) -
            to_float(extra.get("delayed_percentage"))
        )

        reported_delayed_improvement = to_float(
            row.get("delayed_percentage_improvement")
        )

        if expected_delayed_improvement is None or reported_delayed_improvement is None:
            continue

        if abs(expected_delayed_improvement - reported_delayed_improvement) > 1e-6:
            add_issue(
                issues,
                ERROR,
                "incorrect_delayed_improvement",
                (
                    f"Fila {index}: delayed_percentage_improvement incorrecto. "
                    f"Esperado={expected_delayed_improvement}, "
                    f"Reportado={reported_delayed_improvement}."
                ),
            )

    expected_keys = set(raw_grouped.keys())

    missing_comparisons = expected_keys - comparison_keys

    for config_id, replication in sorted(missing_comparisons):
        scenarios = raw_grouped[(config_id, replication)]

        if "two_employees" in scenarios and "extra_employee_peak" in scenarios:
            add_issue(
                issues,
                WARNING,
                "missing_comparison_row",
                (
                    f"Falta comparación para config_id={config_id}, "
                    f"replication={replication}."
                ),
            )


# ------------------------------------------------------------
# Información resumen
# ------------------------------------------------------------

def add_summary_information(rows: List[Dict[str, str]], issues: List[Dict[str, str]]) -> None:
    """
    Agrega información útil al reporte final como mensajes informativos.
    """

    grouped_by_config = {}

    for row in rows:
        config_id = row.get("config_id", "unknown")

        if config_id not in grouped_by_config:
            grouped_by_config[config_id] = []

        grouped_by_config[config_id].append(row)

    for config_id, config_rows in sorted(grouped_by_config.items()):
        base_values = []
        extra_values = []

        for row in config_rows:
            scenario = row.get("scenario")
            delayed_percentage = to_float(row.get("delayed_percentage"))

            if delayed_percentage is None:
                continue

            if scenario == "two_employees":
                base_values.append(delayed_percentage)
            elif scenario == "extra_employee_peak":
                extra_values.append(delayed_percentage)

        if base_values and extra_values:
            base_mean = sum(base_values) / len(base_values)
            extra_mean = sum(extra_values) / len(extra_values)
            improvement = base_mean - extra_mean

            add_issue(
                issues,
                "INFO",
                "summary_delayed_percentage",
                (
                    f"config_id={config_id}: delayed_percentage promedio "
                    f"base={base_mean:.4f}, extra={extra_mean:.4f}, "
                    f"mejora={improvement:.4f} puntos porcentuales."
                ),
            )


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

def group_raw_rows(rows: List[Dict[str, str]]) -> Dict[Tuple[str, str], Dict[str, Dict[str, str]]]:
    """
    Agrupa raw_results por config_id y replication.

    Retorna:

        {
            (config_id, replication): {
                "two_employees": {...},
                "extra_employee_peak": {...}
            }
        }
    """

    grouped: Dict[Tuple[str, str], Dict[str, Dict[str, str]]] = {}

    for row in rows:
        key = (
            row.get("config_id"),
            row.get("replication"),
        )

        scenario = row.get("scenario")

        if key not in grouped:
            grouped[key] = {}

        grouped[key][scenario] = row

    return grouped


def add_issue(
    issues: List[Dict[str, str]],
    severity: str,
    code: str,
    message: str,
) -> None:
    """
    Agrega un mensaje de validación.
    """

    issues.append(
        {
            "severity": severity,
            "code": code,
            "message": message,
        }
    )


def count_issues(issues: List[Dict[str, str]], severity: str) -> int:
    """
    Cuenta mensajes por severidad.
    """

    return sum(1 for issue in issues if issue["severity"] == severity)


def write_validation_report(run_dir: Path, issues: List[Dict[str, str]]) -> Path:
    """
    Escribe el reporte de validación en un archivo de texto.
    """

    report_path = run_dir / VALIDATION_REPORT_FILENAME

    errors = [issue for issue in issues if issue["severity"] == ERROR]
    warnings = [issue for issue in issues if issue["severity"] == WARNING]
    info_messages = [issue for issue in issues if issue["severity"] == "INFO"]

    with report_path.open("w", encoding="utf-8") as file:
        file.write("Validation report\n")
        file.write("=================\n\n")
        file.write(f"Run directory: {run_dir}\n\n")

        file.write("Summary\n")
        file.write("-------\n")
        file.write(f"Errors: {len(errors)}\n")
        file.write(f"Warnings: {len(warnings)}\n")
        file.write(f"Info: {len(info_messages)}\n\n")

        write_issue_section(file, "Errors", errors)
        write_issue_section(file, "Warnings", warnings)
        write_issue_section(file, "Information", info_messages)

    return report_path


def write_issue_section(file, title: str, issues: List[Dict[str, str]]) -> None:
    """
    Escribe una sección del reporte.
    """

    file.write(f"{title}\n")
    file.write("-" * len(title))
    file.write("\n")

    if not issues:
        file.write("None\n\n")
        return

    for index, issue in enumerate(issues, start=1):
        file.write(f"{index}. [{issue['severity']}] {issue['code']}\n")
        file.write(f"   {issue['message']}\n\n")


def describe_row(row: Dict[str, str], index: int) -> str:
    """
    Devuelve una descripción corta de una fila para mensajes de error.
    """

    return (
        f"Fila {index} "
        f"(config_id={row.get('config_id')}, "
        f"replication={row.get('replication')}, "
        f"scenario={row.get('scenario')})"
    )


def to_float(value) -> Optional[float]:
    """
    Convierte un valor a float. Si no puede, devuelve None.
    """

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value) -> Optional[int]:
    """
    Convierte un valor a int. Si no puede, devuelve None.
    """

    if value is None:
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()