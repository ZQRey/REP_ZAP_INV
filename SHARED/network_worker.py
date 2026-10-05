"""Continuous MAC discovery, independent of an open browser."""
import logging
import os
import time
from SHARED.database import SessionLocal
from SHARED.models import NetworkSwitch
from LOCATION.app.services.switch_integration_service import SwitchIntegrationService

logger = logging.getLogger(__name__)

def process_once():
    with SessionLocal() as db:
        ids = [row[0] for row in db.query(NetworkSwitch.id).all()]
    for switch_id in ids:
        with SessionLocal() as db:
            try:
                SwitchIntegrationService.poll_switch(db, switch_id)
            except Exception as exc:
                db.rollback()
                logger.warning("Switch #%s discovery failed: %s", switch_id, type(exc).__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            process_once()
        except Exception as exc:
            logger.warning("Discovery cycle failed: %s", type(exc).__name__)
        time.sleep(max(15, int(os.getenv("NETWORK_POLL_SECONDS", "60"))))
