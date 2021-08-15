from typing import NamedTuple
from datetime import datetime


class ActivityInfo(NamedTuple):
    routable: bool
    title: str
    href: str
    nickname: str
    type: str
    date: datetime


class Activity(NamedTuple):
    info: ActivityInfo
    values: dict
