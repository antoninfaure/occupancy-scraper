import logging

import fire
from dotenv import load_dotenv

from db_utils import init_and_connect
from settings import Settings
from utils import (
    create_courses_bookings,
    create_rooms,
    find_courses_schedules,
    update_schedules,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings()

    db = init_and_connect(settings)
    # Get schedules from edu.epfl.ch for the current or next semester
    logger.info("Getting schedules...")
    schedules = find_courses_schedules(db)

    # Create rooms in DB
    logger.info("Creating rooms...")
    create_rooms(db, schedules)

    # Update schedules in DB
    logger.info("Updating schedules...")
    update_schedules(db, schedules)

    # Create bookings
    logger.info("Creating bookings...")
    create_courses_bookings(db, schedules=schedules)

    logger.info("===== Done =====")


if __name__ == "__main__":
    fire.Fire(main)
