import math
from typing import Iterable, List


def to_float_list(values: Iterable[float]) -> List[float]:
    """
    Convierte una colección de valores numéricos en una lista de floats.
    """

    return [float(value) for value in values]


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
    """
    error_estándar = desviación_estándar / sqrt(n)
    """

    data = to_float_list(values)

    if len(data) <= 1:
        return 0.0

    return std(data) / math.sqrt(len(data))


def confidence_interval_95(values: Iterable[float]) -> tuple[float, float]:
    """
    Calcula un intervalo de confianza aproximado del 95 % para la media.
        media ± 1.96 * error_estándar
    """

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