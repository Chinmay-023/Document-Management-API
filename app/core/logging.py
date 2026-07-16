import logging
import sys
from app.core.config import settings


def setup_logging() -> None:
    # Get level from config string
    log_level_str = settings.LOG_LEVEL.upper()
    level = getattr(logging, log_level_str, logging.INFO)

    # Define standard format
    log_format = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Suppress noise from third-party libraries if needed
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logger = logging.getLogger("app")
    logger.info(f"Logging initialized with level: {log_level_str}")


# Execute configuration on import
setup_logging()
logger = logging.getLogger("app")
