import pymongo
from models import *
from tqdm import tqdm

### DB INIT ###
def init(db):
    def init_rooms_collection():
        try:
            db.create_collection("rooms")
            print("Created collection rooms")
        except Exception as e:
            if str(e) != "collection rooms already exists":
                print(e)

        try:
            db.command("collMod", "rooms", validator=room_validator)
            db.rooms.create_index([("name", pymongo.ASCENDING)], name="room_name", unique=True)
        except Exception as e:
            print(e)
    
    def init_teachers_collection():
        try:
            db.create_collection("teachers")
            print("Created collection teachers")
        except Exception as e:
            if str(e) != "collection teachers already exists":
                print(e)

        try:
            db.command("collMod", "teachers", validator=teacher_validator)
            db.teachers.create_index([("name", pymongo.ASCENDING)], name="teacher_unique", unique=True)
        except Exception as e:
            print(e)

    def init_courses_collection():
        try:
            db.create_collection("courses")
            print("Created collection courses")
        except Exception as e:
            if str(e) != "collection courses already exists":
                print(e)
            return

        try:
            db.command("collMod", "courses", validator=course_validator)
            db.courses.create_index([("code", pymongo.ASCENDING)], name="course_unique", unique=True)
        except Exception as e:
            print(e)

    def init_course_bookings_collection():
        try:
            db.create_collection("course_bookings")
            print("Created collection course_bookings")
        except Exception as e:
            if str(e) != "collection course_bookings already exists":
                print(e)
            return

        try:
            db.command("collMod", "course_bookings", validator=course_booking_validator)
            db.course_bookings.create_index([("schedule_id", pymongo.ASCENDING), ("room_id", pymongo.ASCENDING)], name="booking_unique", unique=True)
        except Exception as e:
            print(e)

    def init_course_schedules_collection():
        try:
            db.create_collection("course_schedules")
            print("Created collection course_schedules")
        except Exception as e:
            if str(e) != "collection course_schedules already exists":
                print(e)
            return
        
        try:
            db.command("collMod", "course_schedules", validator=course_schedule_validator)
            db.course_schedules.create_index([("course_id", pymongo.ASCENDING), ("start_datetime", pymongo.ASCENDING), ("end_datetime", pymongo.ASCENDING)], name="schedule_unique", unique=True)
        except Exception as e:
            print(e)

    def init_studyplans_collection():
        try:
            db.create_collection("studyplans")
            print("Created collection studyplans")
        except Exception as e:
            if str(e) != "collection studyplans already exists":
                print(e)
            return

        try:
            db.command("collMod", "studyplans", validator=studyplan_validator)
            db.studyplans.create_index([("unit_id", pymongo.ASCENDING), ("semester_id", pymongo.ASCENDING)], name="studyplan_unique", unique=True)
        except Exception as e:
            print(e)

    def init_units_collection():
        try:
            db.create_collection("units")
            print("Created collection units")
        except Exception as e:
            if str(e) != "collection units already exists":
                print(e)
            return

        try:
            db.command("collMod", "units", validator=unit_validator)
            db.units.create_index([("name", pymongo.ASCENDING)], name="unit_unique", unique=True)
        except Exception as e:
            print(e)

    def init_semesters_collection():
        try:
            db.create_collection("semesters")
            print("Created collection semesters")
        except Exception as e:
            if str(e) != "collection semesters already exists":
                print(e)
            return

        try:
            db.command("collMod", "semesters", validator=semester_validator)
            db.semesters.create_index([("name", pymongo.ASCENDING)], name="semester_unique", unique=True)
        except Exception as e:
            print(e)

    def init_planned_in_collection():
        try:
            db.create_collection("planned_in")
            print("Created collection planned_in")
        except Exception as e:
            if str(e) != "collection planned_in already exists":
                print(e)
            return

        try:
            db.command("collMod", "planned_in", validator=planned_in_validator)
            db.planned_in.create_index([("studyplan_id", pymongo.ASCENDING), ("course_id", pymongo.ASCENDING)], name="planned_in_unique", unique=True)
        except Exception as e:
            print(e)

    def init_event_bookings_collection():
        try:
            db.create_collection("event_bookings")
            print("Created collection event_bookings")
        except Exception as e:
            if str(e) != "collection event_bookings already exists":
                print(e)
            return
        
        try:
            db.command("collMod", "event_bookings", validator=event_booking_validator)
            db.event_bookings.create_index([("schedule_id", pymongo.ASCENDING), ("room_id", pymongo.ASCENDING)], name="booking_unique", unique=True)
        except Exception as e:
            print(e)

    def init_event_schedules_collection():
        try:
            db.create_collection("event_schedules")
            print("Created collection event_schedules")
        except Exception as e:
            if str(e) != "collection event_schedules already exists":
                print(e)
            return
        
        try:
            db.command("collMod", "event_schedules", validator=event_schedule_validator)
        except Exception as e:
            print(e)
    
    pbar = tqdm(total=10, desc="Initializing DB", leave=False)
    

    inits = [
        init_rooms_collection(),

        # Course collections
        init_teachers_collection(),
        init_courses_collection(),
        init_course_bookings_collection(),
        init_course_schedules_collection(),
        init_studyplans_collection(),
        init_units_collection(),
        init_semesters_collection(),
        init_planned_in_collection(),

        # Event collections
        init_event_bookings_collection(),
        init_event_schedules_collection()
    ]

    for init in inits:
        init
        pbar.update(1)
    pbar.close()
    print("-- DB initialized -- ")



