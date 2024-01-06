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
    
    # Filter duplicates
    courses_url = list(set(courses_url))

    return courses_url

### PARSE COURSE ###
def parse_course(url):
    page = requests.get(url)
    if (page.status_code == 404):
        print(f'404: {url}')
        return None
        
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
    db_semesters = list(db.semesters.find({
        'available': True
    }))

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

    db_semester = get_current_or_next_semester(db)
    db_semester_year = get_current_or_next_semester(db, 'year')

    db_studyplans = list(db.studyplans.find({
        'available': True,
        'semester_id': {
            '$in': [db_semester['_id'], db_semester_year['_id']]
        }
    }))

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
            studyplan_semester_db = list(filter(lambda semester: semester_type == semester.get('type'), [db_semester, db_semester_year]))
            if (studyplan_semester_db == None or len(studyplan_semester_db) == 0):
                continue
            studyplan_semester_db = studyplan_semester_db[0]

            # Find studyplan in db
            studyplan_db = list(filter(lambda plan: plan['unit_id'] == studyplan_unit['_id'] and plan['semester_id'] == studyplan_semester_db['_id'], db_studyplans))
            if (studyplan_db == None or len(studyplan_db) == 0):
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
            "$gte": today
        },
        "end_date": {
            "$lte": today
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

def find_semester_courses_ids(db):
    semester = get_current_or_next_semester(db)
    current_year_semester = get_current_or_next_semester(db, 'year')

    if (semester == None):
        return

    print('Getting studyplans from DB...')
    filtered_studyplans = list(db.studyplans.find({
        'available': True,
        'semester_id': {
            '$in': [semester['_id'], current_year_semester['_id']]
        }
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
    

def find_courses_schedules(db):

    semester = get_current_or_next_semester(db)
    semester_courses_ids = find_semester_courses_ids(db)

    print('Getting courses from DB...')
    db_courses = list(db.courses.find({
        '_id': {
            '$in': semester_courses_ids
        }
    }))
    print(f'- {len(db_courses)} courses found')

    db_schedules = list(db.course_schedules.find({
        'available': True
    }))

    schedules = []

    for course in tqdm(db_courses, total=len(db_courses)):
        course_edu_url = course.get('edu_url')
        if (course_edu_url == None):
            continue

        schedule, edoc = get_course_schedule(course_edu_url)

        if (schedule == None):
            continue

        if (edoc == False):
            schedule = create_semester_schedule(schedule, semester)

        # Add course_id to schedule
        for event in schedule:
            event['course_id'] = course['_id']

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
        rooms_xml = []
        for level in tqdm(range(-3, 8)):
            level_rooms_xml = list_level_rooms((2533565.4081416847, 1152107.9784703811), (2532650.4135850836, 1152685.3502971812), level, max=5000)
            if (level_rooms_xml and len(level_rooms_xml) > 0):
                rooms_xml += level_rooms_xml
        return rooms_xml

    def parse_room(room_xml):
        '''
            Parse a XML room object
            Input:
                - room_xml: the XML room object
            Output:
                - room: the parsed room object (name, type)
        '''
        room_name = BeautifulSoup(room_xml.find('ms:room_abr_link').text, 'html.parser').find('div', class_="room").text.replace(" ", "")
        room_type = room_xml.find('ms:room_uti_a').text
        return { 'name': room_name, 'type': room_type }
    
    def parse_all_rooms(rooms_xml):
        '''
            Parse all XML rooms objects
            Input:
                - rooms_xml: the XML rooms objects
            Output:
                - rooms: a list of parsed rooms objects (name, type)
        '''
        rooms_parsed = []
        for room_xml in rooms_xml:
            room = parse_room(room_xml)
            if (room == None):
                continue
            if (room not in rooms_parsed):
                rooms_parsed.append(room)
        return rooms_parsed
    
    rooms_xml = list_all_levels_rooms()
    rooms = parse_all_rooms(rooms_xml)

    return rooms


### CREATE ROOMS ###
def create_rooms(db, schedules):
    '''
        Create schedules in the database
        Input:
            - db: the database
            - schedules: a list of schedules
    '''

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

    # Update the type of the rooms in the database if necessary
    print("Updating rooms in database")
    for db_room in tqdm(db_rooms):
        db_room_name = db_room.get("name")
        db_room_type = db_room.get("type")
        if (db_room_name not in plan_rooms_names):
            # If the room is not on plan.epfl.ch, ignore it
            print(f"Room {db_room_name} not found on plan.epfl.ch")
            continue
        plan_room = [plan_room for plan_room in plan_rooms if plan_room.get("name") == db_room_name][0]
        plan_room_type = plan_room.get("type")
        if (db_room_type != plan_room_type):
            db.rooms.update_one({"name": db_room_name}, { "$set": { "type": plan_room_type }})

    # List rooms to create
    db_rooms_names = [db_room.get("name") for db_room in db_rooms]
    new_rooms_names = [room_name for room_name in rooms_names if room_name not in db_rooms_names]

    # Create the rooms that are not in the database
    print("Filtering rooms to create")
    new_rooms = []
    for room_name in tqdm(new_rooms_names):
        plan_room = [plan_room for plan_room in plan_rooms if plan_room.get("name") == room_name] 
        if (plan_room is None):
            room_type = "unknown"
        elif (len(plan_room) == 0):
            room_type = "unknown"
        else:
            room_type = plan_room[0].get("type", "unknown")
        
        new_rooms.append({"name": room_name, "type": room_type, "available": True})

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

    # Find schedules with course in the studyplans
    print('Getting schedules from DB...')
    db_schedules = list(db.course_schedules.find({
        'available': True,
        'course_id': {
            '$in': [planned_in['course_id'] for planned_in in db_planned_in]
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
        db.schedules.update_many({
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
    print(f'- {len(db_bookings)} bookings found in DB')

    print('Filtering bookings....')
    new_bookings = []
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

        for room in schedule['rooms']:
            db_room = list(filter(lambda db_room: db_room['name'] == room, db_rooms))

            if (db_room == None or len(db_room) == 0):
                continue
            db_room = db_room[0]

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

            new_bookings.append(booking)

    # remove bookings with a schedule_id not in db_schedules
    print('Removing bookings without schedule...')
    try:
        # find bookings without a schedule_id in db_schedules
        bookings_without_schedule = []
        schedules_ids = [schedule['_id'] for schedule in db_schedules]
        for booking in tqdm(db_bookings, total=len(db_bookings)):
            if (booking.get('schedule_id') not in schedules_ids):
                bookings_without_schedule.append(booking)

        if (len(bookings_without_schedule) == 0):
            print('- No bookings to remove')
        else:
            db.course_bookings.update_many({
                '_id': {
                    '$in': [booking.get('_id') for booking in bookings_without_schedule]
                }
            }, {
                '$set': {
                    'available': False
                }
            })
            print(f'- {len(bookings_without_schedule)} bookings removed')
        
    except Exception as e:
        print(e)

    
    if (len(new_bookings) == 0):
        print('No bookings to create')
        return

    # insert new bookings
    try:
        print(f'Creating {len(new_bookings)} new bookings...')
        db.course_bookings.insert_many(new_bookings)
        print(f'- {len(new_bookings)} bookings created')
    except Exception as e:
        print(e)