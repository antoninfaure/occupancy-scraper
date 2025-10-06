import concurrent.futures
import multiprocessing
import os
import re
from datetime import datetime, timedelta

import numpy as np
import requests
from bs4 import BeautifulSoup
from bson import ObjectId
from pymongo.database import Database
from pyproj import Transformer as pyproj_Transformer
from tqdm import tqdm

from config import (
    MAP_PROMOS_LONG,
    MAP_ROOMS,
    MAP_SECTIONS,
    MAP_SEMESTERS_LONG,
    ROOMS_FILTER,
)
from entity_types import (
    CourseBookingDocument,
    CourseDocument,
    CourseSchedule,
    CourseScraped,
    PlannedInDocument,
    PlanRoom,
    RoomDocument,
    SemesterDocument,
    SemesterType,
    StudyPlanDocument,
    StudyPlanScraped,
    TeacherDocument,
    TeacherScraped,
    UnitDocument,
)


### GET ALL COURSES URLS ###
def get_all_courses_url():
    URL_ROOT = "https://edu.epfl.ch/"
    shs = [
        "https://edu.epfl.ch/studyplan/fr/bachelor/programme-sciences-humaines-et-sociales/",
        "https://edu.epfl.ch/studyplan/fr/master/programme-sciences-humaines-et-sociales/",
    ]
    page = requests.get(URL_ROOT, timeout=500)
    soup = BeautifulSoup(page.content, "html.parser")
    cards = soup.find_all("div", class_="card-title")
    promos = [card.find("a").get("href") for card in cards]
    courses_url = []
    courses_names = []
    for promo in tqdm(promos):
        page = requests.get(URL_ROOT + promo)
        soup = BeautifulSoup(page.content, "html.parser")
        sections = [x.get("href") for x in soup.find("main").find("ul").findAll("a")]
        for section in sections:
            page = requests.get(URL_ROOT + section)
            soup = BeautifulSoup(page.content, "html.parser")
            for course in soup.find("main").findAll("div", class_="cours-name"):
                if course.find("a") is not None:
                    course_url = course.find("a").get("href")
                    course_name = course_url.split("/").pop()
                    if (
                        "programme-sciences-humaines-et-sociales" not in course_url
                        and course_name not in courses_names
                    ):
                        courses_url.append(course_url)
                        courses_names.append(course_name)

    # Add SHS courses
    for url in shs:
        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        for course in soup.find_all("div", class_="cours-name"):
            if course.find("a") is not None:
                course_url = course.find("a").get("href")
                course_name = course_url.split("/").pop()
                if course_name not in courses_names:
                    courses_url.append(course_url)
                    courses_names.append(course_name)

    # Filter duplicates
    courses_url = list(set(courses_url))

    return courses_url


def parse_credits(soup):
    credits = soup.find("div", class_="course-summary")
    if credits is None:
        return None

    credits = credits.findAll("p")
    if len(credits) == 0:
        return None

    credits = credits[0].text.split("/")
    if len(credits) == 0:
        return None

    credits = re.findall(r"\d+", credits[1])
    if len(credits) == 0:
        return None

    return int(credits[0])


### PARSE COURSE ###
def parse_course(url: str) -> CourseScraped | None:
    page = requests.get(url, timeout=(500, 500))
    if page.status_code == 404:
        print(f"404: {url}")
        return None

    soup = BeautifulSoup(page.content, "html.parser")

    title = soup.find("main").find("h1").text
    if soup.find("div", class_="course-summary") is None:
        print(url)
    code = (
        soup.find("div", class_="course-summary")
        .findAll("p")[0]
        .text.split("/")[0]
        .strip()
    )
    credits = parse_credits(soup)
    teachers = [
        TeacherScraped(name=x.text, people_url=x.get("href"))
        for x in soup.find("div", class_="course-summary").findAll("p")[1].findAll("a")
    ]
    language = soup.find("div", class_="course-summary").findAll("p")
    if len(language) > 2:
        language = language[2].text.split(":")
        if "Langue" in language[0] and len(language) > 1:
            language = language[1].strip()
        else:
            language = None
    else:
        language = None

    studyplans_elements = soup.find("div", class_="study-plans").findAll(
        "button", class_="collapse-title-desktop"
    )

    # studyplans_elements are buttons with section name before the xxxx-xxxx years and the semester after
    re_pattern = r"(\d{4}-\d{4})"

    studyplans: list[StudyPlanScraped] = []
    for studyplan_element in studyplans_elements:
        parts = re.split(re_pattern, studyplan_element.text)
        section = parts[0].strip().replace("\n", " ")
        semester = parts[1] + " " + parts[2].strip()
        studyplans.append(StudyPlanScraped(section=section, semester=semester))

    return CourseScraped(
        name=title,
        code=code,
        credits=credits,
        studyplans=studyplans,
        teachers=teachers,
        edu_url=url,
        language=language,
    )


### PARSE ALL COURSES ###
def parse_all_courses() -> list[CourseScraped]:
    URL_ROOT = "https://edu.epfl.ch"
    print("Getting all courses urls...")
    courses_url = get_all_courses_url()
    print(f"- {len(courses_url)} courses urls found")

    courses: list[CourseScraped] = []
    print("Parsing courses...")

    # Use ThreadPoolExecutor to parse courses concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        # Submit all the tasks to the executor
        future_to_url = {
            executor.submit(parse_course, URL_ROOT + url): url for url in courses_url
        }

        # Process the completed futures
        for future in tqdm(
            concurrent.futures.as_completed(future_to_url), total=len(courses_url)
        ):
            url = future_to_url[future]
            try:
                course = future.result()
                if course is not None:
                    courses.append(course)
            except Exception as exc:
                print(f"Course {url} generated an exception: {exc}")

    print(f"- {len(courses)} courses parsed")
    return courses


### FILTER DUPLICATES COURSES ###
def filter_duplicates_courses(courses: list[CourseScraped]) -> list[CourseScraped]:
    """
    Filter duplicates courses
    Input:
        - courses: a list of courses
    Output:
        - filtered_courses: a list of courses without duplicates
    """
    filtered_courses = []
    course_codes = set()
    for course in courses:
        course_code = course.code

        if course_code not in course_codes:
            course_codes.add(course_code)
            filtered_courses.append(course)
    return filtered_courses


### CREATE COURSES ###
def create_courses(db, courses: list[CourseScraped]) -> None:
    """
    Create courses in the db
    Input:
        - courses: a list of courses to create
    Output:
        - None
    """
    print("Getting courses from DB...")
    db_courses_codes = [
        CourseDocument.model_validate(course_doc).code
        for course_doc in db.courses.find()
    ]
    print(f"- {len(db_courses_codes)} courses found in DB")

    print("Filtering courses...")
    new_courses = []
    for course in tqdm(courses, total=len(courses)):
        if course.code in db_courses_codes:
            continue
        new_course = CourseDocument(
            code=course.code,
            name=course.name,
            credits=course.credits,
            edu_url=course.edu_url,
            available=True,
            language=course.language,
        )

        new_courses.append(new_course.model_dump(exclude_none=True))

    print("Creating courses...")
    if len(new_courses) == 0:
        print("- No new courses to create")
        return

    try:
        db.courses.insert_many(new_courses)
        print(f"- {len(new_courses)} courses created")
    except Exception as e:
        print(e)

    return


### CREATE TEACHERS ###
def create_teachers(db: Database, courses: list[CourseScraped]) -> None:
    """
    Create teachers in the db
    Input:
        - courses: a list of courses to create
    Output:
        - None
    """

    print("Getting teachers from DB...")
    db_teachers = [
        TeacherDocument.model_validate(teacher_doc)
        for teacher_doc in db.teachers.find({"available": True})
    ]
    print(f"- {len(db_teachers)} teachers found")

    existing_names = {teacher.name for teacher in db_teachers}

    print("Filtering teachers...")
    new_teachers: list[TeacherDocument] = []
    queued_names: set[str] = set()
    for course in tqdm(courses, total=len(courses)):
        for teacher in course.teachers:
            teacher_name = teacher.name

            if teacher_name in existing_names or teacher_name in queued_names:
                continue

            queued_names.add(teacher_name)
            new_teachers.append(
                TeacherDocument(
                    name=teacher_name,
                    people_url=teacher.people_url,
                    available=True,
                )
            )

    print("Creating new teachers...")
    if len(new_teachers) == 0:
        print("- No new teachers")
        return

    try:
        db.teachers.insert_many(
            [teacher.model_dump(exclude_none=True) for teacher in new_teachers]
        )
        print(f"- {len(new_teachers)} teachers created")
    except Exception as e:
        print(e)

    return


### ADD TEACHERS TO COURSES ###
def add_teachers_to_courses(db: Database, courses: list[CourseScraped]) -> None:
    """
    Add teachers to courses in the db
    Input:
        - courses: a list of courses to update
    Output:
        - None
    """
    db_courses = [
        CourseDocument.model_validate(course_doc)
        for course_doc in db.courses.find({"available": True})
    ]
    print("Getting teachers from DB...")
    db_teachers = [
        TeacherDocument.model_validate(teacher_doc)
        for teacher_doc in db.teachers.find({"available": True})
    ]
    print(f"- {len(db_teachers)} teachers found")

    print("Adding teachers to courses...")
    for course in tqdm(courses, total=len(courses)):
        db_course = next(
            (item for item in db_courses if item.code == course.code), None
        )

        if db_course is None or db_course._id is None:
            continue

        course_teachers_ids: list[ObjectId] = []

        for teacher in course.teachers:
            matching_teacher = next(
                (
                    db_teacher
                    for db_teacher in db_teachers
                    if db_teacher.people_url == teacher.people_url
                ),
                None,
            )

            if matching_teacher and matching_teacher._id is not None:
                course_teachers_ids.append(matching_teacher._id)

        db.courses.update_one(
            {"_id": db_course._id},
            {"$set": {"teachers": course_teachers_ids}},
        )

    return


### CREATE NEW SEMESTER ###
def create_new_semester(db: Database, **kwargs):
    name = kwargs.get("name")
    if not name:
        raise ValueError("create_new_semester requires a non-empty 'name'")

    semester_payload = {
        "start_date": kwargs.get("start_date"),
        "end_date": kwargs.get("end_date"),
        "type": kwargs.get("type"),
        "available": kwargs.get("available", False),
        "skip_dates": kwargs.get("skip_dates", []),
    }

    # Use upsert to avoid duplicate key errors when the semester already exists.
    result = db.semesters.update_one(
        {"name": name},
        {"$set": semester_payload, "$setOnInsert": {"name": name}},
        upsert=True,
    )

    if result.matched_count and not result.modified_count:
        print(f"Semester '{name}' already up-to-date")


def list_units(courses: list[CourseScraped]) -> list[tuple[str, str]]:
    units: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for course in courses:
        for studyplan in course.studyplans:
            unit_key = (studyplan.section, studyplan.semester)
            if unit_key in seen:
                continue
            seen.add(unit_key)
            units.append(unit_key)

    return units


def create_units(db: Database, courses: list[CourseScraped]) -> None:
    units = list_units(courses)

    print("Getting units from DB...")
    db_units = [UnitDocument.model_validate(unit_doc) for unit_doc in db.units.find()]
    print(f"- {len(db_units)} units found")
    db_units_names = [unit.name for unit in db_units]

    semester_re_pattern = r"(\d{4}-\d{4})"

    new_units = []
    new_units_names = set()
    print("Filtering units...")
    for unit in tqdm(units):
        semester_long = re.split(semester_re_pattern, unit[1])[2].strip()
        unit_name = (
            unit[0] + " - " + semester_long
            if semester_long in MAP_PROMOS_LONG
            else unit[0]
        )
        if unit_name not in db_units_names and unit_name not in new_units_names:
            promo = (
                MAP_PROMOS_LONG[semester_long]
                if semester_long in MAP_PROMOS_LONG
                else None
            )
            if unit[0] not in MAP_SECTIONS:
                print("Section not found in MAP_SECTIONS", unit[0])
                continue
            code = (
                f"{MAP_SECTIONS[unit[0]]}-{promo}"
                if promo is not None
                else MAP_SECTIONS[unit[0]]
            )
            new_unit_doc = UnitDocument(
                name=unit_name,
                code=code,
                section=MAP_SECTIONS[unit[0]],
                promo=promo,
                available=True,
            )

            new_units_names.add(unit_name)
            new_units.append(new_unit_doc.model_dump(exclude_none=True))

    print("Creating new units...")
    if len(new_units) == 0:
        print("- No units to create")
        return

    try:
        db.units.insert_many(new_units)
        print(f"- {len(new_units)} units created")
    except Exception as e:
        print(e)

    return


def create_studyplans(db: Database, courses: list[CourseScraped]) -> None:
    print("Getting studyplans from DB...")
    db_studyplans = [
        StudyPlanDocument.model_validate(plan_doc)
        for plan_doc in db.studyplans.find({"available": True})
    ]
    print(f"- {len(db_studyplans)} studyplans found")

    # Find current or next semester for each semester type (fall, spring, year)
    db_semester_fall = get_current_or_next_semester(db, "fall")
    db_semester_spring = get_current_or_next_semester(db, "spring")
    db_semester_year = get_current_or_next_semester(db, "year")

    db_semesters = [
        semester
        for semester in [db_semester_fall, db_semester_spring, db_semester_year]
        if semester is not None
    ]
    print(len(list(db_semesters)), "db semesters found")

    db_units = [
        UnitDocument.model_validate(unit_doc)
        for unit_doc in db.units.find({"available": True})
    ]

    print(db_semesters)

    new_studyplans = []
    semester_re_pattern = r"(\d{4}-\d{4})"
    print("Filtering studyplans...")
    for course in courses:
        for studyplan in course.studyplans:
            semester_long = re.split(semester_re_pattern, studyplan.semester)[2].strip()
            unit_name = (
                studyplan.section + " - " + semester_long
                if semester_long in MAP_PROMOS_LONG
                else studyplan.section
            )

            # Find unit in db
            studyplan_unit = next(
                (unit for unit in db_units if unit.name == unit_name), None
            )
            if studyplan_unit is None:
                print("Unit not found", unit_name)
                continue

            # Map semester name to semester type
            semester_type = None
            if semester_long not in MAP_SEMESTERS_LONG:
                semester_type = MAP_SEMESTERS_LONG[studyplan.section]
            else:
                semester_type = MAP_SEMESTERS_LONG[semester_long]

            # Find semester in db
            studyplan_semester = next(
                (
                    semester
                    for semester in db_semesters
                    if semester_type == semester.type
                ),
                None,
            )
            if studyplan_semester is None:
                continue

            # Check if studyplan already exists in db
            found = False
            for db_plan in db_studyplans:
                if (
                    db_plan.unit_id == studyplan_unit._id
                    and db_plan.semester_id == studyplan_semester._id
                ):
                    found = True
                    break

            # If studyplan already exists, continue
            if found:
                continue

            # Check if studyplan already exists in new_studyplans
            found = False
            for new_plan in new_studyplans:
                if (
                    new_plan["unit_id"] == studyplan_unit._id
                    and new_plan["semester_id"] == studyplan_semester._id
                ):
                    found = True
                    break

            # If studyplan already exists, continue
            if found:
                continue

            if studyplan_unit._id is None or studyplan_semester._id is None:
                continue

            new_plan_doc = StudyPlanDocument(
                unit_id=studyplan_unit._id,
                semester_id=studyplan_semester._id,
                available=True,
            )

            new_studyplans.append(new_plan_doc.model_dump())

    print("Creating studyplans...")
    if len(new_studyplans) == 0:
        print("- No new studyplans to create")
        return

    # Find duplicates in new_studyplans

    try:
        db.studyplans.insert_many(new_studyplans)
        print(f"- {len(new_studyplans)} studyplans created")
    except Exception as e:
        print(e)

    return


def create_planned_in(db: Database, courses: list[CourseScraped]) -> None:
    db_courses = [
        CourseDocument.model_validate(course_doc)
        for course_doc in db.courses.find({"available": True})
    ]

    db_units = [
        UnitDocument.model_validate(unit_doc)
        for unit_doc in db.units.find({"available": True})
    ]

    db_semester_fall = get_current_or_next_semester(db, "fall")
    db_semester_spring = get_current_or_next_semester(db, "spring")
    db_semester_year = get_current_or_next_semester(db, "year")

    db_semesters = [
        semester
        for semester in [db_semester_fall, db_semester_spring, db_semester_year]
        if semester is not None
    ]

    print("Getting studyplans from DB...")
    db_studyplans = [
        StudyPlanDocument.model_validate(plan_doc)
        for plan_doc in db.studyplans.find(
            {
                "available": True,
                "semester_id": {
                    "$in": [
                        semester._id
                        for semester in db_semesters
                        if semester is not None and semester._id is not None
                    ]
                },
            }
        )
    ]
    print(f"- {len(db_studyplans)} studyplans found")

    print("Getting planned_in from DB...")
    db_planned_in = [
        PlannedInDocument.model_validate(planned_doc)
        for planned_doc in db.planned_in.find(
            {
                "available": True,
                "studyplan_id": {
                    "$in": [plan._id for plan in db_studyplans if plan._id is not None]
                },
            }
        )
    ]
    print(f"- {len(db_planned_in)} planned_in found")

    semester_re_pattern = r"(\d{4}-\d{4})"
    new_planned_ins: list[dict] = []
    print("Filtering planned_in...")
    for course in tqdm(courses, total=len(courses)):
        db_course = next(
            (item for item in db_courses if item.code == course.code), None
        )
        if db_course is None or db_course._id is None:
            continue

        course_studyplans_ids: set[ObjectId] = set()

        for studyplan in course.studyplans:
            semester_long = re.split(semester_re_pattern, studyplan.semester)[2].strip()
            unit_name = (
                studyplan.section + " - " + semester_long
                if semester_long in MAP_PROMOS_LONG
                else studyplan.section
            )

            studyplan_unit = next(
                (unit for unit in db_units if unit.name == unit_name),
                None,
            )
            if studyplan_unit is None or studyplan_unit._id is None:
                print("Unit not found", unit_name)
                continue

            if semester_long not in MAP_SEMESTERS_LONG:
                semester_type = MAP_SEMESTERS_LONG[studyplan.section]
            else:
                semester_type = MAP_SEMESTERS_LONG[semester_long]

            studyplan_semester_db = next(
                (
                    semester
                    for semester in db_semesters
                    if semester.type == semester_type
                ),
                None,
            )
            if studyplan_semester_db is None or studyplan_semester_db._id is None:
                continue

            studyplan_db = next(
                (
                    plan
                    for plan in db_studyplans
                    if plan.unit_id == studyplan_unit._id
                    and plan.semester_id == studyplan_semester_db._id
                ),
                None,
            )
            if studyplan_db is None or studyplan_db._id is None:
                continue

            course_studyplans_ids.add(studyplan_db._id)

        for studyplan_id in course_studyplans_ids:
            already_exists = any(
                planned.course_id == db_course._id
                and planned.studyplan_id == studyplan_id
                for planned in db_planned_in
            )
            if already_exists:
                continue

            already_queued = any(
                new_planned["course_id"] == db_course._id
                and new_planned["studyplan_id"] == studyplan_id
                for new_planned in new_planned_ins
            )
            if already_queued:
                continue

            new_planned_doc = PlannedInDocument(
                course_id=db_course._id,
                studyplan_id=studyplan_id,
                available=True,
            )

            new_planned_ins.append(new_planned_doc.model_dump())

    print("Creating planned_in...")
    if len(new_planned_ins) == 0:
        print("- No new planned_in to create")
        return

    try:
        db.planned_in.insert_many(new_planned_ins)
        print(f"- {len(new_planned_ins)} planned_in created")
    except Exception as e:
        print(e)
    return


def get_current_or_next_semester(
    db, semester_type: SemesterType | None = None
) -> SemesterDocument | None:
    today = datetime.today()

    # If semester_type is specified, get the current or next semester of this type
    if semester_type is not None:
        semester_doc = db.semesters.find_one(
            {"end_date": {"$gte": today}, "type": semester_type}, sort=[("end_date", 1)]
        )

        return (
            SemesterDocument.model_validate(semester_doc)
            if semester_doc is not None
            else None
        )

    # Get the current semester
    semester_doc = db.semesters.find_one(
        {
            "start_date": {"$lte": today},
            "end_date": {"$gte": today},
            "type": {"$ne": "year"},
        }
    )

    # If no current semester is found, get the first next semester
    if not semester_doc:
        semester_doc = db.semesters.find_one(
            {"start_date": {"$gte": today}, "type": {"$ne": "year"}},
            sort=[("start_date", 1)],
        )

    return (
        SemesterDocument.model_validate(semester_doc)
        if semester_doc is not None
        else None
    )


def find_semester_courses_ids(db, semester: SemesterDocument | None) -> list[ObjectId]:
    if semester is None or semester._id is None:
        return []

    print("Getting studyplans from DB...")
    filtered_studyplans = [
        StudyPlanDocument.model_validate(plan_doc)
        for plan_doc in db.studyplans.find(
            {"available": True, "semester_id": semester._id}
        )
    ]
    filtered_studyplans_ids = [
        studyplan._id for studyplan in filtered_studyplans if studyplan._id is not None
    ]
    print(f"- {len(filtered_studyplans_ids)} studyplans found")

    planned_in = [
        PlannedInDocument.model_validate(planned_doc)
        for planned_doc in db.planned_in.find(
            {"available": True, "studyplan_id": {"$in": filtered_studyplans_ids}}
        )
    ]
    semester_courses_ids = [planned.course_id for planned in planned_in]

    return semester_courses_ids


### PARSE COURSE SCHEDULE ###
def get_course_schedule(
    url: str,
) -> (
    tuple[list[CourseScheduleSlot] | list[CourseScheduleEventBase] | None, bool] | None
):
    page = requests.get(url)
    if page.status_code == 404:
        print(url)
        return None

    soup = BeautifulSoup(page.content, "html.parser")

    schedule = soup.find("div", class_="coursebook-week-caption sr-only")

    edoc = False
    if schedule is None:
        schedule_parsed = parse_schedule_EDOC(soup)
        edoc = True
    else:
        schedule_parsed = parse_schedule(soup)

    if schedule_parsed is None:
        return None, edoc

    return schedule_parsed, edoc


### PARSE SCHEDULE DOCTORAL SCHOOL ###
def parse_schedule_EDOC(soup) -> list[CourseScheduleScraped] | None:
    # Ecole doctorale
    iframe_soup = BeautifulSoup(
        requests.get(soup.find("iframe").attrs["src"]).content, "html.parser"
    )
    if iframe_soup.find("table") is None:
        return None

    rows = iframe_soup.findAll("tr")
    creneaux: list[CourseScheduleScraped] = []
    current_date: datetime | None = None

    for i, row in enumerate(rows):
        if i == 0:
            continue
        if row.find("th") is not None:
            date_str = re.findall(r"\d{2}.\d{2}.\d{4}", row.find("th").text)
            if len(date_str) > 0:
                current_date = datetime.strptime(date_str[0], "%d.%m.%Y")
            continue

        if (
            row.get("class") is not None
            and "grisleger" in row.get("class")
            and current_date is not None
        ):
            time = [x.split(":")[0] for x in row.findAll("td")[0].text.split("-")]

            start_hour = int(time[0])
            duration = int(time[1]) - int(time[0])

            rooms_found = [room.text for room in row.findAll("td")[1].findAll("a")]

            rooms: list[str] = []
            for room in rooms_found:
                if room in MAP_ROOMS:
                    if isinstance(MAP_ROOMS[room], list):
                        rooms += [x for x in MAP_ROOMS[room]]
                    else:
                        rooms.append(MAP_ROOMS[room])
                elif room not in ROOMS_FILTER:
                    rooms.append(room)
            label = row.findAll("td")[2].text
            if label == "L":
                label = "cours"
            elif label == "E":
                label = "exercice"
            elif label == "P":
                label = "projet"

            start_datetime = current_date.replace(
                hour=start_hour, minute=0, second=0, microsecond=0
            )
            event = CourseScheduleScraped(
                start_datetime=start_datetime,
                end_datetime=start_datetime + timedelta(hours=duration),
                label=label,
                rooms=rooms,
            )
            if rooms:
                creneaux.append(event)

    if len(creneaux) == 0:
        return None

    schedule: list[CourseScheduleScraped] = []
    for creneau in creneaux:
        existing = next(
            (
                s
                for s in schedule
                if s.start_datetime == creneau.start_datetime
                and s.end_datetime == creneau.end_datetime
                and s.label == creneau.label
            ),
            None,
        )
        if existing is not None:
            existing.rooms = existing.rooms + creneau.rooms
        else:
            schedule.append(creneau)

    return schedule


def parse_schedule(soup: BeautifulSoup) -> list[CourseScheduleScraped]:
    coursebook = soup.find("div", class_="coursebook-week-caption sr-only")
    if coursebook is None:
        return []
    creneaux = coursebook.findAll("p")

    schedule: list[CourseScheduleScraped] = []
    for creneau in creneaux:
        # Extracting the full text from the paragraph
        full_text = creneau.get_text().replace("\xa0", " ")

        day = full_text.split(",")[0]

        # Mapping days to weekday numbers
        days_map = {
            "Lundi": 0,
            "Mardi": 1,
            "Mercredi": 2,
            "Jeudi": 3,
            "Vendredi": 4,
            "Samedi": 5,
            "Dimanche": 6,
        }
        day = days_map[day]

        # Extracting start hour and duration
        time_match = re.search(r"(\d{1,2}h) - (\d{1,2}h)", full_text)
        start_hour, end_hour = time_match.groups() if time_match else (None, None)
        if not start_hour or not end_hour:
            continue

        duration = int(end_hour[:-1]) - int(start_hour[:-1])
        start_hour_int = int(start_hour[:-1])

        # Extracting label
        first_room = creneau.find("a")
        if first_room:
            label = creneau.find("a").previousSibling.text.split(": ")[1].strip()
        else:
            label = creneau.text.split(": ")[1].strip()

        if label == "Cours":
            label = "cours"
        elif label == "Exercice, TP":
            label = "exercice"
        elif label == "Projet, autre":
            label = "projet"

        # Extracting rooms
        rooms_found = [link.get_text() for link in creneau.findAll("a", href=True)]
        rooms = []
        for room in rooms_found:
            if room in MAP_ROOMS:
                mapped_room = MAP_ROOMS[room]
                if isinstance(mapped_room, list):
                    rooms.extend(mapped_room)
                else:
                    rooms.append(mapped_room)
            elif room not in ROOMS_FILTER:
                rooms.append(room)

        schedule.append(
            CourseScheduleSlot(
                day=day,
                start_hour=start_hour_int,
                duration=duration,
                label=label,
                rooms=rooms,
            )
        )

    return schedule


def create_semester_schedule(
    schedule: list[CourseScheduleSlot], db_semester: SemesterDocument
) -> list[CourseScheduleEventBase]:
    start_date = db_semester.start_date
    end_date = db_semester.end_date
    skip_dates = db_semester.skip_dates or []

    semester_schedule: list[CourseScheduleEventBase] = []

    current_date = start_date
    while current_date <= end_date:
        if current_date not in skip_dates:
            for event in schedule:
                if event.day != current_date.weekday():
                    continue

                start_datetime = datetime.combine(
                    current_date, datetime.min.time()
                ) + timedelta(hours=event.start_hour)
                end_datetime = start_datetime + timedelta(hours=event.duration)

                event_entry = CourseScheduleEventBase(
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    label=event.label,
                    rooms=event.rooms,
                )

                semester_schedule.append(event_entry)

        current_date += timedelta(days=1)

    return semester_schedule


def process_course_schedules(
    course: CourseDocument,
    db_courses_semester_codes: set[str],
    semester: SemesterDocument | None,
) -> list[CourseSchedule] | None:
    course_edu_url = course.edu_url
    if course_edu_url is None:
        return None

    result = get_course_schedule(course_edu_url)
    if result is None:
        print(f"No schedule found for {course_edu_url}")
        return None
    schedule, edoc = result

    if schedule is None:
        return None

    if edoc is False:
        if course.code not in db_courses_semester_codes or semester is None:
            return None
        schedule = create_semester_schedule(schedule, semester)

    if course._id is None:
        return None

    events_with_course = [
        CourseSchedule(
            course_id=course._id,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
            label=event.label,
            rooms=event.rooms,
        )
        for event in schedule
    ]

    return events_with_course


def process_course_schedules_start(args):
    return process_course_schedules(*args)


def find_courses_schedules(db: Database) -> list[CourseSchedule]:
    semester = get_current_or_next_semester(db)
    semester_courses_ids = find_semester_courses_ids(db, semester)

    current_year = get_current_or_next_semester(db, "year")

    current_year_courses_ids = find_semester_courses_ids(db, current_year)

    print("Getting courses from DB...")
    db_courses_semester = [
        CourseDocument.model_validate(course_doc)
        for course_doc in db.courses.find({"_id": {"$in": semester_courses_ids}})
    ]
    db_courses_semester_codes = {course.code for course in db_courses_semester}

    db_courses_year = [
        CourseDocument.model_validate(course_doc)
        for course_doc in db.courses.find(
            {
                "_id": {
                    "$in": list(
                        set(current_year_courses_ids) - set(semester_courses_ids)
                    )
                }
            }
        )
    ]
    db_courses = db_courses_semester + db_courses_year

    print(f"- {len(db_courses)} courses found")

    schedules: list[CourseSchedule] = []
    num_processes = multiprocessing.cpu_count()
    with multiprocessing.Pool(num_processes) as pool:
        processed_schedules = tqdm(
            pool.imap(
                process_course_schedules_start,
                [
                    (course, db_courses_semester_codes, semester)
                    for course in db_courses
                ],
            ),
            total=len(db_courses),
            desc="Processing courses schedules",
        )

        for schedule in processed_schedules:
            if schedule is not None:
                schedules += schedule

    return schedules


### LIST ALL ROOMS ###
def list_rooms(
    schedules: list[CourseScheduleEvent | CourseScheduleEventBase],
) -> list[str]:
    rooms: list[str] = []
    for schedule in schedules:
        schedule_rooms = schedule.rooms
        if schedule_rooms is None:
            continue

        for room in schedule_rooms:
            if room not in rooms:
                rooms.append(room)

    return rooms


### LIST ALL PLAN ROOMS ###
def list_plan_rooms():
    """
    List all the rooms objects (name, type) on the plan.epfl.ch website
    Output:
        - rooms: a list of rooms
    """

    def list_level_rooms(low, up, floor, max=1000):
        """
        List all the XML rooms objects in a level
        Input:
            - low: the lower left corner of the level
            - up: the upper right corner of the level
            - floor: the floor of the level
            - max: the maximum number of rooms to return
            Output:
                - rooms: a list of XML rooms
        """
        low1, low2 = low
        up1, up2 = up
        request_url = f"https://plan.epfl.ch/mapserv_proxy?ogcserver=source+for+image%2Fpng&cache_version=9fe661ce469e4692b9e402b22d8cb420&floor={floor}"
        xml = f'<GetFeature xmlns="http://www.opengis.net/wfs" service="WFS" version="1.1.0" outputFormat="GML3" maxFeatures="{max}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.1.0/wfs.xsd"><Query typeName="feature:batiments_wmsquery" srsName="EPSG:2056" xmlns:feature="http://mapserver.gis.umn.edu/mapserver"><Filter xmlns="http://www.opengis.net/ogc"><BBOX><PropertyName>the_geom</PropertyName><Envelope xmlns="http://www.opengis.net/gml" srsName="EPSG:2056"><lowerCorner>{low1} {low2}</lowerCorner><upperCorner>{up1} {up2}</upperCorner></Envelope></BBOX></Filter></Query></GetFeature>'

        r = requests.post(request_url, data=xml)
        level_xml = BeautifulSoup(r.text, "xml")
        if level_xml.find("gml:Null") is not None:
            return None
        return level_xml.findAll("gml:featureMember")

    def list_all_levels_rooms():
        """
        List all the XML rooms objects in ALL levels
        Output:
            - rooms: a list of XML rooms
        """
        rooms_xml = {}
        for level in tqdm(range(-3, 8)):
            level_rooms_xml = list_level_rooms(
                (2533565.4081416847, 1152107.9784703811),
                (2532680.590, 1152904.181),
                level,
                max=5000,
            )
            if level_rooms_xml and len(level_rooms_xml) > 0:
                rooms_xml[level] = level_rooms_xml
        return rooms_xml

    def compute_coordinates(coordinates_string):
        coordinates_split = coordinates_string.split()
        coordinates = [
            (float(coordinates_split[i]), float(coordinates_split[i + 1]))
            for i in range(0, len(coordinates_split), 2)
        ]

        # Compute center coordinates
        xs, ys = zip(*coordinates)
        center_x, center_y = (np.mean(xs), np.mean(ys))

        # Transform coordinates from MN95 (epsg:2056) to WGS84 (epsg:4326)
        transformer = pyproj_Transformer.from_crs("epsg:2056", "epsg:4326")

        return transformer.transform(center_x, center_y)

    def parse_room(room_xml, level):
        """
        Parse a XML room object
        Input:
            - room_xml: the XML room object
        Output:
            - room: the parsed room object (name, type, coordinates, link)
        """
        room_name = (
            BeautifulSoup(room_xml.find("ms:room_abr_link").text, "html.parser")
            .find("div", class_="room")
            .text.replace(" ", "")
        )
        room_type = room_xml.find("ms:room_uti_a").text
        room_link = (
            BeautifulSoup(room_xml.find("ms:room_abr_link").text, "html.parser")
            .find("button", class_="clipboard")
            .attrs["data-clipboard-text"]
        )
        room_capacity = room_xml.find("ms:room_place").text
        if room_capacity and room_capacity != "":
            room_capacity = int(room_capacity)
        else:
            room_capacity = None
        room_coordinates_string = room_xml.find("gml:posList").text
        room_coordinates = compute_coordinates(room_coordinates_string)

        return PlanRoom(
            name=room_name,
            type=room_type,
            coordinates=room_coordinates,
            link=room_link,
            capacity=room_capacity,
            level=level,
        )

    def parse_all_rooms(rooms_xml):
        """
        Parse all XML rooms objects
        Input:
            - rooms_xml: object of XML rooms objects (level: rooms_xml)
        Output:
            - rooms: a list of parsed rooms objects (name, type)
        """
        rooms_parsed: list[PlanRoom] = []
        seen_names: set[str] = set()
        for level, level_rooms_xml in tqdm(
            rooms_xml.items(), total=len(rooms_xml.keys())
        ):
            for room_xml in tqdm(
                level_rooms_xml, total=len(level_rooms_xml), leave=False
            ):
                room = parse_room(room_xml, level)
                if room is None:
                    continue
                if room.name in seen_names:
                    continue
                seen_names.add(room.name)
                rooms_parsed.append(room)
        return rooms_parsed

    rooms_xml = list_all_levels_rooms()

    print("Parsing rooms...")
    rooms = parse_all_rooms(rooms_xml)

    return rooms


### CREATE ROOMS ###


def create_rooms(
    db,
    schedules: list[CourseScheduleEvent | CourseScheduleEventBase] | None = None,
    rooms_names: list[str] | None = None,
    update: bool = False,
) -> None:
    """Create or update rooms in the database based on schedules or explicit names."""

    if update:
        rooms_names = []
    elif not rooms_names:
        if not schedules:
            print("No schedules to create")
            return
        rooms_names = list_rooms(schedules)

    if rooms_names is None:
        rooms_names = []

    print("Getting rooms from plan.epfl.ch")
    plan_rooms = list_plan_rooms()
    plan_rooms_names = [plan_room.name for plan_room in plan_rooms]
    print(f"Found {len(plan_rooms_names)} rooms on plan.epfl.ch")

    print("Getting rooms from database")
    db_rooms = [
        RoomDocument.model_validate(room_doc)
        for room_doc in db.rooms.find({"available": True})
    ]
    print(f"Found {len(db_rooms)} rooms in database")

    print("Updating rooms in database")
    for db_room in tqdm(db_rooms):
        if db_room.name not in plan_rooms_names:
            print(f"Room {db_room.name} not found on plan.epfl.ch")
            continue

        plan_room = next(
            (room for room in plan_rooms if room.name == db_room.name),
            None,
        )
        if plan_room is None:
            continue

        requires_update = (
            db_room.type != plan_room.type
            or db_room.link != plan_room.link
            or db_room.coordinates != plan_room.coordinates
            or db_room.capacity != plan_room.capacity
            or db_room.level != plan_room.level
        )

        if not requires_update:
            continue

        update_payload = {
            "type": plan_room.type,
            "link": plan_room.link,
            "coordinates": plan_room.coordinates,
        }
        if plan_room.capacity is not None:
            update_payload["capacity"] = plan_room.capacity
        if plan_room.level is not None:
            update_payload["level"] = plan_room.level

        db.rooms.update_one({"name": db_room.name}, {"$set": update_payload})

    db_rooms_names = [room.name for room in db_rooms]
    new_rooms_names = [
        room_name for room_name in rooms_names if room_name not in db_rooms_names
    ]

    print("Filtering rooms to create")
    new_rooms: list[dict] = []
    for room_name in tqdm(new_rooms_names):
        plan_room = next(
            (room for room in plan_rooms if room.name == room_name),
            None,
        )

        room_type = "unknown"
        room_link = None
        room_coordinates = None
        room_capacity = None
        room_level = None

        room_building = re.split(r"\d", room_name)[0]
        room_building = re.sub(r"[-_]", " ", room_building)

        if plan_room is not None:
            room_type = plan_room.type or "unknown"
            room_link = plan_room.link
            room_coordinates = plan_room.coordinates
            room_capacity = plan_room.capacity
            room_level = plan_room.level

        new_room_doc = RoomDocument(
            name=room_name,
            type=room_type,
            available=True,
            link=room_link,
            coordinates=room_coordinates,
            building=room_building.strip() or None,
            capacity=room_capacity,
            level=room_level,
        )

        new_rooms.append(new_room_doc.model_dump(exclude_none=True))

    if len(new_rooms) == 0:
        print("No new rooms to create")
        return

    print(f"Inserting {len(new_rooms)} new rooms in database")
    try:
        db.rooms.insert_many(new_rooms)
    except Exception as e:
        print(e)

    return


def update_schedules(db, schedules: list[CourseScheduleEvent]) -> None:
    db_semester = get_current_or_next_semester(db)
    db_year_semester = get_current_or_next_semester(db, "year")

    if (
        db_semester is None
        or db_semester._id is None
        or db_year_semester is None
        or db_year_semester._id is None
    ):
        print("Missing semester information, skipping schedule update")
        return

    db_studyplans = [
        StudyPlanDocument.model_validate(plan_doc)
        for plan_doc in db.studyplans.find(
            {
                "available": True,
                "semester_id": {"$in": [db_semester._id, db_year_semester._id]},
            }
        )
    ]

    db_planned_in = [
        PlannedInDocument.model_validate(planned_doc)
        for planned_doc in db.planned_in.find(
            {
                "available": True,
                "studyplan_id": {
                    "$in": [plan._id for plan in db_studyplans if plan._id is not None]
                },
            }
        )
    ]

    man_courses_ids = set(get_man_courses_ids(db))
    db_planned_in_ids = [
        planned.course_id
        for planned in db_planned_in
        if planned.course_id not in man_courses_ids
    ]

    print("Getting schedules from DB...")
    db_schedules = [
        CourseScheduleDocument.model_validate(schedule_doc)
        for schedule_doc in db.course_schedules.find(
            {"course_id": {"$in": db_planned_in_ids}}
        )
    ]
    print(f"- {len(db_schedules)} schedules found")

    existing_index = {
        (
            schedule.course_id,
            schedule.start_datetime,
            schedule.end_datetime,
            schedule.label,
        ): schedule
        for schedule in db_schedules
    }

    schedules_to_remake_available: list[CourseScheduleDocument] = []
    new_schedules_payload: list[dict] = []

    print(f"Filtering {len(schedules)} schedules...")
    for incoming_schedule in tqdm(schedules, total=len(schedules)):
        key = (
            incoming_schedule.course_id,
            incoming_schedule.start_datetime,
            incoming_schedule.end_datetime,
            incoming_schedule.label,
        )
        existing = existing_index.pop(key, None)

        if existing is not None:
            if not existing.available:
                schedules_to_remake_available.append(existing)
            continue

        new_schedule_doc = CourseScheduleDocument(
            course_id=incoming_schedule.course_id,
            start_datetime=incoming_schedule.start_datetime,
            end_datetime=incoming_schedule.end_datetime,
            label=incoming_schedule.label,
            available=True,
        )
        new_schedules_payload.append(new_schedule_doc.model_dump())

    schedules_to_disable_ids = [
        schedule._id for schedule in existing_index.values() if schedule._id is not None
    ]

    print("Deleting schedules not in incoming schedules...")
    if schedules_to_disable_ids:
        try:
            db.course_schedules.update_many(
                {"_id": {"$in": schedules_to_disable_ids}},
                {"$set": {"available": False}},
            )
            print(f"- {len(schedules_to_disable_ids)} schedules deleted")
        except Exception as e:
            print(e)
    else:
        print("- No schedules to delete")

    remake_ids = [
        schedule._id
        for schedule in schedules_to_remake_available
        if schedule._id is not None
    ]
    print("Remaking available schedules...")
    if remake_ids:
        try:
            db.course_schedules.update_many(
                {"_id": {"$in": remake_ids}},
                {"$set": {"available": True}},
            )
            print(f"- {len(remake_ids)} schedules remade available")
        except Exception as e:
            print(e)
    else:
        print("- No schedules to remake available")

    if len(new_schedules_payload) == 0:
        print("No new schedules to create")
        return

    try:
        print(f"Creating {len(new_schedules_payload)} new schedules...")
        db.course_schedules.insert_many(new_schedules_payload)
        print(f"- {len(new_schedules_payload)} schedules created")
    except Exception as e:
        print(e)


def get_man_courses_ids(db) -> list[ObjectId]:
    semester = get_current_or_next_semester(db, "spring")
    if semester is None or semester._id is None:
        return []

    man_units = [
        UnitDocument.model_validate(unit_doc)
        for unit_doc in db.units.find({"section": "MAN"})
    ]
    man_unit_ids = [unit._id for unit in man_units if unit._id is not None]
    if not man_unit_ids:
        return []

    man_studyplans = [
        StudyPlanDocument.model_validate(plan_doc)
        for plan_doc in db.studyplans.find(
            {"unit_id": {"$in": man_unit_ids}, "semester_id": semester._id}
        )
    ]
    man_studyplan_ids = [plan._id for plan in man_studyplans if plan._id is not None]
    if not man_studyplan_ids:
        return []

    man_planned_in = [
        PlannedInDocument.model_validate(planned_doc)
        for planned_doc in db.planned_in.find(
            {"studyplan_id": {"$in": man_studyplan_ids}}
        )
    ]

    return list({planned.course_id for planned in man_planned_in})


def create_courses_bookings(db, schedules: list[CourseScheduleEvent]) -> None:
    db_rooms = [
        RoomDocument.model_validate(room_doc)
        for room_doc in db.rooms.find({"available": True})
    ]
    room_by_name = {room.name: room for room in db_rooms if room.name}

    db_schedules = [
        CourseScheduleDocument.model_validate(schedule_doc)
        for schedule_doc in db.course_schedules.find({"available": True})
    ]
    schedule_by_key = {
        (
            schedule.course_id,
            schedule.start_datetime,
            schedule.end_datetime,
            schedule.label,
        ): schedule
        for schedule in db_schedules
    }

    print("Getting DB bookings...")
    db_bookings = [
        CourseBookingDocument.model_validate(booking_doc)
        for booking_doc in db.course_bookings.find({"available": True})
    ]
    print(f"- {len(db_bookings)} bookings found in DB")

    bookings_by_schedule: dict[ObjectId, list[CourseBookingDocument]] = {}
    existing_pairs: set[tuple[ObjectId, ObjectId]] = set()
    for booking in db_bookings:
        bookings_by_schedule.setdefault(booking.schedule_id, []).append(booking)
        existing_pairs.add((booking.schedule_id, booking.room_id))

    bookings_to_remove_ids: list[ObjectId] = []
    new_bookings_candidates: list[dict] = []

    print("Filtering bookings....")
    for schedule in tqdm(schedules, total=len(schedules)):
        key = (
            schedule.course_id,
            schedule.start_datetime,
            schedule.end_datetime,
            schedule.label,
        )
        db_schedule = schedule_by_key.get(key)
        if db_schedule is None or db_schedule._id is None:
            continue

        schedule_rooms = []
        for room_name in schedule.rooms:
            room = room_by_name.get(room_name)
            if room is not None and room._id is not None:
                schedule_rooms.append(room)

        existing_bookings = bookings_by_schedule.get(db_schedule._id, [])
        for booking in existing_bookings:
            if not any(room._id == booking.room_id for room in schedule_rooms):
                bookings_to_remove_ids.append(booking._id)

        for room in schedule_rooms:
            pair = (db_schedule._id, room._id)
            if pair in existing_pairs:
                continue

            new_booking = CourseBookingDocument(
                schedule_id=db_schedule._id,
                room_id=room._id,
                available=True,
            )
            new_bookings_candidates.append(new_booking.model_dump())
            existing_pairs.add(pair)

    print(
        f" - {len(bookings_to_remove_ids)} bookings changed (not the schedule) (to remove)"
    )

    valid_schedule_ids = {
        schedule._id for schedule in db_schedules if schedule._id is not None
    }
    bookings_without_schedule_ids = [
        booking._id
        for booking in db_bookings
        if booking.schedule_id not in valid_schedule_ids
    ]

    all_bookings_to_disable = [
        booking_id
        for booking_id in bookings_without_schedule_ids + bookings_to_remove_ids
        if booking_id is not None
    ]

    print("Removing bookings without schedule...")
    if all_bookings_to_disable:
        try:
            db.course_bookings.update_many(
                {"_id": {"$in": all_bookings_to_disable}},
                {"$set": {"available": False}},
            )
        except Exception as e:
            print(e)
    else:
        print("- No bookings to remove")

    if len(new_bookings_candidates) == 0:
        print("No new bookings to create")
        return

    try:
        db.course_bookings.insert_many(new_bookings_candidates)
        print(f"- {len(new_bookings_candidates)} bookings created")
    except Exception as e:
        print(e)


def parse_room_events(room_name, start_date, end_date):
    asp_net_cookie = get_asp_net_cookie(room_name)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Cookie": f"ASP.NET_SessionId={asp_net_cookie}; petitpois=dismiss;",
        "Origin": "https://ewa.epfl.ch",
        "Referer": f"https://ewa.epfl.ch/room/Default.aspx?room={room_name}",
    }

    response = query_force(
        lambda: query_room(room_name, start_date, end_date, headers), max_retry=200
    )

    if not response:
        print(f"No response for {room_name}")
        return []
    return parse_events(response)


def parse_next_week(room_name):
    start_date = datetime.now()
    # start_date to begin of the week
    begin_of_week = start_date - timedelta(days=start_date.weekday())
    start_date = begin_of_week + timedelta(days=7)
    end_date = start_date + timedelta(days=7)
    start_date = start_date.strftime("%Y-%m-%dT%H:%M:%S")
    end_date = end_date.strftime("%Y-%m-%dT%H:%M:%S")

    asp_net_cookie = get_asp_net_cookie(room_name)
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "Cookie": f"ASP.NET_SessionId={asp_net_cookie}; petitpois=dismiss;",
        "Origin": "https://ewa.epfl.ch",
        "Referer": f"https://ewa.epfl.ch/room/Default.aspx?room={room_name}",
    }

    response = query_force(
        lambda: query_room(room_name, start_date, end_date, headers), max_retry=100
    )
    if not response:
        print(f"No response for {room_name}")
        return []
    return parse_events(response)


def get_asp_net_cookie(room_name):
    response = query_force(
        lambda: requests.get(f"https://ewa.epfl.ch/room/Default.aspx?room={room_name}"),
        max_retry=100,
    )

    if not response:
        print("No response")
        return None
    if response.status_code == 200:
        cookies = response.cookies
        return cookies.get("ASP.NET_SessionId", None)
    return None


def query_room(room_name, start_date, end_date, headers):
    # generate columns values for the request (for the 7 days starting from start_date)
    columns = []
    start_datetime = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S")
    for i in range(7):
        day = start_datetime + timedelta(days=i)
        columns.append(
            {
                "Value": None,
                "Name": day.strftime("%d.%m.%Y"),
                "ToolTip": None,
                "Date": day.strftime("%Y-%m-%dT00:00:00"),
                "Children": [],
            }
        )

    data = {
        "MIME Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": "/wEPDwUKMTM5ODM2NTk2OQ9kFgJmD2QWAgIFD2QWBAIBD2QWBgIBDw8WAh4EVGV4dAUEQkMwMWRkAgMPDxYCHgtfIURhdGFCb3VuZGdkZAIFDw8WBh4JVGFnRmllbGRzFQIEbmFtZQJpZB8BZx4JU3RhcnREYXRlBgCAPrfdMNwIZGQCAw8PFgIfAAUEMjAyNGRkZBcDZBZ3ATHldACedIUzjN5kMtI2cxXWLlr1+Lr9oP0L",
        "__VIEWSTATEGENERATOR": "CC8E5E3B",
        "__CALLBACKID": "ctl00$ContentPlaceHolder1$DayPilotCalendar1",
        "__CALLBACKPARAM": """JSON{"action":"Command","parameters":{"command":"navigate"},"data":{"start":"2024-02-26T00:00:00","end":"2024-03-04T00:00:00","days":7},"header":{"control":"dpc","id":"ContentPlaceHolder1_DayPilotCalendar1","clientState":{},"columns":[{"Value":null,"Name":"19.02.2024","ToolTip":null,"Date":"2024-02-19T00:00:00","Children":[]},{"Value":null,"Name":"20.02.2024","ToolTip":null,"Date":"2024-02-20T00:00:00","Children":[]},{"Value":null,"Name":"21.02.2024","ToolTip":null,"Date":"2024-02-21T00:00:00","Children":[]},{"Value":null,"Name":"22.02.2024","ToolTip":null,"Date":"2024-02-22T00:00:00","Children":[]},{"Value":null,"Name":"23.02.2024","ToolTip":null,"Date":"2024-02-23T00:00:00","Children":[]},{"Value":null,"Name":"24.02.2024","ToolTip":null,"Date":"2024-02-24T00:00:00","Children":[]},{"Value":null,"Name":"25.02.2024","ToolTip":null,"Date":"2024-02-25T00:00:00","Children":[]}],"days":7,"startDate":"2024-02-19T00:00:00","cellDuration":30,"heightSpec":"BusinessHours","businessBeginsHour":7,"businessEndsHour":20,"viewType":"Days","dayBeginsHour":0,"dayEndsHour":0,"headerLevels":1,"backColor":"White","nonBusinessBackColor":"White","eventHeaderVisible":true,"timeFormat":"Clock12Hours","showAllDayEvents":true,"tagFields":["name","id"],"hourNameBackColor":"#F3F3F9","hourFontFamily":"Tahoma,Verdana,Sans-serif","hourFontSize":"16pt","hourFontColor":"#42658C","selected":"","hashes":{"callBack":"PFfUEJ3wrfDg2Gfp/oBSL89g8Kc=","columns":"bzP1mnnwN+umsglYKroAi3JEFP4=","events":"xVFNXcegBTUqJf6sHwhHjX6e88g=","colors":"u6JkuOn4xmGT35AnGNQ0dmPOOqk=","hours":"K+iMpCQsduglOsYkdIUQZQMtaDM=","corner":"0XBQYL2rjFh+nn9As5pzf4+hWqg="}}}""",
    }

    response = requests.post(
        "https://ewa.epfl.ch/room/Default.aspx", headers=headers, data=data
    )

    return response


def populate_events_room(db, parsed_events):
    db_rooms = list(db.rooms.find({"available": True}))

    new_events = []
    for event in tqdm(parsed_events, total=len(parsed_events)):
        room_name = event["room"]
        if room_name in MAP_ROOMS:
            room_name = MAP_ROOMS[room_name]

        if isinstance(room_name, list):
            for room_name_sub in room_name:
                room = list(filter(lambda x: x["name"] == room_name_sub, db_rooms))
                if len(room) == 0:
                    print(f"Room {room_name_sub} not found in db")
                    continue
                room = room[0]
                new_event = event
                new_event["room"] = room["_id"]
                new_events.append(new_event)
        else:
            room = list(filter(lambda x: x["name"] == room_name, db_rooms))
            if len(room) == 0:
                print(f"Room {room_name} not found in db")
                continue
            room = room[0]
            new_event = event
            new_event["room"] = room["_id"]
            new_events.append(new_event)

    return new_events


def create_event_bookings(db, parsed_events):
    db_event_bookings = list(db.event_bookings.find({"available": True}))
    new_bookings = []
    for event in tqdm(parsed_events, total=len(parsed_events)):
        found = False
        for db_booking in db_event_bookings:
            if (
                event["room"] == db_booking["room_id"]
                and event["start_datetime"] == db_booking["start_datetime"]
                and event["end_datetime"] == db_booking["end_datetime"]
                and event["name"] == db_booking["name"]
            ):
                found = True
                break

        if not found:
            new_booking = {
                "room_id": event["room"],
                "start_datetime": event["start_datetime"],
                "end_datetime": event["end_datetime"],
                "name": event["name"],
                "label": event["label"],
                "available": True,
            }
            new_bookings.append(new_booking)

    if len(new_bookings) == 0:
        print("No new bookings to create")
        return None
    print(f"Creating {len(new_bookings)} new bookings")
    db.event_bookings.insert_many(new_bookings)


def split_date_range(start_date, end_date):
    """
    Split a date range into a list of date ranges, each starting at the beginning of a week and ending at the end of a week
    """
    date_ranges = []

    current_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S")

    while current_date <= datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S"):
        # Find the beginning of the week
        begin_of_week = current_date - timedelta(days=current_date.weekday())
        # Find the end of the week
        end_of_week = begin_of_week + timedelta(days=7)
        # Add the date range to the list
        date_ranges.append((begin_of_week, end_of_week))
        # Move to the next week
        current_date = end_of_week + timedelta(days=1)
    return date_ranges


def parse_all_rooms_events(rooms_names, start_date, end_date):
    parsed_events = []

    date_ranges = split_date_range(start_date, end_date)

    for room_name in tqdm(rooms_names, total=len(rooms_names)):
        for date_range in tqdm(date_ranges, total=len(date_ranges), leave=False):
            start_date = date_range[0].strftime("%Y-%m-%dT%H:%M:%S")
            end_date = date_range[1].strftime("%Y-%m-%dT%H:%M:%S")
            room_events = parse_room_events(room_name, start_date, end_date)
            for event in room_events:
                new_event = {
                    "room": room_name,
                    "start_datetime": datetime.strptime(
                        event["Start"], "%Y-%m-%dT%H:%M:%S"
                    ),
                    "end_datetime": datetime.strptime(
                        event["End"], "%Y-%m-%dT%H:%M:%S"
                    ),
                    "name": event["Text"],
                    "label": "event",
                    "available": True,
                }
                parsed_events.append(new_event)

    return parsed_events


def parse_all_rooms_next_week(rooms_names):
    parsed_events = []
    for room_name in tqdm(rooms_names, total=len(rooms_names)):
        room_events = parse_next_week(room_name)
        for event in room_events:
            new_event = {
                "room": room_name,
                "start_datetime": datetime.strptime(
                    event["Start"], "%Y-%m-%dT%H:%M:%S"
                ),
                "end_datetime": datetime.strptime(event["End"], "%Y-%m-%dT%H:%M:%S"),
                "name": event["Text"],
                "label": "event",
                "available": True,
            }
            parsed_events.append(new_event)

    return parsed_events
