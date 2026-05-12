import math
from typing import Iterable, List, Optional
DEFAULT_NDIGITS = 4


def to_float_list(values: Iterable[float]) -> List[float]:
    """
    Convert numeric values to floats.
    """

    data = []

    for value in values:
        if value is None:
            continue
        data.append(float(value))

    return data


def rounded(value: Optional[float], ndigits: Optional[int] = DEFAULT_NDIGITS):
    if value is None:
        return None

    if ndigits is None:
        return float(value)

    return round(float(value), ndigits)


def mean(values: Iterable[float]) -> float:
    data = to_float_list(values)

    if not data:
        return 0.0

    return sum(data) / len(data)


def variance(values: Iterable[float]) -> float:
    data = to_float_list(values)

    if len(data) <= 1:
        return 0.0

    avg = mean(data)
    return sum((value - avg) ** 2 for value in data) / (len(data) - 1)


def std(values: Iterable[float]) -> float:
    return math.sqrt(variance(values))


def standard_error(values: Iterable[float]) -> float:
    data = to_float_list(values)

    if len(data) <= 1:
        return 0.0

    return std(data) / math.sqrt(len(data))


def confidence_interval_95(values: Iterable[float]) -> tuple[float, float]:
    data = to_float_list(values)
    avg = mean(data)

    if len(data) <= 1:
        return avg, avg

    margin = 1.96 * standard_error(data)
    return avg - margin, avg + margin


def minimum(values: Iterable[float]) -> float:
    data = to_float_list(values)
    return min(data) if data else 0.0


def maximum(values: Iterable[float]) -> float:
    data = to_float_list(values)
    return max(data) if data else 0.0


def summarize(values: Iterable[float]) -> dict:

    data = to_float_list(values)
    ci_low, ci_high = confidence_interval_95(data)

    return {
        "count": len(data),
        "mean": mean(data),
        "std": std(data),
        "min": minimum(data),
        "max": maximum(data),
        "ci95_low": ci_low,
        "ci95_high": ci_high,
    }

def summarize_for_json(
    values: Iterable[float],
    unit: Optional[str] = None,
    ndigits: Optional[int] = DEFAULT_NDIGITS,
) -> dict:

    data = to_float_list(values)

    if not data:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
            "ci95": {
                "low": None,
                "high": None,
            },
            "unit": unit,
        }

    stats = summarize(data)

    return {
        "count": stats["count"],
        "mean": rounded(stats["mean"], ndigits),
        "std": rounded(stats["std"], ndigits),
        "min": rounded(stats["min"], ndigits),
        "max": rounded(stats["max"], ndigits),
        "ci95": {
            "low": rounded(stats["ci95_low"], ndigits),
            "high": rounded(stats["ci95_high"], ndigits),
        },
        "unit": unit,
    }


def relative_reduction_percent(base_value: float, alternative_value: float) -> Optional[float]:
    """
    Relative reduction using the base scenario as denominator.
        (base_value - alternative_value) / base_value * 100
    """

    if base_value == 0:
        return None

    return 100.0 * (base_value - alternative_value) / base_value


def improvement_for_json(
    base_value: float,
    alternative_value: float,
    unit: Optional[str] = None,
    ndigits: Optional[int] = DEFAULT_NDIGITS,
) -> dict:
    improvement = base_value - alternative_value
    relative = relative_reduction_percent(base_value, alternative_value)

    return {
        "base": rounded(base_value, ndigits),
        "with_extra": rounded(alternative_value, ndigits),
        "improvement": rounded(improvement, ndigits),
        "relative_reduction_percent": rounded(relative, ndigits),
        "unit": unit,
    }


def summarize_improvement_for_json(
    base_values: Iterable[float],
    alternative_values: Iterable[float],
    unit: Optional[str] = None,
    ndigits: Optional[int] = DEFAULT_NDIGITS,
) -> dict:
    base_data = to_float_list(base_values)
    alternative_data = to_float_list(alternative_values)

    if len(base_data) != len(alternative_data):
        raise ValueError(
            "base_values and alternative_values must have the same length."
        )

    improvements = [
        base_value - alternative_value
        for base_value, alternative_value in zip(base_data, alternative_data)
    ]

    relative_reductions = [
        relative_reduction_percent(base_value, alternative_value)
        for base_value, alternative_value in zip(base_data, alternative_data)
    ]

    return {
        "base": summarize_for_json(base_data, unit=unit, ndigits=ndigits),
        "with_extra": summarize_for_json(alternative_data, unit=unit, ndigits=ndigits),
        "improvement": summarize_for_json(improvements, unit=unit, ndigits=ndigits),
        "relative_reduction_percent": summarize_for_json(
            relative_reductions,
            unit="percent",
            ndigits=ndigits,
        ),
    }
