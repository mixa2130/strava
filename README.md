# strava
Asynchronous spider for web-scraping data from Strava.

The main goals, set during the development, were: performance in working with a large amount of data, 
and system stability.

##### Note
This project was developed as a part of [strava_run_battle](https://gitlab.com/mixa2130/strava_run_battle) project and
will be updated as needed.


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

## Exceptions
The following errors may occur during operation:

* `StravaSessionFailed` - unable to create or update strava session;
* `StravaTooManyRequests` - http 429 status code - too many requests per time unit.
