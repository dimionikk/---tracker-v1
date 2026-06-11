import logging
from logging.handlers import RotatingFileHandler

from tools.common import DATA_DIR

LOG_FILE = DATA_DIR / "app.log"

_logger = logging.getLogger("moi_instrumenty")
_logger.setLevel(logging.INFO)
_logger.propagate = False

if not _logger.handlers:
    _handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(tag)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    _logger.addHandler(_handler)


def log(tag: str, message: str):
    """Записати подію в журнал програми (data/app.log)."""
    try:
        _logger.info(message, extra={"tag": tag})
    except Exception:
        pass
