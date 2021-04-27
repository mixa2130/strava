"""Custom exceptions, which were used in async_strava"""


class StravaSessionFailed(Exception):
    """Unable to create or update strava session"""

    def __repr__(self):
        return "Unable to create or update strava session"


class StravaTooManyRequests(Exception):
    """Http 429 status code - too many requests per time unit"""

    def __repr__(self):
        return "Http 429 status code - too many requests per time unit"