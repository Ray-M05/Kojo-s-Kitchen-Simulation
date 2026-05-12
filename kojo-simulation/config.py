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
EXPERIMENT_CONFIGS = [
    {
        "config_id": "arrival_normal_6_peak_2_5",
        "mean_interarrival_normal": 6.0,
        "mean_interarrival_peak": 2.5,
    },
    {
        "config_id": "arrival_normal_6_peak_2_0",
        "mean_interarrival_normal": 6.0,
        "mean_interarrival_peak": 2.0,
    },
    {
        "config_id": "arrival_normal_5_peak_2_5",
        "mean_interarrival_normal": 5.0,
        "mean_interarrival_peak": 2.5,
    },
    {
        "config_id": "arrival_normal_8_peak_2_0",
        "mean_interarrival_normal": 8.0,
        "mean_interarrival_peak": 2.0,
    },
    {
        "config_id": "arrival_normal_10_peak_7_5",
        "mean_interarrival_normal": 10.0,
        "mean_interarrival_peak": 7.5,
    },
    {
        "config_id": "arrival_normal_4_peak_2_0",
        "mean_interarrival_normal": 4.0,
        "mean_interarrival_peak": 2.0,
    },
    {
        "config_id": "arrival_normal_7_peak_5_5",
        "mean_interarrival_normal": 7.0,
        "mean_interarrival_peak": 5.5,
    }
]

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

N_REPLICATIONS = 10
DEFAULT_SEED = 1

LOG_ENABLED = True
LOG_LEVEL = "DEBUG"
LOG_FILE = "logs/simulation.log"


def validate_experiment_config(experiment_config: dict) -> None:

    required_keys = [
        "config_id",
        "mean_interarrival_normal",
        "mean_interarrival_peak",
    ]

    for key in required_keys:
        if key not in experiment_config:
            raise ValueError(f"Falta la clave '{key}' en EXPERIMENT_CONFIGS.")

    if experiment_config["mean_interarrival_normal"] <= 0:
        raise ValueError(
            f"mean_interarrival_normal debe ser positivo en {experiment_config['config_id']}."
        )

    if experiment_config["mean_interarrival_peak"] <= 0:
        raise ValueError(
            f"mean_interarrival_peak debe ser positivo en {experiment_config['config_id']}."
        )



def validate_config() -> None:
    if DAY_OPEN < 0:
        raise ValueError("DAY_OPEN no puede ser negativo.")

    if DAY_CLOSE <= DAY_OPEN:
        raise ValueError("DAY_CLOSE debe ser mayor que DAY_OPEN.")

    if not 0.0 <= P_SANDWICH <= 1.0:
        raise ValueError("P_SANDWICH debe estar entre 0 y 1.")

    if abs((P_SANDWICH + P_SUSHI) - 1.0) > 1e-9:
        raise ValueError("Las probabilidades de productos deben sumar 1.")

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

    if not EXPERIMENT_CONFIGS:
        raise ValueError("Debe existir al menos una configuración experimental.")

    for experiment_config in EXPERIMENT_CONFIGS:
        validate_experiment_config(experiment_config)