import os
import sys
import time
from logging import INFO, Formatter, Handler, Logger, StreamHandler
from typing import Dict, Optional

from concurrent_log_handler import ConcurrentRotatingFileHandler

TAGS_KEY = "tags"


class SplightFormatter(Formatter):
    DEFAULT_FMT: str = (
        "%(levelname)s | %(asctime)s | %(filename)s:%(lineno)d | %(message)s"
    )

    def format(self, record):
        fmt = self.DEFAULT_FMT
        try:
            if record.tags is not None:
                fmt = " | ".join([fmt, "%(tags)s"])
        except AttributeError:
            pass  # tags aren't present
        formatter = Formatter(fmt=fmt, datefmt="%Y-%m-%dT%H:%M:%SZ")
        formatter.converter = time.gmtime
        return formatter.format(record)


class SplightLogger(Logger):
    # TODO: fix lno always printing logging.py:89

    def __init__(self, name: str = None) -> None:
        # this is to avoid adding handlers to root logger
        # and interfering with third party app logs
        self.name = name if name is not None else "splight"
        level = int(os.getenv("LOG_LEVEL", INFO))
        super().__init__(name, level)
        # the co_filename attribute is a property of the code object that
        # specifies the name of the file from which the code was compiled
        self.propagate = False
        self.addHandler(
            standard_output_handler(log_level=level, formatter=self.formatter)
        )
        self.addHandler(
            _file_handler(log_level=level, formatter=self.formatter)
        )

    @property
    def formatter(self) -> Formatter:
        return SplightFormatter()

    @staticmethod
    def _update_kwargs(kwargs: Dict) -> Dict:
        """Format log method tags and save into `extra` logging argument."""
        tags = kwargs.pop(TAGS_KEY, None)
        if tags is not None:
            kwargs.update({"extra": {TAGS_KEY: tags}})
        return kwargs


def standard_output_handler(
    formatter: Optional[Formatter] = SplightFormatter(),
    log_level: Optional[str] = INFO,
) -> Handler:
    handler = StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    return handler


def _file_handler(
    formatter: Optional[Formatter] = SplightFormatter(),
    log_level: Optional[str] = INFO,
) -> Handler:
    filename = os.getenv("SPLIGHT_COMPONENT_LOG_FILE", "/tmp/agent.log")
    max_bytes = int(os.getenv("SPLIGHT_COMPONENT_MAX_BYTES", 5e6))  # 5MB
    backup_count = int(os.getenv("SPLIGHT_COMPONENT_BACKUP_COUNT", 100))

    handler = ConcurrentRotatingFileHandler(
        filename=filename, maxBytes=max_bytes, backupCount=backup_count
    )
    handler.setFormatter(formatter)
    handler.setLevel(log_level)
    return handler
