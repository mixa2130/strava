"""
Ignoring non run activities

None in results of club_activities represents an error in activity. For example - ActivityNotExist
"""
import logging
import re
import asyncio

from typing import NoReturn, List
from contextlib import asynccontextmanager
from sys import stdout
from datetime import datetime, timezone

import aiohttp

from bs4 import BeautifulSoup as Bs
from lxml import html
from async_class import AsyncClass
from .exceptions import StravaSessionFailed, ServerError, StravaTooManyRequests, NonRunActivity, ActivityNotExist, \
    ParserError
from .attributes import Activity, ActivityValues, EMPTY_ACTIVITY, EMPTY_ACTIVITY_VALUE

# Configure logging
LOGGER = logging.getLogger('strava_crawler')
LOGGER.setLevel(logging.DEBUG)

handler = logging.StreamHandler(stdout)
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s.%(funcName)s - %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')

handler.setFormatter(formatter)
LOGGER.addHandler(handler)


def bs_object(text):
    return Bs(text, 'html.parser')


def write_club_activities_to_file(results: List[Activity], filename: str = 'results.txt', mode: str = 'a'):
    """
    Represents activity results in a well-readable view.

    NOTE: Remember that it's a synchronous function!!

    :param results: obtained info about activities
    :param mode: file write mode: 'w', 'a'. Default = 'w'
    :param filename: default - 'results.txt'
    """
    with open(filename, mode) as file:
        for activity in results:
            out_activity_dict = activity._asdict()
            for key in out_activity_dict:
                if key == 'activity_values':
                    tmp: ActivityValues = out_activity_dict[key]
                    act_val = tmp._asdict()

                    for act_key in act_val.keys():
                        file.write(f"{' ' * 5}{act_key}: {act_val[act_key]}\n")

                else:
                    file.write(f'{key}: {out_activity_dict[key]}\n')

            file.write('\n')


class Strava(AsyncClass):
    """Main class for interacting  with www.strava.com website"""

    async def __ainit__(self, login: str, password: str) -> NoReturn:
        self._session = aiohttp.ClientSession()
        self._login: str = login
        self._password: str = password

        self.connection_established: bool = False

        connection = await self._session_reconnecting()
        if connection == 0:
            self.connection_established = True

        # Session connection failure during initialization would be proceed in a context manager

    async def _strava_authorization(self):
        """
        Makes authorization for current strava session.

        :return: aiohttp auth request information
        """

        def _csrf_token(text: str) -> str:
            """
            Extracts the csrf token from the passed html text.

            :param text: html page code
            :return: csrf token from page code
            """
            tree = html.fromstring(text)
            tokens: list = tree.xpath('//*[@name="csrf-token"]/@content')

            return tokens[0]

        html_text: str = await self._get_html('https://www.strava.com/login')
        csrf_token: str = _csrf_token(html_text)

        parameters = {'authenticity_token': csrf_token,
                      'email': self._login,
                      'password': self._password
                      }

        return await self._session.post('https://www.strava.com/session', data=parameters)

    async def _session_reconnecting(self) -> int:
        """
        Updates or reconnects strava session.

        :return: 0 - session established;
                 -1 - can't reconnect
        """
        allowed_attempts: int = 3

        for check_counter in range(allowed_attempts):
            # This one will try to reconnect the session,
            # if connection wasn't established in the first attempt
            session_response = await self._strava_authorization()
            connection = await self.connection_check(session_response)

            if not connection:
                LOGGER.error('%i of %i attempt to connect has failed', check_counter + 1, allowed_attempts)
                await asyncio.sleep(15)
            else:
                LOGGER.info('Session established')
                return 0

        # Can't reconnect
        return -1

    async def _get_html(self, uri) -> str:
        """Gets html page code """
        response = await self._session.get(uri)
        return await response.text()

    @staticmethod
    async def _get_soup(html_text: str):
        """Executes blocking task in an executor - another thread"""
        soup_loop = asyncio.get_running_loop()
        return await soup_loop.run_in_executor(None, bs_object, html_text)

    async def connection_check(self, request_response) -> bool:
        """
        Checks the strava page connection by parsing the html code


        :returns: - True - the connection is establish;
                  - False - the connection isn't established.
        """
        html_text = await request_response.text()

        if html_text[:500].find('logged-out') == -1:
            # We've logged-in
            return True

        # Strava logged us out, maybe there is an alert message
        soup = await self._get_soup(html_text)

        alert_message = soup.select_one('div.alert-message')
        if alert_message is not None:
            LOGGER.error('alert message in a page: %s', alert_message.text)

        return False

    async def _get_response(self, uri):
        """
        In my mind - this function has to proceed and return "get" request response.
        It has to proceed such errors, as 429, ServerDisconnectedError, ..

        :param uri: requested page

        :raise StravaSessionFailed: if unable to reconnect or update strava session
        :return: request result obj
        """
        try:
            response = await self._session.get(uri)
            status_code = response.status

            if status_code != 200:

                if status_code == 429:
                    # This error will cancel connection.
                    # Therefore, within the framework of this class, it is not processed
                    raise StravaTooManyRequests

                if status_code - 400 >= 0:
                    raise ServerError(status_code)

            return response

        except aiohttp.ServerDisconnectedError:
            LOGGER.info('ServerDisconnectedError in get_strava_nickname_from_uri %s', uri)

            if self.connection_established:
                # We would like to reconnect just one time,
                # and not as much as tasks will come
                self.connection_established = False

                connection = await self._session_reconnecting()
                if connection == -1:
                    raise StravaSessionFailed

                self.connection_established = True
            else:
                while not self.connection_established:
                    await asyncio.sleep(4)

            return await self._session.get(uri)

    async def get_strava_nickname_from_uri(self, profile_uri: str) -> str:
        """
        Gets nickname from strava user profile page.
        If page not found - def will return '' - an empty str.

        :param profile_uri: strava user profile uri
        :raise StravaTooManyRequests: too many requests per time unit -
         strava won't let us in for 10 minutes at least
        :return: user nickname from transmitted uri
        """
        try:
            response = await self._get_response(profile_uri)
        except ServerError as exc:
            LOGGER.info('status %s - %s', profile_uri, repr(exc))
            return ''

        soup = await self._get_soup(await response.text())
        title = soup.select_one('title').text

        return title[(title.find('| ') + 2):]

    @staticmethod
    def _process_inline_section(stat_section, activity_href: str) -> dict:
        """
        Processes activity page inline-stats section.

        :param activity_href: activity uri
        :param stat_section: inline-stats section html cluster

        :raise ActivityNotExist: Activity has been deleted
        :return {distance:, moving_time:, pace:}
        """
        distance = 0
        moving_time = {'hours': 0, 'minutes': 0, 'seconds': 0}
        pace: dict = {'min_km': 0, 'sec_km': 0}

        try:
            activity_details = stat_section.select('li')
            for item in activity_details:
                tmp = item.select_one('div.label').text

                cluster_type = tmp.strip()
                cluster = item.select_one('strong').text

                if cluster_type == 'Distance':
                    divided_distance = re.findall(r'[\d.]', cluster)
                    distance = float(''.join(divided_distance))

                if cluster_type == 'Moving Time' or cluster_type == 'Elapsed Time':
                    time_values: List[str] = cluster.split(':')

                    if len(time_values) == 3:
                        for time_index, key in enumerate(moving_time.keys()):
                            moving_time[key] = int(time_values[time_index])
                    else:
                        moving_time['minutes'] = int(time_values[0])
                        moving_time['seconds'] = int(time_values[1])

                if cluster_type == 'Pace':
                    pace_values = cluster.split(':')  # ['7', '18/km'] ['7s/km']
                    for index, value in enumerate(pace_values):
                        str_value = re.search(r'\d+', value)
                        pace_values[index]: int = int(str_value.group(0)) if str_value is not None else 0

                    if len(pace_values) == 1:
                        pace['sec_km'] = pace_values[0]
                    else:
                        pace['min_km'] = pace_values[0]
                        pace['sec_km'] = pace_values[1]

        except Exception as exc:
            LOGGER.error(repr(exc))
            raise ParserError(activity_href, repr(exc))

        if moving_time['minutes'] == moving_time['seconds'] == moving_time['hours'] == 0 or \
                distance == 0 or pace['min_km'] == pace['sec_km'] == 0:
            # Run activity can't exist without one of this params
            raise NonRunActivity(activity_href)

        return {'distance': distance, 'moving_time': moving_time, 'avg_pace': pace}

    @staticmethod
    def _process_more_stats(more_stats_section, activity_href) -> dict:
        """
        Processes activity page more-stats section.

        :param more_stats_section: more-stats section html cluster

        :return: {elevation_gain:, calories:}
        """
        elevation_gain: int = 0
        calories: int = 0

        try:
            if more_stats_section:
                rows = more_stats_section.select('div.row')

                for row in rows:
                    values = row.select('div.spans3')
                    descriptions = row.select('div.spans5')

                    for index, desc in enumerate(descriptions):
                        if desc.text.strip() == 'Elevation':
                            # We get value in format '129m\n' or '\n129m\n'
                            elevation = re.search('[0-9]+', values[index].text)

                            if elevation is not None:
                                elevation_gain = int(elevation.group())

                        if desc.text.strip() == 'Calories':
                            calories_value: str = values[index].text.strip()

                            # We can get calories in such views: '-' <=> 0, '684', '1,099' <=> 1099
                            if calories_value != '—':
                                calories: int = int(re.sub(r',', r'', calories_value))
        except Exception as exc:
            LOGGER.error(repr(exc))
            raise ParserError(activity_href, repr(exc))

        return {'elevation_gain': elevation_gain, 'calories': calories}

    @staticmethod
    def _process_device_section(device_cluster, activity_href) -> dict:
        """
        Processes activity page device section.

        :param device_cluster: device section html cluster

        :return: {device:, gear:}
        """
        gear = '-'
        device = '-'

        try:
            if device_cluster:
                device_section = device_cluster.select_one('div.device')
                gear_section = device_cluster.select_one('span.gear-name')

                if gear_section is not None:
                    raw_gear: str = gear_section.text.strip()  # adidas Pulseboost HD\n(2,441.7 km)

                    gear = raw_gear.split('\n')
                    if len(gear) == 2 and len(gear[1]) > 2:
                        # remove brackets from gear mileage
                        gear[1] = gear[1][1:len(gear[1]) - 1]

                if device_section is not None:
                    device: str = device_section.text.strip()

        except Exception as exc:
            LOGGER.error(repr(exc))
            raise ParserError(activity_href, repr(exc))

        return {'device': device, 'gear': tuple(gear)}

    async def _process_activity_page(self, activity_href: str) -> ActivityValues:
        """
        Processes activity page, which contains 3 importable sections for us:
            1) inline-stats section - distance, moving time, pace blocks;
            2) more-stats section - elevation gain, calories blocks;
            3) device section - device, gear blocks.

        :param activity_href: activity page uri
        """
        response = await self._get_response(activity_href)
        soup = await self._get_soup(await response.text())

        try:
            # Activity type
            title_block = soup.select_one('span.title')
            if title_block is None:
                # Server errors have been proceeded previously in get_response
                # If there is no activity title - then we've been redirected to the dashboard
                raise ActivityNotExist(activity_href)

            # Distance, Moving time, Pace block
            inline_section: dict = self._process_inline_section(
                stat_section=soup.select_one('ul.inline-stats.section'),
                activity_href=activity_href)

            # Elevation, Calories blocks
            more_stats_section: dict = self._process_more_stats(
                more_stats_section=soup.select_one('div.section.more-stats'),
                activity_href=activity_href)

            # Device, Gear blocks
            device_section = self._process_device_section(
                device_cluster=soup.select_one('div.section.device-section'),
                activity_href=activity_href)

        except (NonRunActivity, ActivityNotExist, ParserError) as exc:
            LOGGER.info(repr(exc))
            return EMPTY_ACTIVITY_VALUE

        else:
            return ActivityValues(distance=inline_section['distance'],
                                  moving_time=inline_section['moving_time'],
                                  avg_pace=inline_section['avg_pace'],
                                  elevation_gain=more_stats_section['elevation_gain'],
                                  calories=more_stats_section['calories'],
                                  device=device_section['device'],
                                  gear=device_section['gear'])

    async def _process_activity_cluster(self, activity_cluster, group_mode: bool = False):
        """
        Processing of the activity cluster, presented on the page of recent club activities.
        Works as for single, as for group activities

        Cluster contains a lot of useful information. That's why you may have a question:
        why do we need to get particular values exactly from activity page, and not from this cluster?
        We have to do it because cluster, mostly, contains outdated information.
        For example - if user has deleted an activity - it will be shown among clusters,
        but activity page would not exist, which may lead some problems..

        :param activity_cluster: bs object: class 'bs4.element.Tag'
        """

        def utc_to_local(timestamp: str):
            """
            UTC timestamp converter

            Output instance:
            datetime.datetime(2021, 5, 8, 18, 38, 29, tzinfo=datetime.timezone(datetime.timedelta(seconds=10800), 'MSK'))

            :param timestamp: utc timestamp in format '0000-00-00 00:00:00 UTC'
            :type timestamp: str

            :return: local timestamp in datetime format
            """
            utc_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S UTC")
            return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)

        def nickname_converter(raw_nickname: str) -> str:
            """Validates obtained nickname"""
            # nickname looks like: '\nАлександр Мариев\nSubscriber\n'
            nick: str = re.sub(r'\n|\bSubscriber\b', '', raw_nickname)
            return nick.strip()

        entry_head = activity_cluster.select_one('div.entry-head')
        activity_timestamp = entry_head.select_one('time.timestamp').get('datetime')
        local_dt = utc_to_local(activity_timestamp)

        if not group_mode:
            # Single activity cluster processing
            route = bool(activity_cluster.select('a.entry-image.activity-map'))
            nickname: str = nickname_converter(entry_head.select_one('a.entry-athlete').text)

            entry_body = activity_cluster.select_one('h3.entry-title.activity-title').select_one('strong a')
            activity_href = entry_body.get('href')
            activity_title = entry_body.text

            activity_values = await self._process_activity_page('https://www.strava.com' + activity_href)
            if activity_values == EMPTY_ACTIVITY_VALUE:
                return EMPTY_ACTIVITY
            return Activity(route_exist=route, activity_datetime=local_dt,
                            activity_title=activity_title.strip(), user_nickname=nickname,
                            activity_values=activity_values)
        else:
            # Group cluster processing
            route: bool = bool(activity_cluster.select('div.group-map'))

            activities: List[Activity] = []
            # Group activity cluster can't exist without entries.
            for entry in activity_cluster.select('li.feed-entry.entity-details'):
                nickname: str = nickname_converter(entry.select_one('a.entry-athlete').text)

                entry_title = entry.select_one('a.minimal')
                activity_href = entry_title.get('href')
                activity_title = entry_title.text

                activity_values = await self._process_activity_page('https://www.strava.com' + activity_href)
                if activity_values != EMPTY_ACTIVITY_VALUE:
                    activities.append(Activity(route_exist=route, activity_datetime=local_dt,
                                               activity_title=activity_title.strip(), user_nickname=nickname,
                                               activity_values=activity_values))

            return tuple(activities)

    async def _get_tasks(self, page_url: str, tasks: list) -> int:
        """
        Create tasks of single and group activities for concurrently execution

        :return - before parameter for next page request. If it's the last page - 0.
        """
        response = await self._get_response(page_url)
        soup = await self._get_soup(await response.text())

        single_activities_blocks = soup.select('div.activity.entity-details.feed-entry')
        single_len: int = len(single_activities_blocks)

        group_activities_blocks = soup.select('div.feed-entry.group-activity')
        group_len: int = len(group_activities_blocks)

        if single_len == 0 and group_len == 0:
            # No more pages - we've found the last one
            return 0

        single_before: int = -1
        group_before: int = -1

        if single_len > 0:
            for cluster in single_activities_blocks:
                tasks.append(asyncio.create_task(self._process_activity_cluster(cluster)))

            # We can guarantee before existence, cause it's one of main params in a strava activity class
            single_before = int(single_activities_blocks[len(single_activities_blocks) - 1].get('data-updated-at'))

        if group_len > 0:
            for group_cluster in group_activities_blocks:
                tasks.append(asyncio.create_task(self._process_activity_cluster(group_cluster, group_mode=True)))

            # We can guarantee before existence, cause it's one of main params in a strava activity class
            group_before = int(group_activities_blocks[len(group_activities_blocks) - 1].get('data-updated-at'))

        # One of (single_before, group_before) will exist anyway, cause the last page case we've proceeded previously
        if single_before == -1:
            return group_before
        if group_before == -1:
            return single_before

        # As single_before, as group_before was initialised
        return single_before if single_before < group_before else group_before

    @staticmethod
    def _validate_tasks_output(validate_lst: list):
        """
        Creates a generator from validate_list, which consist of:
            Activity class instances - single activities, which've been parsed well,
            EMPTY_ACTIVITY - single activity in which the error from exceptions.py has occurred,
            and tuple of Activity class instances - group Activity.

        :return: generator, which yields Activity class instances
        """
        for activity in validate_lst:
            if type(activity) == tuple:
                for el in activity:
                    yield el
            elif activity != EMPTY_ACTIVITY:
                yield activity

    async def get_club_activities(self, club_id: int):
        """
        Get club activities, presented in https://www.strava.com/clubs/{club_id}/recent_activity page.
        Retrieves as single, as group activities.

        :return: the result generator, which yields objects of the Activity class
        """
        club_activities_page_url: str = f'https://www.strava.com/clubs/{str(club_id)}/feed?feed_type=club'

        # Start pages processing
        activities_tasks = []
        before: int = await self._get_tasks(club_activities_page_url, activities_tasks)

        while before != 0:
            before: int = await self._get_tasks(
                club_activities_page_url + f'&before={before}&cursor={float(before)}',
                activities_tasks)

        return self._validate_tasks_output(await asyncio.gather(*activities_tasks))

    def check_connection_setup(self) -> bool:
        return self.connection_established

    async def __adel__(self) -> None:
        await self._session.close()


async def shutdown():
    """Closes unfinished tasks"""
    tasks = [task for task in asyncio.Task.all_tasks() if task is not
             asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    LOGGER.info('All tasks are finished')


@asynccontextmanager
async def strava_connector(login: str, password: str):
    """
    Context manager for working with instances of Strava class.

    Available RuntimeError: generator didn't yield
    :param login: strava login
    :param password: strava password

    :raise StravaSessionFailed: if unable to reconnect or update strava session
    """
    small_strava = await Strava(login, password)

    try:
        if not small_strava.check_connection_setup():
            raise StravaSessionFailed

        yield small_strava

    except Exception as exc:
        LOGGER.error(repr(exc))

    finally:
        await small_strava.close()
        await shutdown()
        LOGGER.info('Session closed')
