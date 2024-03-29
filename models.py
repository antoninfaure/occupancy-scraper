room_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "type", "available"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "must be a string and is required"
            },
            "type": {
                "bsonType": "string",
                "description": "must be a string and is required",
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            },
            "capacity": {
                "bsonType": "int",
                "description": "must be an integer"
            },
            'level': {
                "bsonType": "int",
                "description": "must be an integer"
            },
            "building": {
                "bsonType": "string",
                "description": "must be a string"
            },
        }
    }
}

teacher_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "people_url", "available"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "must be a string and is required"
            },
            "people_url": {
                "bsonType": "string",
                "description": "must be a string and is required",
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            }
        }
    }
}

course_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "code", "credits", "available"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "must be a string and is required"
            },
            "code": {
                "bsonType": "string",
                "description": "must be a string and is required",
            },
            "credits": {
                "bsonType": "int",
                "description": "must be an integer and is required"
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            },
            "edu_url": {
                "bsonType": "string",
                "description": "must be a string"
            },
            "language": {
                "bsonType": "string",
                "description": "must be a string"
            },
            "teachers": {
                "bsonType": "array",
                "description": "must be an array of objects"
            }
        }
    }
}

course_schedule_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["course_id", "start_datetime", "end_datetime", "available", "label"],
        "properties": {
            "course_id": {
                "bsonType": "objectId",
                "description": "must be an objectId and is required"
            },
            "start_datetime": {
                "bsonType": "date",
                "description": "must be a date and is required"
            },
            "end_datetime": {
                "bsonType": "date",
                "description": "must be a date and is required"
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            },
            "label": {
                "bsonType": "string",
                "description": "must be a string and is required"
            },
        }
    }
}

event_booking_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["start_datetime", "end_datetime", "room_id", "available", "label", "name"],
        "properties": {
            "start_datetime": {
                "bsonType": "date",
                "description": "must be a date and is required"
            },
            "end_datetime": {
                "bsonType": "date",
                "description": "must be a date and is required"
            },
            "room_id": {
                "bsonType": "objectId",
                "description": "must be an objectId and is required"
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            },
            "label": {
                "bsonType": "string",
                "description": "must be a string and is required"
            },
            "description": {
                "bsonType": "string",
                "description": "must be a string"
            },
            "name": {
                "bsonType": "string",
                "description": "must be a string"
            }
        }
    }
}

course_booking_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["schedule_id", "room_id", "available"],
        "properties": {
            "schedule_id": {
                "bsonType": "objectId",
                "description": "must be an objectId and is required"
            },
            "room_id": {
                "bsonType": "objectId",
                "description": "must be an objectId and is required"
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            }
        }
    }
}

studyplan_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["unit_id", "semester_id", "available"],
        "properties": {
            "unit_id": {
                "bsonType": "objectId",
                "description": "must be an objectId and is required"
            },
            "semester_id": {
                "bsonType": "objectId",
                "description": "must be an objectId  and is required"
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            }
        }
    }
}

planned_in_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["studyplan_id", "course_id", "available"],
        "properties": {
            "studyplan_id": {
                "bsonType": "objectId",
                "description": "must be an objectId and is required"
            },
            "course_id": {
                "bsonType": "objectId",
                "description": "must be an objectId and is required"
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            }
        }
    }
}

semester_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "start_date", "end_date", "available", "type"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "must be a string and is required"
            },
            "type": {
                "enum": ["fall", "spring", "year"],
                "description": "must be a string and is required"
            },
            "start_date": {
                "bsonType": "date",
                "description": "must be a date and is required"
            },
            "end_date": {
                "bsonType": "date",
                "description": "must be a date and is required"
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            },
            "skip_dates": {
                "bsonType": "array",
                "description": "must be an array of dates"
            }
        }
    }
}

unit_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["name", "code", "available"],
        "properties": {
            "name": {
                "bsonType": "string",
                "description": "must be a string and is required"
            },
            "code": {
                "bsonType": "string",
                "description": "must be a string and is required"
            },
            "section": {
                "bsonType": "string",
                "description": "must be a string"
            },
            "promo": {
                "bsonType": "string",
                "description": "must be a string"
            },
            "available": {
                "bsonType": "bool",
                "description": "must be a bool and is required"
            },
        }
    }
}