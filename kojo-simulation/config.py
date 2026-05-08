# Tiempo en minutos desde la apertura:
# 10:00 a.m. -> 0
# 9:00 p.m.  -> 660
DAY_OPEN = 0.0
DAY_CLOSE = 660.0

# Horas pico
# 11:30 a.m. - 1:30 p.m. -> 90 - 210
# 5:00 p.m.  - 7:00 p.m. -> 420 - 540
PEAK_PERIODS = [
    (90.0, 210.0),
    (420.0, 540.0),
]

# Segmentos del día
# (inicio, fin, tipo_de_segmento)
NORMAL = "normal"
PEAK = "peak"

DAY_SEGMENTS = [
    (0.0, 90.0, NORMAL),
    (90.0, 210.0, PEAK),
    (210.0, 420.0, NORMAL),
    (420.0, 540.0, PEAK),
    (540.0, 660.0, NORMAL),
]

# Parámetros de llegada
# Se interpretan como medias del tiempo entre llegadas, en minutos.
MEAN_INTERARRIVAL_NORMAL = 6.0
MEAN_INTERARRIVAL_PEAK = 2.5

INTERARRIVAL_MEANS = {
    NORMAL: MEAN_INTERARRIVAL_NORMAL,
    PEAK: MEAN_INTERARRIVAL_PEAK,
}

# Prob de clientes que desean productos
PRODUCT_SANDWICH = "sandwich"
PRODUCT_SUSHI = "sushi"
P_SANDWICH = 0.5
P_SUSHI = 1.0 - P_SANDWICH


# Tiempos de servicio
SANDWICH_SERVICE_MIN = 3.0
SANDWICH_SERVICE_MAX = 5.0

SUSHI_SERVICE_MIN = 5.0
SUSHI_SERVICE_MAX = 8.0

SERVICE_TIME_RANGES = {
    PRODUCT_SANDWICH: (SANDWICH_SERVICE_MIN, SANDWICH_SERVICE_MAX),
    PRODUCT_SUSHI: (SUSHI_SERVICE_MIN, SUSHI_SERVICE_MAX),
}


WAIT_THRESHOLD = 5.0
BASE_EMPLOYEES = 2
EXTRA_EMPLOYEE_ID = 3

N_REPLICATIONS = 100
DEFAULT_SEED = 1

LOG_ENABLED = True
LOG_LEVEL = "INFO"
LOG_FILE = "logs/simulation.log"


def validate_config() -> None:
    if DAY_OPEN < 0:
        raise ValueError("DAY_OPEN no puede ser negativo.")

    if DAY_CLOSE <= DAY_OPEN:
        raise ValueError("DAY_CLOSE debe ser mayor que DAY_OPEN.")

    if not 0.0 <= P_SANDWICH <= 1.0:
        raise ValueError("P_SANDWICH debe estar entre 0 y 1.")

    if abs((P_SANDWICH + P_SUSHI) - 1.0) > 1e-9:
        raise ValueError("Las probabilidades de productos deben sumar 1.")

    if MEAN_INTERARRIVAL_NORMAL <= 0:
        raise ValueError("MEAN_INTERARRIVAL_NORMAL debe ser positivo.")

    if MEAN_INTERARRIVAL_PEAK <= 0:
        raise ValueError("MEAN_INTERARRIVAL_PEAK debe ser positivo.")

    for product, (minimum, maximum) in SERVICE_TIME_RANGES.items():
        if minimum <= 0:
            raise ValueError(f"El tiempo mínimo de {product} debe ser positivo.")
        if maximum < minimum:
            raise ValueError(f"Rango de servicio inválido para {product}.")

    for start, end, segment_type in DAY_SEGMENTS:
        if start < DAY_OPEN or end > DAY_CLOSE:
            raise ValueError(f"Segmento fuera del horario del día: {segment_type}.")
        if end <= start:
            raise ValueError(f"Segmento inválido: {segment_type}.")
        if segment_type not in INTERARRIVAL_MEANS:
            raise ValueError(f"Tipo de segmento desconocido: {segment_type}.")