# strava
The strava project aims to provide an ability to quickly get big data not provided via current API.

The main goals, set during the development, were: performance and clarity in working with a large amount of data, 
and, of course, system stability.

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

## Basic Usage

Please take a look at [examples](https://github.com/mixa2130/strava/tree/master/examples) if something remained unclear