import requests
from bs4 import BeautifulSoup
import re
from config import *
from datetime import datetime, timedelta
from tqdm import tqdm

### GET ALL COURSES URLS ###
def get_all_courses_url():
    URL_ROOT = 'https://edu.epfl.ch/'
    shs = ['https://edu.epfl.ch/studyplan/fr/bachelor/programme-sciences-humaines-et-sociales/', 'https://edu.epfl.ch/studyplan/fr/master/programme-sciences-humaines-et-sociales/']
    page = requests.get(URL_ROOT)
    soup = BeautifulSoup(page.content, "html.parser")
    cards = soup.findAll("div", class_="card-title")
    promos = [card.find('a').get('href') for card in cards]
    courses_url = []
    courses_names = []
    for promo in tqdm(promos):
        page = requests.get(URL_ROOT + promo)
        soup = BeautifulSoup(page.content, "html.parser")
        sections = [x.get('href') for x in soup.find('main').find('ul').findAll('a')]
        for section in sections:
            page = requests.get(URL_ROOT + section)
            soup = BeautifulSoup(page.content, "html.parser")
            for course in soup.find('main').findAll('div', class_="cours-name"):
                if course.find('a') != None:
                    course_url = course.find('a').get('href')
                    course_name = course_url.split('/').pop()
                    if 'programme-sciences-humaines-et-sociales' not in course_url and course_name not in courses_names:
                        courses_url.append(course_url)
                        courses_names.append(course_name)

    # Add SHS courses
    for url in shs:
        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        for course in soup.findAll("div", class_="cours-name"):
            if course.find('a') != None:
                course_url = course.find('a').get('href')
                course_name = course_url.split('/').pop()
                if course_name not in courses_names:
                    courses_url.append(course_url)
                    courses_names.append(course_name)
                
    return courses_url


### PARSE COURSE ###
def parse_course(url):
    page = requests.get(url)
    if (page.status_code == 404):
        print(url)
        return
        
    soup = BeautifulSoup(page.content, "html.parser")
    
    title = soup.find('main').find('h1').text
    if (soup.find('div', class_="course-summary") == None):
        print(url)
    code = soup.find('div', class_="course-summary").findAll('p')[0].text.split('/')[0].strip()
    credits = int(re.findall(r'\d+', soup.find('div', class_="course-summary").findAll('p')[0].text.split('/')[1])[0])
    teachers = [(x.text, x.get('href')) for x in soup.find('div', class_="course-summary").findAll('p')[1].findAll('a')]
    language = soup.find('div', class_="course-summary").findAll('p')
    if len(language) > 2:
        language = language[2].text.split(':')
        if len(language) > 1:
            language = language[1].strip()
        else:
            print(url)
            language = None
    else:
        print(url)
        language = None

    studyplans_elements = soup.find('div', class_="study-plans").findAll('button', class_="collapse-title-desktop")

    # studyplans_elements are buttons with section name before the xxxx-xxxx years and the semester after
    re_pattern = r'(\d{4}-\d{4})'

    studyplans = []
    for studyplan_element in studyplans_elements:
        studyplan = {}
        parts = re.split(re_pattern, studyplan_element.text)
        studyplan['section'] = parts[0].strip().replace("\n", " ")
        studyplan['semester'] = parts[1] + ' ' + parts[2].strip()
        studyplans.append(studyplan) 
    
    course = {
        'name': title,
        'code': code,
        'credits': credits,
        'studyplans': studyplans,
        'teachers': teachers,
        'edu_url': url,
        'language': language,
    }

    return course


### FILTER DUPLICATES COURSES ###
def filter_duplicates_courses(courses):
    '''
        Filter duplicates courses
        Input:
            - courses: a list of courses
        Output:
            - filtered_courses: a list of courses without duplicates
    '''
    filtered_courses = []
    course_codes = set()
    for course in courses:
        course_code = course.get("code")

        if (course_code not in course_codes):
            course_codes.add(course_code)
            filtered_courses.append(course)
    return filtered_courses


### CREATE COURSES ###
def create_courses(db, courses):
    '''
        Create courses in the db
        Input:
            - courses: a list of courses to create
        Output:
            - None
    '''
    db_courses_codes = [course.get('code') for course in db.courses.find()]
    
    new_courses = []
    for course in tqdm(courses, total=len(courses)):
        if (course.get("code") in db_courses_codes):
            continue
        new_course = {
            "code": course.get("code"),
            "name": course.get("name"),
            "credits": course.get("credits"),
            "edu_url": course.get("edu_url"),
            "available": True
        }
        if (course.get("language") != None):
            new_course["language"] = course.get("language")

        new_courses.append(new_course)

    if (len(new_courses) == 0):
        return
    
    try:
        db.courses.insert_many(new_courses)
    except Exception as e:
        print(e)

    return


### CREATE TEACHERS ###
def create_teachers(db, courses):
    '''
        Create teachers in the db
        Input:
            - courses: a list of courses to create
        Output:
            - None
    '''
    db_teachers = list(db.teachers.find({
        "available": True
    }))
    
    new_teachers = []
    for course in tqdm(courses, total=len(courses)):
        for teacher in course.get('teachers'):
            found = False
            for db_teacher in db_teachers:
                if (db_teacher.get("people_url") == teacher[1]):
                    found = True
                    break
                
            if (found == True):
                continue

            for new_teacher in new_teachers:
                if (new_teacher.get("people_url") == teacher[1]):
                    found = True
                    break

            if (found == True):
                continue

            new_teachers.append({
                "name": teacher[0],
                "people_url": teacher[1],
                "available": True
            })

    if (len(new_teachers) == 0):
        return
    
    try:
        db.teachers.insert_many(new_teachers)
    except Exception as e:
        print(e)

    return


### ADD TEACHERS TO COURSES ###
def add_teachers_to_courses(db, courses):
    '''
        Add teachers to courses in the db
        Input:
            - courses: a list of courses to update
        Output:
            - None
    '''
    db_courses = list(db.courses.find({
        "available": True
    }))
    db_teachers = list(db.teachers.find({
        "available": True
    }))
    
    for course in tqdm(courses, total=len(courses)):
        db_course = None
        for db_course_ in db_courses:
            if (db_course_.get("code") == course.get("code")):
                db_course = db_course_
                break
        
        if (db_course == None):
            continue

        course_teachers_ids = []

        for teacher in course.get('teachers'):
            found = False
            for db_teacher in db_teachers:
                if (db_teacher.get("people_url") == teacher[1]):
                    found = True
                    break
                
            if (found == True):
                course_teachers_ids.append(db_teacher.get("_id"))
                continue

        db.courses.update_one({
            "_id": db_course.get("_id")
        }, {
            "$set": {
                "teachers": course_teachers_ids
            }
        })

    return

### CREATE NEW SEMESTER ###
def create_new_semester(db, **kwargs):
    name = kwargs.get("name") or None
    start_date = kwargs.get("start_date") or None
    end_date = kwargs.get("end_date") or None
    type = kwargs.get("type") or None
    available = kwargs.get("available") or False
    skip_dates = kwargs.get("skip_dates") or []

    db_semesters = list(db.semesters.find())

    # Check if semester already exists
    found = False
    for db_semester in db_semesters:
        if (db_semester.get("name") == name):
            found = True
            break

    if (found == True):
        print("Semester already exists")
        return
    
    try:
        db.semesters.insert_one({
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "type": type,
            "available": available,
            "skip_dates": skip_dates
       })
    except Exception as e:
        print(e)

def list_units(courses):
    units = []
    unique_sections = set()
    unique_promos = set()
    for courses in courses:
        for studyplan in courses['studyplans']:
            if (studyplan['section'] not in unique_sections):
                unique_sections.add(studyplan['section'])
            if (studyplan['semester'] not in unique_promos):
                unique_promos.add(studyplan['semester'])
            if (studyplan['section'], studyplan['semester']) not in units:
                units.append((studyplan['section'], studyplan['semester']))
    
    return units

def create_units(db, courses):

    units = list_units(courses)

    db_units = list(db.units.find())
    db_units_names = [unit.get('name') for unit in db_units]

    semester_re_pattern = r'(\d{4}-\d{4})'

    new_units = []
    new_units_names = set()
    for unit in tqdm(units):
        semester_long = re.split(semester_re_pattern, unit[1])[2].strip()
        unit_name = unit[0] + ' - ' + semester_long if semester_long in MAP_PROMOS_LONG else unit[0]
        if (unit_name not in db_units_names and unit_name not in new_units_names):

            promo = MAP_PROMOS_LONG[semester_long] if semester_long in MAP_PROMOS_LONG else None
            code = MAP_SECTIONS[unit[0]] + '-' + promo if promo != None else MAP_SECTIONS[unit[0]]
            new_units.append({
                'code': code,
                'promo': promo,
                'section': MAP_SECTIONS[unit[0]],
                'name': unit_name,
                'available': True
            })
            new_units_names.add(unit_name)

    if (len(new_units) == 0):
        return
    
    try:
        db.units.insert_many(new_units)
    except Exception as e:
        print(e)

    return