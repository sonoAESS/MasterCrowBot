# logger.py
import logging
import os
from constants import LOGS_FOLDER


def setup_logger(name, log_file, level=logging.INFO):
    """Configura y retorna un logger."""
    # Ensure logs directory exists
    os.makedirs(LOGS_FOLDER, exist_ok=True)

    # Create the full path for the log file
    log_path = os.path.join(LOGS_FOLDER, log_file)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    handler = logging.FileHandler(log_path)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    # Evitar que los logs se propaguen a otros loggers
    logger.propagate = False

    return logger


data_logger = setup_logger("data_logger", "data.log")
ai_logger = setup_logger("ai_logger", "ai.log")
