import logging
from datetime import datetime

import fire
from dotenv import load_dotenv

from db_utils import init_and_connect
from entity_types import CourseScraped
from settings import Settings
from utils import (
    add_teachers_to_courses,
    create_courses,
    create_new_semester,
    create_planned_in,
    create_studyplans,
    create_teachers,
    create_units,
    filter_duplicates_courses,
    parse_all_courses,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to MongoDB


def main() -> None:
    settings = Settings()
    db = init_and_connect(settings)

    # Parse all courses from edu.epfl.ch
    logger.info("Parsing all courses...")
    courses: list[CourseScraped] = parse_all_courses()

    # Filter duplicates
    logger.info("Filtering duplicates...")
    unique_courses: list[CourseScraped] = filter_duplicates_courses(courses)

    # Create courses in DB
    logger.info("Creating courses...")
    create_courses(db, unique_courses)

    # Create teachers in DB
    logger.info("Creating teachers...")
    create_teachers(db, unique_courses)

    # Assign teachers to courses
    logger.info("Assigning teachers to courses...")
    add_teachers_to_courses(db, unique_courses)

    # Create semesters

    # Fall 2024-2025
    # skip_dates = [
    #     datetime(2024, 9, 16),
    #     datetime(2024, 10, 21),
    #     datetime(2024, 10, 22),
    #     datetime(2024, 10, 23),
    #     datetime(2024, 10, 24),
    #     datetime(2024, 10, 25),
    #     datetime(2025, 4, 18),
    #     datetime(2025, 4, 21),
    #     datetime(2025, 4, 22),
    #     datetime(2025, 4, 23),
    #     datetime(2025, 4, 24),
    #     datetime(2025, 4, 25),
    #     datetime(2025, 5, 29),
    # ]

    # utils.create_new_semester(db,
    #     name="Semestre d'automne 2024-2025",
    #     start_date=datetime(2024, 9, 9),
    #     end_date=datetime(2024, 12, 22),
    #     skip_dates=skip_dates,
    #     type="fall",
    #     available=True
    # )

    # utils.create_new_semester(db,
    #     name="2024-2025",
    #     start_date=datetime(2024, 9, 9),
    #     end_date=datetime(2025, 6, 1),
    #     skip_dates=skip_dates,
    #     type="year",
    #     available=True
    # )

    skip_dates = [
        datetime(2025, 9, 22),
        datetime(2025, 10, 20),
        datetime(2025, 10, 21),
        datetime(2025, 10, 22),
        datetime(2025, 10, 23),
        datetime(2025, 10, 24),
        datetime(2026, 4, 6),
        datetime(2026, 4, 7),
        datetime(2026, 4, 8),
        datetime(2026, 4, 9),
        datetime(2026, 4, 10),
        datetime(2026, 5, 14),
        datetime(2026, 5, 25),
    ]

    # Fall 2025-2026
    logger.info("Creating semesters...")
    create_new_semester(
        db,
        name="Semestre d'automne 2025-2026",
        start_date=datetime(2025, 9, 8),
        end_date=datetime(2025, 12, 21),
        skip_dates=skip_dates,
        type="fall",
        available=True,
    )
    # Spring 2025-2026
    create_new_semester(
        db,
        name="Semestre de printemps 2025-2026",
        start_date=datetime(2026, 2, 16),
        end_date=datetime(2026, 5, 31),
        skip_dates=skip_dates,
        type="spring",
        available=True,
    )
    # Year 2025-2026
    create_new_semester(
        db,
        name="2025-2026",
        start_date=datetime(2025, 9, 8),
        end_date=datetime(2026, 5, 31),
        skip_dates=skip_dates,
        type="year",
        available=True,
    )
    # Create units
    logger.info("Creating units...")
    create_units(db, unique_courses)

    # Create study plans
    logger.info("Creating study plans...")
    create_studyplans(db, unique_courses)

    # Create planned in (courses in study plans)
    logger.info("Creating planned in...")
    create_planned_in(db, unique_courses)

    logger.info("=== Done ===")


if __name__ == "__main__":
    fire.Fire(main)
