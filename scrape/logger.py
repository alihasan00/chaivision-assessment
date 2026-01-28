import logging
import sys
from functools import lru_cache


class UnbufferedStreamHandler(logging.StreamHandler):
    """StreamHandler that flushes after each log message for immediate output."""

    def emit(self, record):
        super().emit(record)
        self.flush()


@lru_cache(maxsize=None)
def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance with consistent configuration.

    Args:
        name: Logger name (typically __name__). If None, uses root logger.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Create console handler with unbuffered output
        handler = UnbufferedStreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

    return logger
