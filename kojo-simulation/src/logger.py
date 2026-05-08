import logging
import os

def setup_logger(
    enabled: bool = True,
    level: str = "INFO",
    log_file: str = "logs/simulation.log",
) -> logging.Logger:

    logger = logging.getLogger("kojo")
    logger.handlers.clear()
    logger.propagate = False

    if not enabled:
        logger.addHandler(logging.NullHandler())
        logger.disabled = True
        return logger

    logger.disabled = False

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    log_directory = os.path.dirname(log_file)

    if log_directory:
        os.makedirs(log_directory, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        log_file,
        mode="w",
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger