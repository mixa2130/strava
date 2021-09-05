async_strava
===========
------
[![PyPI - License](https://img.shields.io/pypi/l/strava)](https://pypi.org/project/strava)
[![Wheel](https://img.shields.io/pypi/wheel/strava)](https://pypi.org/project/strava)
[![PyPI](https://img.shields.io/pypi/v/strava)](https://pypi.org/project/strava)
[![PyPI](https://img.shields.io/pypi/pyversions/strava)](https://pypi.org/project/strava)

The strava project aims to provide an ability to quickly get big data not provided via current API.

The main goals, set during the development, were: performance and clarity in working with a large amount of data, and,
of course, system stability.

##### Note

This project was developed as a part of [strava_run_battle](https://gitlab.com/mixa2130/strava_run_battle) project and
will be updated as needed. But it's also an open source project - so you always can take part in it:)

If you would like to see some extra functions - as getting activity splits, segments.. Just open a new issue with a
description why you need such functionality.

## Installation

____

The package is available on PyPI to be installed using easy_install or pip:

``` bash
pip3 install strava
```

(Installing in a [virtual environment](https://pypi.python.org/pypi/virtualenv) is always recommended.)

Of course, by itself this package doesn't do much; it's a library. So it is more likely that you will list this package
as a dependency in your own `install_requires` directive in `setup.py`. Or you can download it and explore Strava
content in your favorite IDE.

## Building from sources

To build the project from sources access the project root directory and run

```bash
python3 setup.py build
```

Running

```bash
python3 setup.py install
```

will build and install *strava* in your *pip* package repository.

## Basic Usage

____

Please take a look at the source (in particular the async_strava.strava.Strava class), if you'd like to play around with
the API. Most of the functions have been implemented at this point; however, it's still not such fast as I would like,
and certain features, such as filters are still on the to-do list.

### Logger

Strava class provides a convenient logger which can help you to understand what's happening - ___do not avoid it___!

```bash
2021-09-05 16:54:59 - strava_crawler - INFO - strava.py._session_reconnecting - Session established

# Get strava nicknames from uri list
2021-09-05 16:55:29 - strava_crawler - INFO - strava.py._get_response - try ro reconnect, status code: 404
2021-09-05 16:55:44 - strava_crawler - INFO - strava.py.get_strava_nickname_from_uri - status https://www.starva.com/athletes/52015208 - 404 - Server error
2021-09-05 16:55:45 - strava_crawler - INFO - strava.py.get_strava_nickname_from_uri - Incorrect link - there are no strava title at https://vk.com/nagibator_archivator

# Get club activities
processing page_id: 1630829905
processing page_id: 1630767526
processing page_id: 1630735528
processing page_id: 1630666593
processing page_id: 1630603855
processing page_id: 1630579222
processing page_id: 1630557209
2021-09-05 20:51:42 - strava_crawler - INFO - strava.py.process_activity_page - Activity https://www.strava.com/activities/5899109029 has been deleted

2021-07-17 00:10:25 - strava_crawler - INFO - strava.py.shutdown - All tasks are finished
2021-07-17 00:10:25 - strava_crawler - INFO - strava.py.strava_connector - Session closed
```

### Authorization

In order to make use of this library, you will need to create an account at Strava, and join the corresponding clubs.

async_strava provides a convenient asynchronous context manager `strava_connector` which makes interaction easier.

```python
from async_strava import strava_connector

_login: str = 'LOGIN'
_password: str = 'PASSWORD'

async with strava_connector(_login, _password) as strava_obj:
    print(strava_obj.check_connection_setup())
```

You also can create session by yourself - by using the class directly:

```python
from async_strava import Strava

strava_obj = Strava(_login, _password)
print(strava_obj.check_connection_setup())

# Closing the session at the end of work - is a sign of good manners
await strava_obj.close()
```

_Using strava_connector - is preferable._

### Club activities

Using async_strava you can retrieve activities from clubs you belong to, and it will be fast!
async_strava needs about 13 seconds to get, and process all club activities.

As a result you'll get python dict, which is ready for json serialize:

```python
{
    "results": [
        {
            "info": {
                'routable': True,
                'title': 'Ночной забег',
                'href': 'https://www.strava.com/activities/5847036527',
                'nickname': 'Денис Тюрин',
                'type': 'Run',
                'date': '2021-08-24'
            },
            'values': {
                'distance': 5.43,
                'moving_time': 1575,
                'pace': 290,
                'elevation_gain': 34,
                'calories': 0
            }
        },
        {
            'info': {
                'routable': False,
                'title': 'Hello weekend!',
                'href': 'https://www.strava.com/activities/5900606701',
                'nickname': 'Janet Dam',
                'type': 'Run',
                'date': '2021-09-03'
            },
            'values': {
                'distance': 5.7,
                'moving_time': 3480,
                'pace': 610,
                'elevation_gain': 0,
                'calories': 0
            }
        }
    ]
}
```

#### Note
Serialization example:

```python
import json

def dict_serialize(activities: dict):
    """activities dict from get_club_activities function already ready for serialization"""
    return json.dumps(activities)
```

Pretty adorable - isn't it?

#### How to use
```python
from async_strava import strava_connector

_login: str = 'LOGIN'
_password: str = 'PASSWORD'

async with strava_connector(_login, _password) as strava_obj:
    # To get the club activities - you will need the club id, 
    # which could be found at https://www.strava.com/clubs/{club_id}/recent_activity
    club_id: int = 00000
    activities_generator = await strava_obj.get_club_activities(club_id)
```

New in version _0.2.0_ - filters!

```python
from datetime import datetime
from async_strava import strava_connector

_login: str = 'LOGIN'
_password: str = 'PASSWORD'

async with strava_connector(_login, _password,
                            filters={'date': datetime(year=2021, month=1, day=1)}) as strava_obj:
    # To get the club activities - you will need the club id, 
    # which could be found at https://www.strava.com/clubs/{club_id}/recent_activity
    club_id: int = 00000
    activities_generator = await strava_obj.get_club_activities(club_id)
```


### Get nicknames

```python
from async_strava import strava_connector

_login: str = 'LOGIN'
_password: str = 'PASSWORD'

async with strava_connector(_login, _password) as strava_obj:
    nickname: str = await strava_obj.get_strava_nickname_from_uri('https://www.strava.com/athletes/..')
```

## Still reading?

____
Take a look at [examples](https://github.com/mixa2130/strava/tree/master/examples) if something remained unclear