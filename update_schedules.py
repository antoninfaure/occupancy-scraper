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

# Get schedules from edu.epfl.ch for the current or next semester
print("----- Get schedules -----")
schedules = utils.find_courses_schedules(db)

# Create rooms in DB
print("----- Create rooms -----")
utils.create_rooms(db, schedules)

# Update schedules in DB
print("----- Update schedules -----")
utils.update_schedules(db, schedules)

# Create bookings
print("----- Create bookings -----")
utils.create_courses_bookings(db, schedules=schedules)

print("===== Done =====")