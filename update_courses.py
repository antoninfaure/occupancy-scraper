from pymongo import MongoClient
from config import *
import utils
from tqdm import tqdm
from datetime import datetime
import db_utils
from bson.objectid import ObjectId

# Connect to MongoDB
client = MongoClient(f"mongodb+srv://{DB_USER}:{DB_PASSWORD}@{DB_URL}/?retryWrites=true&w=majority")
db = client[DB_NAME]
db_utils.init(db)

# Parse all courses from edu.epfl.ch
courses = utils.parse_all_courses()

# Filter duplicates
unique_courses = utils.filter_duplicates_courses(courses)

# Create courses in DB
utils.create_courses(db, unique_courses)

# Create teachers in DB
utils.create_teachers(db, unique_courses)

# Assign teachers to courses
utils.add_teachers_to_courses(db, unique_courses)



# Create semesters
utils.create_new_semester(db,
    name="Semestre de printemps 2023-2024",
    start_date=datetime(2024, 2, 19),
    end_date=datetime(2024, 5, 31),
    skip_dates=[
        datetime(2024, 3, 29),
        datetime(2024, 4, 1),
        datetime(2024, 4, 2),
        datetime(2024, 4, 3),
        datetime(2024, 4, 4),
        datetime(2024, 4, 5),
        datetime(2024, 5, 9),
        datetime(2024, 5, 20),
    ],
    type="spring",
    available=True
)

utils.create_new_semester(db,
    name="2023-2024",
    start_date=datetime(2024, 9, 1),
    end_date=datetime(2024, 8, 30),
    skip_dates=[
        datetime(2023, 9, 18),
        datetime(2024, 3, 29),
        datetime(2024, 4, 1),
        datetime(2024, 4, 2),
        datetime(2024, 4, 3),
        datetime(2024, 4, 4),
        datetime(2024, 4, 5),
        datetime(2024, 5, 9),
        datetime(2024, 5, 20),
    ],
    type="year",
    available=True
)

# Create units
utils.create_units(db, unique_courses)

# Create study plans
utils.create_studyplans(db, unique_courses)

# Create planned in (courses in study plans)
utils.create_planned_in(db, unique_courses)

print("--- Done ---")

