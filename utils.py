import requests
from bs4 import BeautifulSoup
import re
from config import *
from datetime import datetime, timedelta
from tqdm import tqdm
from pyproj import Transformer as pyproj_Transformer
import numpy as np
import json
import multiprocessing
import os

### GET ALL COURSES URLS ###
def get_all_courses_url():
    URL_ROOT = 'https://edu.epfl.ch/'
    shs = ['https://edu.epfl.ch/studyplan/fr/bachelor/programme-sciences-humaines-et-sociales/', 'https://edu.epfl.ch/studyplan/fr/master/programme-sciences-humaines-et-sociales/']
    page = requests.get(URL_ROOT, timeout=500)
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
    
    # Filter duplicates
    courses_url = list(set(courses_url))

    return courses_url

def parse_credits(soup):
    credits = soup.find('div', class_="course-summary")
    if (credits == None):
        return None
    
    credits = credits.findAll('p')
    if (len(credits) == 0):
        return None
    
    credits = credits[0].text.split('/')
    if (len(credits) == 0):
        return None
    
    credits = re.findall(r'\d+', credits[1])
    if (len(credits) == 0):
        return None
    
    return int(credits[0])
        

### PARSE COURSE ###
def parse_course(url):
    page = requests.get(url, timeout=(500, 500))
    if (page.status_code == 404):
        print(f'404: {url}')
        return None
        
    soup = BeautifulSoup(page.content, "html.parser")
    
    title = soup.find('main').find('h1').text
    if (soup.find('div', class_="course-summary") == None):
        print(url)
    code = soup.find('div', class_="course-summary").findAll('p')[0].text.split('/')[0].strip()
    credits = parse_credits(soup)
    teachers = [(x.text, x.get('href')) for x in soup.find('div', class_="course-summary").findAll('p')[1].findAll('a')]
    language = soup.find('div', class_="course-summary").findAll('p')
    if len(language) > 2:
        language = language[2].text.split(':')
        if 'Langue' in language[0] and len(language) > 1:
            language = language[1].strip()
        else:
            language = None
    else:
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

### PARSE ALL COURSES ###
def parse_all_courses():
    URL_ROOT = 'https://edu.epfl.ch'
    print('Getting all courses urls...')
    courses_url = get_all_courses_url()
    print(f'- {len(courses_url)} courses urls found')
    courses = []
    print('Parsing courses...')
    for url in tqdm(courses_url, total=len(courses_url)):
        course = parse_course(URL_ROOT + url)
        if course != None:
            courses.append(course)
    print(f'- {len(courses)} courses parsed')
    return courses

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
    print('Getting courses from DB...')
    db_courses_codes = [course.get('code') for course in db.courses.find()]
    print(f'- {len(db_courses_codes)} courses found in DB')
    
    print('Filtering courses...')
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

    print('Creating courses...')
    if (len(new_courses) == 0):
        print('- No new courses to create')
        return
    
    try:
        db.courses.insert_many(new_courses)
        print(f'- {len(new_courses)} courses created')
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

    print('Getting teachers from DB...')
    db_teachers = list(db.teachers.find({
        "available": True
    }))
    print(f'- {len(db_teachers)} teachers found')

    print('Filtering teachers...')
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

    print('Creating new teachers...')
    if (len(new_teachers) == 0):
        print('- No new teachers')
        return
    
    try:
        db.teachers.insert_many(new_teachers)
        print(f'- {len(new_teachers)} teachers created')
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
    print('Getting teachers from DB...')
    db_teachers = list(db.teachers.find({
        "available": True
    }))
    print(f'- {len(db_teachers)} teachers found')
    
    print('Adding teachers to courses...')
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

    print('Getting units from DB...')
    db_units = list(db.units.find())
    print(f'- {len(db_units)} units found')
    db_units_names = [unit.get('name') for unit in db_units]

    semester_re_pattern = r'(\d{4}-\d{4})'

    new_units = []
    new_units_names = set()
    print('Filtering units...')
    for unit in tqdm(units):
        semester_long = re.split(semester_re_pattern, unit[1])[2].strip()
        unit_name = unit[0] + ' - ' + semester_long if semester_long in MAP_PROMOS_LONG else unit[0]
        if (unit_name not in db_units_names and unit_name not in new_units_names):

            new_unit = dict()
            promo = MAP_PROMOS_LONG[semester_long] if semester_long in MAP_PROMOS_LONG else None
            if (promo != None):
                new_unit['promo'] = promo
            if (unit[0] not in MAP_SECTIONS):
                print('Section not found in MAP_SECTIONS', unit[0])
                continue
            code = MAP_SECTIONS[unit[0]] + '-' + promo if promo != None else MAP_SECTIONS[unit[0]]
            new_unit['code'] = code
            new_unit['section'] = MAP_SECTIONS[unit[0]]
            new_unit['name'] = unit_name
            new_unit['available'] = True

            new_units_names.add(unit_name)
            new_units.append(new_unit)

    print('Creating new units...')
    if (len(new_units) == 0):
        print('- No units to create')
        return
    
    try:
        db.units.insert_many(new_units)
        print(f'- {len(new_units)} units created')
    except Exception as e:
        print(e)

    return

def create_studyplans(db, courses):
    print('Getting studyplans from DB...')
    db_studyplans = list(db.studyplans.find({
        'available': True
    }))
    print(f'- {len(db_studyplans)} studyplans found')
    
    # Find current or next semester for each semester type (fall, spring, year)
    db_semester_fall = get_current_or_next_semester(db, 'fall')
    db_semester_spring = get_current_or_next_semester(db, 'spring')
    db_semester_year = get_current_or_next_semester(db, 'year')
    
    db_semesters = [db_semester_fall, db_semester_spring, db_semester_year]

    db_units = list(db.units.find({ 'available': True }))

    new_studyplans = []
    semester_re_pattern = r'(\d{4}-\d{4})'
    print('Filtering studyplans...')
    for course in courses:
        for studyplan in course['studyplans']:
            semester_long = re.split(semester_re_pattern, studyplan['semester'])[2].strip()
            unit_name = studyplan['section'] + ' - ' + semester_long if semester_long in MAP_PROMOS_LONG else studyplan['section']

            # Find unit in db
            studyplan_unit = list(filter(lambda unit: unit['name'] == unit_name, db_units))
            if (studyplan_unit == None or len(studyplan_unit) == 0):
                print('Unit not found', unit_name)
                continue
            studyplan_unit = studyplan_unit[0]
            
            # Map semester name to semester type
            semester_type = None
            if semester_long not in MAP_SEMESTERS_LONG:
                semester_type = MAP_SEMESTERS_LONG[studyplan['section']]
            else:
                semester_type = MAP_SEMESTERS_LONG[semester_long]

            # Find semester in db
            studyplan_semester = list(filter(lambda semester: semester_type == semester.get('type'), db_semesters))
            if (studyplan_semester == None or len(studyplan_semester) == 0):
                continue
            studyplan_semester = studyplan_semester[0]

            # Check if studyplan already exists in db
            found = False
            for db_plan in db_studyplans:
                if (
                    db_plan['unit_id'] == studyplan_unit['_id'] and
                    db_plan['semester_id'] == studyplan_semester['_id']
                ):
                    found = True
                    break
            
            # If studyplan already exists, continue
            if (found == True):
                continue
            
            # Check if studyplan already exists in new_studyplans
            found = False
            for new_plan in new_studyplans:
                if (
                    new_plan['unit_id'] == studyplan_unit['_id'] and
                    new_plan['semester_id'] == studyplan_semester['_id']
                ):
                    found = True
                    break

            # If studyplan already exists, continue
            if (found == True):
                continue

            new_studyplans.append({
                'unit_id': studyplan_unit['_id'],
                'semester_id': studyplan_semester['_id'],
                'available': True,
            })

    print('Creating studyplans...')
    if (len(new_studyplans) == 0):
        print('- No new studyplans to create')
        return

    # Find duplicates in new_studyplans
    
    try:
        db.studyplans.insert_many(new_studyplans)
        print(f'- {len(new_studyplans)} studyplans created')
    except Exception as e:
        print(e)

    return

def create_planned_in(db, courses):
    db_courses = list(db.courses.find({
        'available': True
    }))
    
    db_units = list(db.units.find({
        'available': True
    }))

    db_semester_fall = get_current_or_next_semester(db, 'fall')
    db_semester_spring = get_current_or_next_semester(db, 'spring')
    db_semester_year = get_current_or_next_semester(db, 'year')
    
    db_semesters = [db_semester_fall, db_semester_spring, db_semester_year]

    print('Getting studyplans from DB...')
    db_studyplans = list(db.studyplans.find({
        'available': True,
        'semester_id': {
            '$in': [semester['_id'] for semester in db_semesters]
        }
    }))
    print(f'- {len(db_studyplans)} studyplans found')

    print('Getting planned_in from DB...')
    db_planned_in = list(db.planned_in.find({
        'available': True,
        "studyplan_id": {
            "$in": [studyplan['_id'] for studyplan in db_studyplans]
        }
    }))
    print(f'- {len(db_planned_in)} planned_in found')

    semester_re_pattern = r'(\d{4}-\d{4})'
    new_planned_ins = []
    print('Filtering planned_in...')
    for course in tqdm(courses, total=len(courses)):
        db_course = list(filter(lambda db_course: db_course['code'] == course['code'], db_courses))[0]
        if (db_course == None):
            continue

        course_studyplans_ids = set()
        
        for studyplan in course['studyplans']:
            semester_long = re.split(semester_re_pattern, studyplan['semester'])[2].strip()
            unit_name = studyplan['section'] + ' - ' + semester_long if semester_long in MAP_PROMOS_LONG else studyplan['section']

            # Find unit in db
            studyplan_unit = list(filter(lambda unit: unit['name'] == unit_name, db_units))[0]
            if (studyplan_unit == None):
                print('Unit not found')
                continue

            # Map semester name to semester type
            if semester_long not in MAP_SEMESTERS_LONG:
                semester_type = MAP_SEMESTERS_LONG[studyplan['section']]
            else:
                semester_type = MAP_SEMESTERS_LONG[semester_long]

            # Find semester in db
            studyplan_semester_db = list(filter(lambda semester: semester_type == semester.get('type'), db_semesters))
            if (studyplan_semester_db == None or len(studyplan_semester_db) == 0):
                continue
            studyplan_semester_db = studyplan_semester_db[0]

            # Find studyplan in db
            studyplan_db = list(filter(lambda plan: plan['unit_id'] == studyplan_unit['_id'] and plan['semester_id'] == studyplan_semester_db['_id'], db_studyplans))
            if (studyplan_db == None or len(studyplan_db) == 0):
                print('Studyplan not found')
                continue
            studyplan_db = studyplan_db[0]

            # Find planned_in in db
            planned_in_db = list(filter(lambda planned_in: \
                planned_in['course_id'] == db_course['_id'] and \
                planned_in['studyplan_id'] == studyplan_db['_id'], db_planned_in))

            if (studyplan_db['_id'] in course_studyplans_ids):
                continue
            course_studyplans_ids.add(studyplan_db['_id'])

            if (planned_in_db == None or len(planned_in_db) == 0):
                print(studyplan_db)
                new_planned_ins.append({
                    'course_id': db_course['_id'],
                    'studyplan_id': studyplan_db['_id'],
                    'available': True
                })


    print('Creating planned_in...')
    if (len(new_planned_ins) == 0):
        print('- No new planned_in to create')
        return

    try:
        db.planned_in.insert_many(new_planned_ins)
        print(f'- {len(new_planned_ins)} planned_in created')
    except Exception as e:
        print(e)
    return

def get_current_or_next_semester(db, semester_type=None):
    
    today = datetime.today()

    # If semester_type is specified, get the current or next semester of this type
    if (semester_type != None):
        semester = db.semesters.find_one({
            "end_date": {
                "$gte": today
            },
            "type": semester_type
        }, sort=[("end_date", 1)])

        return semester

    # Get the current semester
    semester = db.semesters.find_one({
        "start_date": {
            "$lte": today
        },
        "end_date": {
            "$gte": today
        },
        "type": {
            "$ne": "year"
        }
    })

    # If no current semester is found, get the first next semester
    if not semester:
        semester = db.semesters.find_one({
            "start_date": {
                "$gte": today
            },
            "type": {
                "$ne": "year"
            }
        }, sort=[("start_date", 1)])
        
    return semester

def find_semester_courses_ids(db, semester):

    if (semester == None):
        return

    print('Getting studyplans from DB...')
    filtered_studyplans = list(db.studyplans.find({
        'available': True,
        'semester_id': semester['_id']
    }))
    filtered_studyplans_ids = [studyplan['_id'] for studyplan in filtered_studyplans]
    print(f'- {len(filtered_studyplans_ids)} studyplans found')


    planned_in = list(db.planned_in.find({
        'available': True,
        'studyplan_id': {
            '$in': filtered_studyplans_ids
        }
    }))
    semester_courses_ids = [planned['course_id'] for planned in planned_in]


    return semester_courses_ids

### PARSE COURSE SCHEDULE ###
def get_course_schedule(url):
    page = requests.get(url)
    if (page.status_code == 404):
        print(url)
        return
        
    soup = BeautifulSoup(page.content, "html.parser")

    schedule = soup.find('div', class_="coursebook-week-caption sr-only")

    edoc = False
    if (schedule == None):
        schedule_parsed= parse_schedule_EDOC(soup)
        edoc = True
    else:
        schedule_parsed = parse_schedule(soup)

    if (schedule_parsed == None):
        return None, edoc

    return schedule_parsed, edoc

### PARSE SCHEDULE DOCTORAL SCHOOL ###
def parse_schedule_EDOC(soup):
    # Ecole doctorale
    schedule = dict()

    iframe_soup = BeautifulSoup(requests.get(soup.find("iframe").attrs['src']).content, "html.parser")
    if (iframe_soup.find('table') == None):
        #print(f'\033[91m SKIP (no schedule) \033[0m')
        return None
    
    rows = iframe_soup.findAll('tr')
    creneaux = []
    
    for i, row in enumerate(rows):
        if (i == 0):
            continue
        if (row.find('th') != None):
            # find a dd.mm.yyyy date
            date = re.findall(r'\d{2}.\d{2}.\d{4}', row.find('th').text)
            if (len(date) > 0):
                date = datetime.strptime(date[0], '%d.%m.%Y')
        elif (row.get("class") != None and 'grisleger' in row.get("class") and date != None):
            time = [x.split(':')[0] for x in row.findAll('td')[0].text.split('-')]
            
            start_hour = int(time[0])
            duration = int(time[1]) - int(time[0])
        
            rooms_found = [room.text for room in row.findAll('td')[1].findAll('a')]

            rooms = []
            for room in rooms_found:
                if (room in MAP_ROOMS):
                    if (isinstance(MAP_ROOMS[room], list)):
                        rooms += [x for x in MAP_ROOMS[room]]
                    else:
                        rooms.append(MAP_ROOMS[room])
                elif (room not in ROOMS_FILTER):
                    rooms.append(room)
            label = row.findAll('td')[2].text
            if (label == 'L'):
                label = 'cours'
            elif(label == 'E'):
                label = 'exercice'
            elif(label == 'P'):
                label = 'projet'
            else:
                print(label)

            # create datetime object from date string dd.mm.yyyy and time string hh
            start_datetime = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            creneau = {
                'start_datetime': start_datetime,
                'end_datetime': start_datetime + timedelta(hours=duration),
                'label': label,
                'rooms': rooms,
            }
            if (len(rooms) > 0):
                creneaux.append(creneau)
            creneau = {}

    if len(creneaux) == 0:
        #print(f'\033[91m SKIP (no creneaux) \033[0m')
        return None
    
    schedule = []
    for creneau in creneaux:
        found = False
        for i, s in enumerate(schedule):
            if (s['start_datetime'] == creneau['start_datetime'] and s['end_datetime'] == creneau['end_datetime'] and s['label'] == creneau['label']):
                schedule[i]['rooms'] = schedule[i]['rooms'] + creneau['rooms']
                found = True
                break
        if (not found):
            schedule.append(creneau)    

    return schedule


def parse_schedule(soup):
    creneaux = soup.find('div', class_="coursebook-week-caption sr-only").findAll('p')

    schedule = []
    for creneau in creneaux:
         # Extracting the full text from the paragraph
        full_text = creneau.get_text().replace('\xa0', ' ')

        day = full_text.split(',')[0]

        # Mapping days to weekday numbers
        days_map = {'Lundi': 0, 'Mardi': 1, 'Mercredi': 2, 'Jeudi': 3, 'Vendredi': 4, 'Samedi': 5, 'Dimanche': 6}
        day = days_map[day]

        # Extracting start hour and duration
        time_match = re.search(r'(\d{1,2}h) - (\d{1,2}h)', full_text)
        start_hour, end_hour = time_match.groups() if time_match else (None, None)
        duration = int(end_hour[:-1]) - int(start_hour[:-1]) if start_hour and end_hour else None
        start_hour = int(start_hour[:-1]) if start_hour else None

        # Extracting label
        first_room = creneau.find('a')
        if first_room:
            label = creneau.find('a').previousSibling.text.split(': ')[1].strip()
        else:
            label = creneau.text.split(': ')[1].strip()

        if label == 'Cours':
            label = 'cours'
        elif label == 'Exercice, TP':
            label = 'exercice'
        elif label == 'Projet, autre':
            label = 'projet'
            

        # Extracting rooms
        rooms_found = [link.get_text() for link in creneau.findAll('a', href=True)]
        rooms = []
        for room in rooms_found:
            if (room in MAP_ROOMS):
                if (isinstance(MAP_ROOMS[room], list)):
                    rooms += [x for x in MAP_ROOMS[room]]
                else:
                    rooms.append(MAP_ROOMS[room])
            elif (room not in ROOMS_FILTER):
                rooms.append(room)

        schedule.append({
            'day': day,
            'start_hour': start_hour,
            'duration': duration,
            'label': label,
            'rooms': rooms
        })

    return schedule
    
def create_semester_schedule(schedule, db_semester):
    start_date = db_semester.get('start_date')
    end_date = db_semester.get('end_date')
    skip_dates = db_semester.get('skip_dates')
    if (skip_dates == None):
        skip_dates = []


    semester_schedule = []

     # Iterate through each day of the semester
    current_date = start_date
    while current_date <= end_date:
        if current_date not in skip_dates:
            # Add each event in the schedule to this day
            for event in schedule:
                if event['day'] != current_date.weekday():
                    continue
                
                # Parse start hour
                start_hour = datetime.strptime(str(event['start_hour']), '%H').time()
                start_datetime = datetime.combine(current_date, start_hour)

                # Calculate end datetime based on duration
                duration_hours = int(event['duration'])
                end_datetime = start_datetime + timedelta(hours=duration_hours)

                # Create a new event entry for the semester schedule
                event_entry = {
                    'start_datetime': start_datetime,
                    'end_datetime': end_datetime,
                    'label': event['label'],
                    'rooms': event['rooms']
                }

                semester_schedule.append(event_entry)
        
        # Move to the next day
        current_date += timedelta(days=1)

    return semester_schedule
    

def process_course_schedules(course, db_courses_semester_codes, semester):
    course_edu_url = course.get('edu_url')
    if (course_edu_url == None):
        return None

    result = get_course_schedule(course_edu_url)
    if (result == None):
        print(f'No schedule found for {course_edu_url}')
        return None
    schedule, edoc = result

    if (schedule == None):
        return None

    if (edoc == False):
        if (course.get('code') not in db_courses_semester_codes):
            return None
        schedule = create_semester_schedule(schedule, semester)

    # Add course_id to schedule
    for event in schedule:
        event['course_id'] = course['_id']

    return schedule

def process_course_schedules_start(args):
    return process_course_schedules(*args)

    
def find_courses_schedules(db):

    semester = get_current_or_next_semester(db)
    semester_courses_ids = find_semester_courses_ids(db, semester)

    current_year = get_current_or_next_semester(db, 'year')
    current_year_courses_ids = find_semester_courses_ids(db, current_year)

    print('Getting courses from DB...')
    db_courses_semester = list(db.courses.find({
        '_id': {
            '$in': semester_courses_ids
        }
    }))
    db_courses_semester_codes = [course.get('code') for course in db_courses_semester]

    db_courses_year = list(db.courses.find({
        '_id': {
            '$in': list(set(current_year_courses_ids) - set(semester_courses_ids))
        }
    }))
    db_courses_year_codes = [course.get('code') for course in db_courses_year]

    db_courses = db_courses_semester + db_courses_year

    print(f'- {len(db_courses)} courses found')

    db_schedules = list(db.course_schedules.find({
        'available': True
    }))

    schedules = []
    num_processes = multiprocessing.cpu_count()
    with multiprocessing.Pool(num_processes) as pool:
        processed_schedules = tqdm(pool.imap(process_course_schedules_start, [(course, db_courses_semester_codes, semester) for course in db_courses]), total=len(db_courses), desc="Processing courses schedules")

        for schedule in processed_schedules:
            if (schedule != None):
                schedules += schedule

    return schedules


### LIST ALL ROOMS ###
def list_rooms(schedules):

    rooms = []
    for schedule in schedules:
        if (schedule.get('rooms') == None):
            continue

        schedule_rooms = schedule.get('rooms')

        for room in schedule_rooms:
            if (room not in rooms):
                rooms.append(room)
                
    return rooms



### LIST ALL PLAN ROOMS ###
def list_plan_rooms():
    '''
        List all the rooms objects (name, type) on the plan.epfl.ch website
        Output:
            - rooms: a list of rooms
    '''

    def list_level_rooms(low, up, floor, max=1000):
        '''
            List all the XML rooms objects in a level
            Input:
                - low: the lower left corner of the level
                - up: the upper right corner of the level
                - floor: the floor of the level
                - max: the maximum number of rooms to return
                Output:
                    - rooms: a list of XML rooms
        '''
        low1, low2 = low
        up1, up2 = up
        request_url = f"https://plan.epfl.ch/mapserv_proxy?ogcserver=source+for+image%2Fpng&cache_version=9fe661ce469e4692b9e402b22d8cb420&floor={floor}"
        xml = f'<GetFeature xmlns="http://www.opengis.net/wfs" service="WFS" version="1.1.0" outputFormat="GML3" maxFeatures="{max}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.1.0/wfs.xsd"><Query typeName="feature:batiments_wmsquery" srsName="EPSG:2056" xmlns:feature="http://mapserver.gis.umn.edu/mapserver"><Filter xmlns="http://www.opengis.net/ogc"><BBOX><PropertyName>the_geom</PropertyName><Envelope xmlns="http://www.opengis.net/gml" srsName="EPSG:2056"><lowerCorner>{low1} {low2}</lowerCorner><upperCorner>{up1} {up2}</upperCorner></Envelope></BBOX></Filter></Query></GetFeature>'

        r = requests.post(request_url, data=xml)
        level_xml = BeautifulSoup(r.text, 'xml')
        if (level_xml.find('gml:Null') != None):
            return None
        return level_xml.findAll('gml:featureMember')

    def list_all_levels_rooms():
        '''
            List all the XML rooms objects in ALL levels
            Output:
                - rooms: a list of XML rooms
        '''
        rooms_xml = {}
        for level in tqdm(range(-3, 8)):
            level_rooms_xml = list_level_rooms((2533565.4081416847, 1152107.9784703811), (2532680.590, 1152904.181), level, max=5000)
            if (level_rooms_xml and len(level_rooms_xml) > 0):
                rooms_xml[level] = level_rooms_xml
        return rooms_xml

    def compute_coordinates(coordinates_string):
        coordinates_split = coordinates_string.split()
        coordinates = [(float(coordinates_split[i]), float(coordinates_split[i+1])) for i in range(0, len(coordinates_split), 2)]

        # Compute center coordinates
        xs, ys = zip(*coordinates)
        center_x, center_y = (np.mean(xs), np.mean(ys))

        # Transform coordinates from MN95 (epsg:2056) to WGS84 (epsg:4326)
        transformer = pyproj_Transformer.from_crs("epsg:2056", "epsg:4326")

        return transformer.transform(center_x, center_y)

    def parse_room(room_xml):
        '''
            Parse a XML room object
            Input:
                - room_xml: the XML room object
            Output:
                - room: the parsed room object (name, type, coordinates, link)
        '''
        room_name = BeautifulSoup(room_xml.find('ms:room_abr_link').text, 'html.parser').find('div', class_="room").text.replace(" ", "")
        room_type = room_xml.find('ms:room_uti_a').text
        room_link = BeautifulSoup(room_xml.find('ms:room_abr_link').text, 'html.parser').find('button', class_="clipboard").attrs['data-clipboard-text']
        room_capacity = room_xml.find('ms:room_place').text
        if (room_capacity and room_capacity != ''):
            room_capacity = int(room_capacity)
        else:
            room_capacity = None
        room_coordinates_string = room_xml.find('gml:posList').text
        room_coordinates = compute_coordinates(room_coordinates_string)
        

        return { 'name': room_name, 'type': room_type, 'coordinates': room_coordinates, 'link': room_link, 'capacity': room_capacity }

    def parse_all_rooms(rooms_xml):
        '''
            Parse all XML rooms objects
            Input:
                - rooms_xml: object of XML rooms objects (level: rooms_xml)
            Output:
                - rooms: a list of parsed rooms objects (name, type)
        '''
        rooms_parsed = []
        for level, level_rooms_xml in tqdm(rooms_xml.items(), total=len(rooms_xml.keys())):
            for room_xml in tqdm(level_rooms_xml, total=len(level_rooms_xml), leave=False):
                room = parse_room(room_xml)
                if (room == None):
                    continue
                if (room not in rooms_parsed):
                    room['level'] = level
                    rooms_parsed.append(room)
        return rooms_parsed
    
    rooms_xml = list_all_levels_rooms()

    print("Parsing rooms...")
    rooms = parse_all_rooms(rooms_xml)

    return rooms


### CREATE ROOMS ###
def create_rooms(db, schedules=[], rooms_names=[], update=False):
    '''
        Create schedules in the database
        Input:
            - db: the database
            - schedules: a list of schedules
    '''

    if (update == True):
        rooms_names = []

    elif (len(rooms_names) == 0 or type(rooms_names) != list):
        if (len(schedules) == 0 or type(schedules) != list):
            print("No schedules to create")
            return

        # List all rooms in the schedules
        rooms_names = list_rooms(schedules)
    

    # Find all rooms on plan.epfl.ch
    print("Getting rooms from plan.epfl.ch")
    plan_rooms = list_plan_rooms()
    plan_rooms_names = [plan_room.get("name") for plan_room in plan_rooms]
    print(f"Found {len(plan_rooms_names)} rooms on plan.epfl.ch")


    # List all rooms in the database
    print("Getting rooms from database")
    db_rooms = list(db.rooms.find({
        "available": True
    }))
    print(f"Found {len(db_rooms)} rooms in database")

    # Update the rooms type, coordinates and link in the database if necessary
    print("Updating rooms in database")
    for db_room in tqdm(db_rooms):
        db_room_name = db_room.get("name")
        if (db_room_name not in plan_rooms_names):
            # If the room is not on plan.epfl.ch, ignore it
            print(f"Room {db_room_name} not found on plan.epfl.ch")
            continue
        db_room_type = db_room.get("type")
        db_room_capacity = db_room.get("capacity")
        db_room_level = db_room.get("level", None)
        db_room_link = db_room.get("link")
        db_room_coordinates = db_room.get("coordinates")

        # Find the room in plan data
        plan_room = [plan_room for plan_room in plan_rooms if plan_room.get("name") == db_room_name][0]
        plan_room_type = plan_room.get("type")
        plan_room_link = plan_room.get("link")
        plan_room_coordinates = plan_room.get("coordinates")
        plan_room_capacity = plan_room.get("capacity")
        plan_room_level = plan_room.get("level", None)

        # Update it if necessary
        if (db_room_type != plan_room_type or \
            db_room_link != plan_room_link or \
            db_room_coordinates != plan_room_coordinates or \
            db_room_capacity != plan_room_capacity or \
            (db_room_level != plan_room_level and plan_room_level) ):

            updated_room = {
                "name": db_room_name,
                "type": plan_room_type,
                "link": plan_room_link,
                "coordinates": plan_room_coordinates
            }

            if (plan_room_capacity != None and isinstance(plan_room_capacity, int)):
                updated_room["capacity"] = plan_room_capacity
            
            if (plan_room_level != None and isinstance(plan_room_level, int)):
                updated_room["level"] = plan_room_level
        
            db.rooms.update_one({
                "name": db_room_name
            }, { "$set": updated_room})

    # List rooms to create
    db_rooms_names = [db_room.get("name") for db_room in db_rooms]
    new_rooms_names = [room_name for room_name in rooms_names if room_name not in db_rooms_names]

    # Create the rooms that are not in the database
    print("Filtering rooms to create")
    new_rooms = []
    for room_name in tqdm(new_rooms_names):
        plan_room = [plan_room for plan_room in plan_rooms if plan_room.get("name") == room_name] 

        room_link = None
        room_coordinates = None
        room_type = "unknown"
        room_capacity = 0
        room_level = 0

        # building is the characters before the first number
        room_building = re.split(r'\d', room_name)[0]
        # replace underscores or hyphens with spaces
        room_building = re.sub(r'[-_]', ' ', room_building)
        
        if (plan_room is not None and len(plan_room) != 0):
            room_type = plan_room[0].get("type", "unknown")
            room_link = plan_room[0].get("link", None)
            room_coordinates = plan_room[0].get("coordinates", None)
            room_capacity = plan_room[0].get("capacity", None)
            room_level = plan_room[0].get("level", None)
        
        new_rooms.append({
            "name": room_name,
            "type": room_type,
            "available": True,
            "link": room_link,
            "coordinates": room_coordinates,
            "building": room_building,
            "level": room_level,
            "capacity": room_capacity
        })

    if (len(new_rooms) == 0):
        print("No new rooms to create")
        return

    print(f"Inserting {len(new_rooms)} new rooms in database")
    try:
        db.rooms.insert_many(new_rooms)
    except Exception as e:
        print(e)

    return

def update_schedules(db, schedules):
    db_rooms = list(db.rooms.find({
        'available': True
    }))

    db_semester = get_current_or_next_semester(db)
    db_year_semester = get_current_or_next_semester(db, 'year')

    # Find studyplans in the current semester
    db_studyplans = list(db.studyplans.find({
        'available': True,
        'semester_id': {
            '$in': [db_semester['_id'], db_year_semester['_id']]
        }
    }))

    # Find planned_in in the current semester
    db_planned_in = list(db.planned_in.find({
        'available': True,
        'studyplan_id': {
            '$in': [studyplan['_id'] for studyplan in db_studyplans]
        }
    }))

    # remove MAN courses from db_planned_in
    man_courses_ids = get_man_courses_ids(db)
    db_planned_in_ids = [planned_in['course_id'] for planned_in in db_planned_in]
    db_planned_in_ids = [course_id for course_id in db_planned_in_ids if course_id not in man_courses_ids]

    # Find schedules with course in the studyplans
    print('Getting schedules from DB...')
    db_schedules = list(db.course_schedules.find({
        'available': True,
        'course_id': {
                '$in': db_planned_in_ids,      
        }
    }))
    print(f'- {len(db_schedules)} schedules found')

    incoming_schedules = schedules.copy()
    
    print(f'Filtering {len(incoming_schedules)} schedules...')
    new_schedules = []
    for incoming_schedule in tqdm(incoming_schedules, total=len(incoming_schedules)):
        found = False
        for db_schedule in db_schedules:
            if (
                db_schedule.get('course_id') == incoming_schedule.get('course_id') and
                db_schedule.get('start_datetime') == incoming_schedule.get('start_datetime') and
                db_schedule.get('end_datetime') == incoming_schedule.get('end_datetime') and
                db_schedule.get('label') == incoming_schedule.get('label')
            ):
                found = True
                db_schedules.remove(db_schedule)
                break

        if (found == True):
            continue

        new_schedules.append({
            'course_id': incoming_schedule.get('course_id'),
            'start_datetime': incoming_schedule.get('start_datetime'),
            'end_datetime': incoming_schedule.get('end_datetime'),
            'label': incoming_schedule.get('label'),
            'available': True
        })

    # delete remaining db_schedules
    print('Deleting schedules not in incoming schedules...')
    try:
        db.course_schedules.update_many({
            '_id': {
                '$in': [db_schedule.get('_id') for db_schedule in db_schedules]
            }
        }, {
            '$set': {
                'available': False
            }
        })
        print(f'- {len(db_schedules)} schedules deleted')
    except Exception as e:
        print(e)

    # insert new schedules
    if (len(new_schedules) == 0):
        print('No new schedules to create')
        return

    try:
        print(f'Creating {len(new_schedules)} new schedules...')
        db.course_schedules.insert_many(new_schedules)
        print(f'- {len(new_schedules)} schedules created')
    except Exception as e:
        print(e)

def get_man_courses_ids(db):
    semester = get_current_or_next_semester(db, 'spring')

    man_units = list(db.units.find({
        'section': 'MAN'
    }))

    man_studyplans = list(db.studyplans.find({
        'unit_id': {
            '$in': [unit['_id'] for unit in man_units],
        },
        'semester_id': semester['_id']
    }))

    man_planned_in = list(db.planned_in.find({
        'studyplan_id': {
            '$in': [studyplan['_id'] for studyplan in man_studyplans]
        }
    }))

    return list(set([planned['course_id'] for planned in man_planned_in]))

def create_courses_bookings(db, schedules):
    db_rooms = list(db.rooms.find({
        'available': True
    }))

    db_schedules = list(db.course_schedules.find({
        'available': True
    }))

    print('Getting DB bookings...')
    db_bookings = list(db.course_bookings.find({
        'available': True
    }))

    db_unavailable_bookings = list(db.course_bookings.find({
        'available': False
    }))
    print(f'- {len(db_bookings)} bookings found in DB')

    print('Filtering bookings....')
    new_bookings_candidates = []
    bookings_to_remove = []
    for schedule in tqdm(schedules, total=len(schedules)):
        db_schedule = None
        for db_item in db_schedules:
            if (
                db_item.get('course_id') == schedule.get('course_id') and
                db_item.get('start_datetime') == schedule.get('start_datetime') and
                db_item.get('end_datetime') == schedule.get('end_datetime') and
                db_item.get('label') == schedule.get('label')
            ):
                db_schedule = db_item
                break

        if (db_schedule == None):
            continue
        
            
        schedule_rooms = []
        for room in schedule['rooms']:
            db_room = list(filter(lambda db_room: db_room['name'] == room, db_rooms))

            if (db_room == None or len(db_room) == 0):
                continue
            db_room = db_room[0]

            schedule_rooms.append(db_room)

        # check for rooms in db_rooms not in schedule['rooms'] (to remove)
        db_schedule_bookings = list(filter(lambda db_booking: db_booking.get('schedule_id') == db_schedule['_id'], db_bookings))
        for db_schedule_booking in db_schedule_bookings:
            room_id = db_schedule_booking.get('room_id')
            found = False
            for db_room in schedule_rooms:
                if (room_id == db_room['_id']):
                    found = True
                    break
                
            if (found == False):
                bookings_to_remove.append(db_schedule_booking)

        for db_room in schedule_rooms:
            # Check if booking already exists
            found = False
            for db_booking in db_bookings:
                if (
                    db_booking.get('schedule_id') == db_schedule['_id'] and
                    db_booking.get('room_id') == db_room['_id']
                ):
                    found = True

                    break
            
            if (found == True):
                continue
            
            booking = {
                'schedule_id': db_schedule['_id'],
                'room_id': db_room['_id'],
                'available': True
            }

            new_bookings_candidates.append(booking)

    print(f' - {len(bookings_to_remove)} bookings changed (not the schedule) (to remove)')

    # remove bookings with a schedule_id not in db_schedules
    print('Removing bookings without schedule...')
    try:
        # find bookings without a schedule_id in db_schedules
        bookings_without_schedule = []
        schedules_ids = [schedule['_id'] for schedule in db_schedules]
        for booking in tqdm(db_bookings, total=len(db_bookings)):
            if (booking.get('schedule_id') not in schedules_ids):
                bookings_without_schedule.append(booking)

        if (len(bookings_without_schedule) == 0 and len(bookings_to_remove) == 0):
            print('- No bookings to remove')
        else:
            db.course_bookings.update_many({
                '_id': {
                    '$in': [booking.get('_id') for booking in bookings_without_schedule + bookings_to_remove]
                }
            }, {
                '$set': {
                    'available': False
                }
            })
            print(f'- {len(bookings_without_schedule + bookings_to_remove)} bookings removed')
        
    except Exception as e:
        print(e)

    # check if new booking is in db_unavailable_bookings and set it to available
    print('Checking if new bookings are in unavailable bookings...')
    to_make_available = []
    to_create = []
    for new_booking in tqdm(new_bookings_candidates, total=len(new_bookings_candidates)):
        found = False
        for unavailable_booking in db_unavailable_bookings:
            if (
                new_booking.get('schedule_id') == unavailable_booking.get('schedule_id') and
                new_booking.get('room_id') == unavailable_booking.get('room_id')
            ):
                found = True
                to_make_available.append(unavailable_booking)
                break

        if (found == False):
            to_create.append(new_booking)

    if (len(to_make_available) == 0):
        print('- No bookings to (re)make available')
    else:
        db.course_bookings.update_many({
            '_id': {
                '$in': [booking.get('_id') for booking in to_make_available]
            }
        }, {
            '$set': {
                'available': True
            }
        })
        print(f'- {len(to_make_available)} bookings (re)made available')
    
    if (len(to_create) == 0):
        print('No bookings to create')
        return

    # insert new bookings
    try:
        print(f'Creating {len(to_create)} new bookings...')
        db.course_bookings.insert_many(to_create)
        print(f'- {len(to_create)} bookings created')
    except Exception as e:
        print(e)



### MEETINGS ###

def query_force(query, max_retry=50):
    for _ in range(max_retry):
        response = query()
        if not response:
            continue
        if response.status_code == 200:
            return response
    return None


def parse_events(response):
    if not response or not response.text:
        print('No response')
        return []

    events_line = response.text.split('0|')[1]

    print(response.text)

    if not events_line:
        print('No events line')
        return []

    # Do a little bit of parsing
    room_occupancy = (events_line.replace(';', '')
                                 .replace('\\"', '')
                                 .replace('<br>', '')
                                 .replace('ISA - ', '')
                                 .replace('\\', ''))
    
    parsed_room_occupancy = json.loads(room_occupancy)['Events']

    events_tags = ['Evénements', 'Réservation académique', 'Réservation ponctuelle']
    
    # Filter events based on the specified tags
    filtered_events = [event for event in parsed_room_occupancy if event['Text'] in events_tags]

    # Keep only the relevant fields
    filtered_events = [{k: event[k] for k in ['Text', 'Start', 'End']} for event in filtered_events]

    return filtered_events

def parse_room_events(room_name, start_date, end_date):
    asp_net_cookie = get_asp_net_cookie(room_name)
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        'Cookie': f'ASP.NET_SessionId={asp_net_cookie}; petitpois=dismiss;',
        'Origin': 'https://ewa.epfl.ch',
        'Referer': f'https://ewa.epfl.ch/room/Default.aspx?room={room_name}',
    }
    
    response = query_force(lambda: query_room(room_name, start_date, end_date, headers), max_retry=200)
  
    if not response:
        print(f'No response for {room_name}')
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
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
        'Cookie': f'ASP.NET_SessionId={asp_net_cookie}; petitpois=dismiss;',
        'Origin': 'https://ewa.epfl.ch',
        'Referer': f'https://ewa.epfl.ch/room/Default.aspx?room={room_name}',
    }
    
    response = query_force(lambda: query_room(room_name, start_date, end_date, headers), max_retry=100)
    if not response:
        print(f'No response for {room_name}')
        return []
    return parse_events(response)

def get_asp_net_cookie(room_name):
    response = query_force(lambda: requests.get(f'https://ewa.epfl.ch/room/Default.aspx?room={room_name}'), max_retry=100)

    if not response:
        print('No response')
        return None
    if response.status_code == 200:
        cookies = response.cookies
        return cookies.get('ASP.NET_SessionId', None)
    return None

def query_room(room_name, start_date, end_date, headers):

    # generate columns values for the request (for the 7 days starting from start_date)
    columns = []
    start_datetime = datetime.strptime(start_date, '%Y-%m-%dT%H:%M:%S')
    for i in range(7):
        day = start_datetime + timedelta(days=i)
        columns.append({
            "Value": None,
            "Name": day.strftime('%d.%m.%Y'),
            "ToolTip": None,
            "Date": day.strftime('%Y-%m-%dT00:00:00'),
            "Children": []
        })

    callback_params = {
        "action": "Command",
        "parameters": {
            "command": "navigate"
        },
        "data": {
            "start": start_date,
            "end": end_date,
            "days": 7
        },
        "header": {
            "control": "dpc",
            "id": "ContentPlaceHolder1_DayPilotCalendar1",
            "clientState": {},
            "columns": columns,
            "days": 7,
            "startDate": start_date,
            "cellDuration": 30,
            "heightSpec": "BusinessHours",
            "businessBeginsHour": 7,
            "businessEndsHour": 20,
            "viewType": "Days",
            "dayBeginsHour": 0,
            "dayEndsHour": 0,
            "headerLevels": 1,
            "backColor": "White",
            "nonBusinessBackColor": "White",
            "eventHeaderVisible": True,
            "timeFormat": "Clock12Hours",
            "showAllDayEvents": True,
            "tagFields": ["name", "id"],
            "hourNameBackColor": "#F3F3F9",
            "hourFontFamily": "Tahoma,Verdana,Sans-serif",
            "hourFontSize": "16pt",
            "hourFontColor": "#42658C",
            "selected": "",
            "hashes": {
                "callBack": "OV+dLKlTRpwauhSy/FtI1aLjgoc=",
                "columns": "IhqLqz4fVg5t3JL4XXO3ZfZvJRA=",
                "events": "NqagU2+lBsSSGcEgjzHvWAy3Rds=",
                "colors": "3caslJYaCfbLdelD4+2YHVvrvn8=",
                "hours": "K+iMpCQsduglOsYkdIUQZQMtaDM=",
                "corner": "0XBQYL2rjFh+nn9As5pzf4+hWqg="
            }
        }
    }

    data = {
        'MIME Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        '__EVENTTARGET': '',
        '__EVENTARGUMENT': '',
        '__VIEWSTATE': '/wEPDwUKMTM5ODM2NTk2OQ9kFgJmD2QWAgIFD2QWBAIBD2QWBgIBDw8WAh4EVGV4dAUEQkMwMWRkAgMPDxYCHgtfIURhdGFCb3VuZGdkZAIFDw8WBh4JVGFnRmllbGRzFQIEbmFtZQJpZB8BZx4JU3RhcnREYXRlBgCAPrfdMNwIZGQCAw8PFgIfAAUEMjAyNGRkZBcDZBZ3ATHldACedIUzjN5kMtI2cxXWLlr1+Lr9oP0L',
        '__VIEWSTATEGENERATOR': 'CC8E5E3B',
        '__CALLBACKID': 'ctl00$ContentPlaceHolder1$DayPilotCalendar1',
        '__CALLBACKPARAM': """JSON{"action":"Command","parameters":{"command":"navigate"},"data":{"start":"2024-02-26T00:00:00","end":"2024-03-04T00:00:00","days":7},"header":{"control":"dpc","id":"ContentPlaceHolder1_DayPilotCalendar1","clientState":{},"columns":[{"Value":null,"Name":"19.02.2024","ToolTip":null,"Date":"2024-02-19T00:00:00","Children":[]},{"Value":null,"Name":"20.02.2024","ToolTip":null,"Date":"2024-02-20T00:00:00","Children":[]},{"Value":null,"Name":"21.02.2024","ToolTip":null,"Date":"2024-02-21T00:00:00","Children":[]},{"Value":null,"Name":"22.02.2024","ToolTip":null,"Date":"2024-02-22T00:00:00","Children":[]},{"Value":null,"Name":"23.02.2024","ToolTip":null,"Date":"2024-02-23T00:00:00","Children":[]},{"Value":null,"Name":"24.02.2024","ToolTip":null,"Date":"2024-02-24T00:00:00","Children":[]},{"Value":null,"Name":"25.02.2024","ToolTip":null,"Date":"2024-02-25T00:00:00","Children":[]}],"days":7,"startDate":"2024-02-19T00:00:00","cellDuration":30,"heightSpec":"BusinessHours","businessBeginsHour":7,"businessEndsHour":20,"viewType":"Days","dayBeginsHour":0,"dayEndsHour":0,"headerLevels":1,"backColor":"White","nonBusinessBackColor":"White","eventHeaderVisible":true,"timeFormat":"Clock12Hours","showAllDayEvents":true,"tagFields":["name","id"],"hourNameBackColor":"#F3F3F9","hourFontFamily":"Tahoma,Verdana,Sans-serif","hourFontSize":"16pt","hourFontColor":"#42658C","selected":"","hashes":{"callBack":"PFfUEJ3wrfDg2Gfp/oBSL89g8Kc=","columns":"bzP1mnnwN+umsglYKroAi3JEFP4=","events":"xVFNXcegBTUqJf6sHwhHjX6e88g=","colors":"u6JkuOn4xmGT35AnGNQ0dmPOOqk=","hours":"K+iMpCQsduglOsYkdIUQZQMtaDM=","corner":"0XBQYL2rjFh+nn9As5pzf4+hWqg="}}}""",
    }

    response = requests.post('https://ewa.epfl.ch/room/Default.aspx', headers=headers, data=data)

    return response


def populate_events_room(db, parsed_events):
    db_rooms = list(db.rooms.find({
        'available': True
    }))

    new_events = []
    for event in tqdm(parsed_events, total=len(parsed_events)):
        room_name = event['room']
        if room_name in MAP_ROOMS:
            room_name = MAP_ROOMS[room_name]

        if isinstance(room_name, list):
            for room_name_sub in room_name:
                room = list(filter(lambda x: x['name'] == room_name_sub, db_rooms))
                if len(room) == 0:
                    print(f"Room {room_name_sub} not found in db")
                    continue
                room = room[0]
                new_event = event
                new_event['room'] = room['_id']
                new_events.append(new_event)
        else:
            room = list(filter(lambda x: x['name'] == room_name, db_rooms))
            if len(room) == 0:
                print(f"Room {room_name} not found in db")
                continue
            room = room[0]
            new_event = event
            new_event['room'] = room['_id']
            new_events.append(new_event)

    return new_events

def create_event_bookings(db, parsed_events):
    db_event_bookings = list(db.event_bookings.find({
        'available': True
    }))
    new_bookings = []
    for event in tqdm(parsed_events, total=len(parsed_events)):
        found = False
        for db_booking in db_event_bookings:
            if event['room'] == db_booking['room_id'] and \
                event['start_datetime'] == db_booking['start_datetime'] and \
                event['end_datetime'] == db_booking['end_datetime'] and \
                event['name'] == db_booking['name']:
                found = True
                break

        if not found:
            new_booking = {
                'room_id': event['room'],
                'start_datetime': event['start_datetime'],
                'end_datetime': event['end_datetime'],
                'name': event['name'],
                'label': event['label'],
                'available': True
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
    
    current_date = datetime.strptime(start_date, '%Y-%m-%dT%H:%M:%S')

    while current_date <= datetime.strptime(end_date, '%Y-%m-%dT%H:%M:%S'):
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
            start_date = date_range[0].strftime('%Y-%m-%dT%H:%M:%S')
            end_date = date_range[1].strftime('%Y-%m-%dT%H:%M:%S')
            room_events = parse_room_events(room_name, start_date, end_date)
            for event in room_events:
                new_event = {
                    'room': room_name,
                    'start_datetime': datetime.strptime(event['Start'], '%Y-%m-%dT%H:%M:%S'),
                    'end_datetime': datetime.strptime(event['End'], '%Y-%m-%dT%H:%M:%S'),
                    'name': event['Text'],
                    'label': 'event',
                    'available': True
                }
                parsed_events.append(new_event)

    return parsed_events

def parse_all_rooms_next_week(rooms_names):
    parsed_events = []
    for room_name in tqdm(rooms_names, total=len(rooms_names)):
        room_events = parse_next_week(room_name)
        for event in room_events:
            new_event = {
                'room': room_name,
                'start_datetime': datetime.strptime(event['Start'], '%Y-%m-%dT%H:%M:%S'),
                'end_datetime': datetime.strptime(event['End'], '%Y-%m-%dT%H:%M:%S'),
                'name': event['Text'],
                'label': 'event',
                'available': True
            }
            parsed_events.append(new_event)

    return parsed_events


