from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Literal

from bson import ObjectId
from pydantic import BaseModel, ConfigDict

SemesterType = Literal["fall", "spring", "year"]


class DictModel(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )

    def get(self, item: str, default: Any | None = None) -> Any:
        return getattr(self, item, default)

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(item) from exc

    def __contains__(self, item: object) -> bool:
        return isinstance(item, str) and hasattr(self, item)

    def keys(self) -> Iterable[str]:
        return self.model_dump().keys()

    def items(self) -> Iterable[tuple[str, Any]]:
        return self.model_dump().items()

    def values(self) -> Iterable[Any]:
        return self.model_dump().values()


class TeacherScraped(DictModel):
    name: str
    people_url: str


class StudyPlanScraped(DictModel):
    section: str
    semester: str


class CourseScraped(DictModel):
    name: str
    code: str
    credits: int | None
    studyplans: list[StudyPlanScraped]
    teachers: list[TeacherScraped]
    edu_url: str
    language: str | None = None


class CourseSchedule(BaseModel):
    course_id: str
    start_datetime: datetime
    end_datetime: datetime
    label: str
    rooms: list[str]


class PlanRoom(DictModel):
    name: str
    type: str
    coordinates: tuple[float, float] | None = None
    link: str | None = None
    capacity: int | None = None
    level: int | None = None


class CourseDocument(DictModel):
    _id: ObjectId | None = None
    code: str
    name: str
    credits: int | None = None
    available: bool
    edu_url: str | None = None
    language: str | None = None
    teachers: list[ObjectId] | None = None


class TeacherDocument(DictModel):
    _id: ObjectId | None = None
    name: str
    people_url: str
    available: bool


class UnitDocument(DictModel):
    _id: ObjectId | None = None
    name: str
    code: str
    section: str
    promo: str | None = None
    available: bool


class SemesterDocument(DictModel):
    _id: ObjectId | None = None
    name: str
    start_date: datetime
    end_date: datetime
    type: SemesterType
    available: bool
    skip_dates: list[datetime] | None = None


class StudyPlanDocument(DictModel):
    _id: ObjectId | None = None
    unit_id: ObjectId
    semester_id: ObjectId
    available: bool


class PlannedInDocument(DictModel):
    _id: ObjectId | None = None
    studyplan_id: ObjectId
    course_id: ObjectId
    available: bool


class CourseBookingDocument(DictModel):
    _id: ObjectId | None = None
    schedule_id: ObjectId
    room_id: ObjectId
    available: bool


class RoomDocument(DictModel):
    _id: ObjectId | None = None
    name: str
    type: str
    available: bool
    link: str | None = None
    coordinates: tuple[float, float] | None = None
    building: str | None = None
    capacity: int | None = None
    level: int | None = None
