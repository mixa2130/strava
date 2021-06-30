from typing import NamedTuple
from datetime import datetime


class ActivityValues(NamedTuple):
    """Values from activity page"""

    distance: float
    moving_time: dict  # {'hours': 0, 'min': 13, 'sec': 7}
    avg_pace: dict  # {'min_km': 6, 'sec_km': 25}
    elevation_gain: int
    calories: int
    device: str
    gear: tuple


class Activity(NamedTuple):
    """Represents single strava activity"""

    route_exist: bool
    user_nickname: str
    activity_datetime: datetime
    activity_title: str
    activity_values: ActivityValues
