# async_strava
____

The strava project aims to provide an ability to quickly get big data not provided via current API.

The main goals, set during the development, were: performance and clarity in working with a large amount of data, 
and, of course, system stability.

##### Note
This project was developed as a part of [strava_run_battle](https://gitlab.com/mixa2130/strava_run_battle) project and
will be updated as needed. But it's also an open source project - so you always can take part in it:)

If you would like to see some extra functions - as getting activity splits, segments.. 
Just open a new issue with a description why you need such functionality

## Installation
____

(Installing in a [virtual environment](https://pypi.python.org/pypi/virtualenv) is always recommended.)

```bash
pip3 install -r requirements.txt
```

### Configuration
The project is configured using the `.env` environment variable file in the working directory.

Sample `.env` file:
```env
# Strava auth parameters
LOGIN="abrakadabra@example.com"
PASSWORD="abrakadabra"
```

## Basic Usage
____

Please take a look at the source (in particular the async_strava.strava.Strava class), if you'd like to play around with the API.
Most of the functions have been implemented at this point; however, it's still not such fast as I would like, and certain features, 
such as filters are still on the to-do list.

### Logger
Strava class provides a convenient logger which can help you to understand what's happening - ___do not avoid it___!
```bash
2021-07-17 00:10:11 - strava_crawler - INFO - strava.py._session_reconnecting - Session established
2021-07-17 00:10:18 - strava_crawler - INFO - strava.py._process_activity_page - Non-running activity https://www.strava.com/activities/..
2021-07-17 00:10:19 - strava_crawler - INFO - strava.py._process_activity_page - Non-running activity https://www.strava.com/activities/..
2021-07-17 00:10:25 - strava_crawler - INFO - strava.py._process_activity_page - Activity https://www.strava.com/activities/.. has been deleted
2021-07-17 00:10:25 - strava_crawler - INFO - strava.py.shutdown - All tasks are finished
2021-07-17 00:10:25 - strava_crawler - INFO - strava.py.strava_connector - Session closed
```

### Authorization
In order to make use of this library, you will need to create an account at Strava, and join the corresponding clubs.

async_strava provides a convenient asynchronous context manager `strava_connector` which makes interaction easier.
```python
from async_strava import strava_connector

_login: str = os.getenv('LOGIN')
_password: str = os.getenv('PASSWORD')

async with strava_connector(_login, _password) as strava_obj:
    print(strava_obj.check_connection_setup())
```

You also can create session by yourself - by using the class directly:
```python
strava_obj = Strava(_login, _password)
print(strava_obj.check_connection_setup())
    
# Closing the session at the end of work - is a sign of good manners
await strava_obj.close()
```

_Using strava_connector - is preferable._

### Club activities
Using async_class you can retrieve activities from clubs you belong to, and it will be fast!
async_class needs about 13 seconds (It will be faster in the version _0.2.0_) to get, and process all club activities. 

```python
from async_strava import strava_connector

_login: str = os.getenv('LOGIN')
_password: str = os.getenv('PASSWORD')

async with strava_connector(_login, _password) as strava_obj:
    # To get the club activities - you will need the club id, 
    # which could be found at https://www.strava.com/clubs/{club_id}/recent_activity
    club_id: int = 
    activities_generator = await strava_obj.get_club_activities(club_id)
```
#### Note
Be careful: the `get_club_activities` coroutine returns a generator! 


#### Activities viewing
____

For easy viewing the results of parsing - I've done a `write_club_activities_to_file` function, 
which writes activities to the `.txt` file.

```python
from async_strava import write_club_activities_to_file

write_club_activities_to_file(activities_generator)
```

The result looks like: 
```text
route_exist: True
user_nickname: Harry Potter
activity_datetime: 2021-07-16 14:39:06+03:00
activity_title: Exploring caves on the Marauder’s Map
     distance: 12.23
     moving_time: {'hours': 1, 'minutes': 6, 'seconds': 58}
     avg_pace: {'min_km': 5, 'sec_km': 28}
     elevation_gain: 49
     calories: 1078
     device: Huami Amazfit Pace
     gear: ('—',)

route_exist: True
user_nickname: Obi-Wan Kenobi
activity_datetime: 2021-07-16 12:57:41+03:00
activity_title: On this day, I stand above you
     distance: 6.62
     moving_time: {'hours': 1, 'minutes': 11, 'seconds': 39}
     avg_pace: {'min_km': 10, 'sec_km': 49}
     elevation_gain: 40
     calories: 598
     device: Suunto Ambit3 Sport
     gear: ('adidas Solar boost', '2,303.5 km')
```

Pretty adorable - isn't it?


#### Return
____

The time to talk about `get_club_activities` return value has come.
This coroutine, as mentioned above, returns a generator, which yields Activity class instances.
Activity class, as others, which purpose is communication between functions,
locates in async_strava.attributes.

```python
class Activity(NamedTuple):
    """Represents single strava activity"""

    route_exist: bool
    user_nickname: str
    activity_datetime: datetime
    activity_title: str
    activity_values: ActivityValues
```

Where ActivityValues:

```python
class ActivityValues(NamedTuple):
    """Values from activity page"""

    distance: float
    moving_time: dict  # {'hours': 0, 'min': 13, 'sec': 7}
    avg_pace: dict  # {'min_km': 6, 'sec_km': 25}
    elevation_gain: int
    calories: int
    device: str
    gear: tuple
```
_Deprecated since version 0.1.0, will be removed in version 0.2.0_

### Get nicknames

This function has been added for a friend - the organizer of the beermile.
```python
from async_strava import strava_connector

_login: str = os.getenv('LOGIN')
_password: str = os.getenv('PASSWORD')

async with strava_connector(_login, _password) as strava_obj:
    nickname: str = await strava_obj.get_strava_nickname_from_uri('https://www.strava.com/athletes/..')
```

_Will be fully redesigned and optimized in version 0.2.1_

## Still reading?
____
Take a look at [examples](https://github.com/mixa2130/strava/tree/master/examples) if something remained unclear