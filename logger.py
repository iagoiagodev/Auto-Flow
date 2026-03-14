"""
logger.py — Log persistente do AutoFlow.
Grava em logs/autoflow_YYYYMMDD.log com rotacao de 7 dias.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
LOGS_DIR = BASE / "logs"


def _setup() -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)

    # Limpa logs com mais de 7 dias
    for f in LOGS_DIR.glob("autoflow_*.log"):
        try:
            date_str = f.stem.replace("autoflow_", "")
            file_date = datetime.strptime(date_str, "%Y%m%d")
            if (datetime.now() - file_date).days > 7:
                f.unlink()
        except Exception:
            pass

    log_file = LOGS_DIR / f"autoflow_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger("autoflow")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.addHandler(fh)

    return logger


def _mask(value: str) -> str:
    """Mascara valores potencialmente sensiveis (senhas, tokens)."""
    lower = value.lower()
    sensitive_keys = ("senha", "password", "token", "secret", "key", "auth", "pass")
    if any(k in lower for k in sensitive_keys):
        return "***"
    return value if len(value) <= 80 else value[:77] + "..."


log = _setup()
