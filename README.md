# strava
The strava project aims to provide an ability to quickly get big data not provided via current API.

The main goals, set during the development, were: performance and clarity in working with a large amount of data, 
and, of course, system stability.

##### Note
This project was developed as a part of [strava_run_battle](https://gitlab.com/mixa2130/strava_run_battle) project and
will be updated as needed. But it's also an open source project - so you always can take part in it:)

If you would like to see some extra functions - as getting activity splits, segments.. 
Just open a new issue with a description why you need such functionality

## Installation
(Installing in a [virtual environment](https://pypi.python.org/pypi/virtualenv) is always recommended.)

### Configuration
The project is configured using the `.env ' environment variable file in the working directory.

Sample `.env` file:

```env
# Strava auth parameters
LOGIN="abrakadabra@example.com"
PASSWORD="abrakadabra"
```

## Basic Usage
Strava class provides a convenient logger which can help you to understand what's happening - ___do not avoid it___!

```
2021-04-29 18:02:30 - strava_crawler - INFO - Session established
2021-04-29 18:03:08 - strava_crawler - INFO - status https://www.starva.com/athletes/.. - 404
2021-04-29 18:03:35 - strava_crawler - INFO - ServerDisconnectedError in get_strava_nickname_from_uri https://www.starva.com/athletes/..
2021-04-29 18:03:43 - strava_crawler - INFO - status https://www.starva.com/athletes/.. - 404
2021-04-29 18:03:44 - strava_crawler - ERROR - alert message in a page: You must be logged out before attempting to log in again.
2021-04-29 18:03:51 - strava_crawler - ERROR - 1 of 3 attempt to connect has failed
2021-04-29 18:03:54 - strava_crawler - INFO - Session established
2021-04-29 18:03:59 - strava_crawler - INFO - status https://www.starva.com/athletes/.. - 404
2021-04-29 18:04:48 - strava_crawler - INFO - status https://www.starva.com/athletes/.. - 404
2021-04-29 18:04:48 - strava_crawler - INFO - Session closed
```

## Still reading?
Take a look at [examples](https://github.com/mixa2130/strava/tree/master/examples) if something remained unclear