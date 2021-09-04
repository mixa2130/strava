"""Custom exceptions, which were used in async_strava"""


class StravaSessionFailed(Exception):
    """Unable to create or update strava session"""

    def __repr__(self):
        return "Unable to create or update strava session"


class StravaTooManyRequests(Exception):
    """Http 429 status code - too many requests per time unit"""

    def __repr__(self):
        return "Http 429 status code - too many requests per time unit"


class ServerError(Exception):
    """Strava server error"""

    def __init__(self, status_code):
        self.code = status_code

    def __repr__(self):
        return f"{self.code} - Server error"


class ActivityNotExist(Exception):
    """
    Activity might be deleted recently.
    In this case strava redirects to the profile page
    """

    def __init__(self, activity_uri: str):
        self.uri = activity_uri

    def __repr__(self):
        return f'Activity {self.uri} has been deleted'


class ParserError(Exception):
    """Failure during web page parsing: Programmer made a mistake"""

    def __init__(self, activity_uri: str, exception_desc: str):
        self.uri = activity_uri
        self.exc = exception_desc

    def __repr__(self):
        return f'{self.exc} during parsing {self.uri}.'
