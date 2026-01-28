import logging
import sys
from functools import lru_cache


class UnbufferedStreamHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()


@lru_cache(maxsize=None)
def get_logger(name: str = None) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        handler = UnbufferedStreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
