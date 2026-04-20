from __future__ import annotations

import logging
import subprocess
import traceback
from pathlib import Path

HOME = Path.home()
APP_BUNDLE = Path("/Applications/IRIS.app")
LOG_DIR = HOME / "Library" / "Logs" / "IRIS"
LOG_FILE = LOG_DIR / "launcher.log"


def setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("iris.native.compat")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    logger.addHandler(handler)
    return logger


logger = setup_logger()


def main() -> None:
    logger.info("legacy-launcher:start")
    try:
        if not APP_BUNDLE.exists():
            raise RuntimeError(f"IRIS app bundle introuvable: {APP_BUNDLE}")
        subprocess.Popen(
            ["open", "-a", str(APP_BUNDLE)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info("legacy-launcher:redirected-to-app %s", APP_BUNDLE)
    except Exception:
        logger.error("legacy-launcher:exception\n%s", traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
