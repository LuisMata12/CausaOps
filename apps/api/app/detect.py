import argparse
import logging
import time

from app.config import get_settings
from app.database import SessionLocal
from app.detection import run_detection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def run_once() -> None:
    with SessionLocal() as db:
        result = run_detection(db)
    logger.info("detection_run %s", result.as_dict())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic CausaOps detection rules")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument(
        "--interval",
        type=int,
        default=get_settings().detection_interval_seconds,
        help="Seconds between detection runs",
    )
    args = parser.parse_args()
    if not args.loop:
        run_once()
        return
    logger.info("detector_started interval_seconds=%s", args.interval)
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("detection_run_failed")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
