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

# Create units
utils.create_units(db, unique_courses)

# Create study plans
utils.create_studyplans(db, unique_courses)

# Create planned in (courses in study plans)
utils.create_planned_in(db, unique_courses)

print("--- Done ---")

