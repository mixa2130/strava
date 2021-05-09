"""Custom exceptions, which were used in async_strava"""


class StravaSessionFailed(Exception):
    """Unable to create or update strava session"""

    def __repr__(self):
        return "Unable to create or update strava session"


class StravaTooManyRequests(Exception):
    """Http 429 status code - too many requests per time unit"""

    def __repr__(self):
        return "Http 429 status code - too many requests per time unit"


class NonRunActivity(Exception):
    """Non-running activity, such as cardio"""

    def __init__(self, activity_uri: str):
        self.uri = activity_uri

    def __repr__(self):
        return f"Non-running activity {self.uri}"


class ActivityNotExist(Exception):
    """Activity might be deleted recently.
    In this case strava redirects to the profile page"""

    def __init__(self, activity_uri: str):
        self.uri = activity_uri

    def __repr__(self):
        return f'Activity {self.uri} has been deleted'
