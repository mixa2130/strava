"""
Ignoring non run activities

None in results of club_activities represents an error in activity. For example - ActivityNotExist
"""
import logging
import re
import json
import asyncio

from typing import NoReturn, List, Optional
from contextlib import asynccontextmanager
from sys import stdout
from datetime import datetime, timedelta

import aiohttp

from bs4 import BeautifulSoup as Bs
from lxml import html
from async_class import AsyncClass
from .exceptions import StravaSessionFailed, ServerError, StravaTooManyRequests, ActivityNotExist, ParserError
from .attributes import ActivityInfo, Activity

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


class Strava(AsyncClass):
    """Main class for interacting  with www.strava.com website"""

    async def __ainit__(self, login: str, password: str, filters: dict) -> NoReturn:
        self._session = aiohttp.ClientSession()
        self._login: str = login
        self._password: str = password

        self.filters: dict = filters
        self.connection_established: bool = False

        connection = await self._session_reconnecting()
        if connection == 0:
            self.connection_established = True
        else:
            raise StravaSessionFailed
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

        response = await self._session.get('https://www.strava.com/login')
        csrf_token: str = _csrf_token(await response.text())

        data = {'authenticity_token': csrf_token,
                'email': self._login,
                'password': self._password
                }

        return await self._session.post('https://www.strava.com/session', data=data)

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

    @staticmethod
    async def _get_soup(html_text: str):
        """Executes blocking task in an executor - another thread"""
        soup_loop = asyncio.get_running_loop()
        return await soup_loop.run_in_executor(None, bs_object, html_text)

    async def _get_response(self, uri):
        """
        In my mind - this function has to proceed and return "get" request response.
        It has to proceed such errors, as 429, ServerDisconnectedError, ..

        :param uri: requested page

        # :raise StravaSessionFailed: if unable to reconnect or update strava session
        :return: request result obj
        """
        response = await self._session.get(uri)
        status_code = response.status

        if status_code != 200:

            if status_code == 429:
                # This error will cancel connection.
                # Therefore, within the framework of this class, it is not processed
                raise StravaTooManyRequests

            if status_code - 400 >= 0:
                # try to reconnect
                LOGGER.info(f'try ro reconnect:{status_code}')
                await asyncio.sleep(5)

                response = await self._session.get(uri)
                if response.status != 200:
                    raise ServerError(status_code)

        return response

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

        def str_time_to_sec(_time: list) -> int:
            _seconds: int = 0
            n = len(_time) - 1

            for time_el in _time:
                _seconds += int(time_el) * pow(60, n)
                n -= 1

            return _seconds

        distance: float = 0.0
        moving_time: int = 0
        pace: int = 0

        try:
            activity_details = stat_section.select('li')
            for item in activity_details:
                tmp = item.select_one('div.label').text

                cluster_type = tmp.strip()
                cluster = item.select_one('strong').text

                if cluster_type == 'Distance':
                    divided_distance = re.findall(r'[\d.]', cluster)

                    if len(divided_distance) != 0:
                        distance = float(''.join(divided_distance))
                        # else it would be a default value

                if cluster_type in ('Moving Time', 'Elapsed Time', 'Duration'):
                    moving_time: int = str_time_to_sec(cluster.split(':'))

                if cluster_type == 'Pace':
                    divided_pace: List[str] = cluster.split(':')  # ['7', '18/km'] ['7s/km']
                    raw_pace_vls: List[int] = []

                    for index, value in enumerate(divided_pace):
                        str_value = re.search(r'\d+', value)

                        if str_value is not None:
                            raw_pace_vls.append(int(str_value.group(0)))

                    pace: int = str_time_to_sec(raw_pace_vls)

            return {'distance': distance, 'moving_time': moving_time, 'pace': pace}

        except Exception as exc:
            raise ParserError(activity_href, repr(exc))

    @staticmethod
    def _process_more_stats(more_stats_section, activity_href) -> dict:
        """
        Processes activity page more-stats section.

        :param more_stats_section: more-stats section html cluster

        :return: {elevation_gain:, calories:}
        """
        elevation_gain: int = 0
        calories: int = 0

        if more_stats_section is not None:
            # Such block exists, but frontend may have changed

            try:
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

    async def _process_activity_page(self, activity_href: str,
                                     activity_info: ActivityInfo = None) -> Optional[Activity]:
        """
        Processes activity page, which contains 3 importable sections for us:
            1) inline-stats section - distance, moving time, pace blocks;
            2) more-stats section - elevation gain, calories blocks;
            3) device section - device, gear blocks. - temporarily unavailable

        :param activity_href: activity page uri
        """
        try:
            response = await self._get_response(activity_href)
        except ServerError as exc:
            LOGGER.info('status %s - %s', activity_href, repr(exc))
            return None

        soup = await self._get_soup(await response.text())

        try:
            title_block = soup.select_one('span.title')
            if title_block is None:
                # Server errors have been proceeded previously in get_response
                # If there is no activity title - then we've been redirected to the dashboard
                raise ActivityNotExist(activity_href)

            # There maybe no such blocks as inline/more_stats.

            # Distance, Moving time, Pace blocks
            # If there are no inline section - that's a problem(cause it's the most important section),
            # and responsible function has to raise ParserError.
            inline_section: dict = self._process_inline_section(
                stat_section=soup.select_one('ul.inline-stats.section'),
                activity_href=activity_href)

            # Elevation, Calories blocks
            # If there are no more stats - that's okay,
            # responsible function will return nullify values.
            more_stats_section: dict = self._process_more_stats(
                more_stats_section=soup.select_one('div.section.more-stats'),
                activity_href=activity_href)

            activity_values: dict = {**inline_section, **more_stats_section}
            return Activity(info=activity_info, values=activity_values)

        except (ActivityNotExist, ParserError) as exc:
            LOGGER.info(repr(exc))

    async def _get_tasks(self, page_url: str, tasks: list) -> int:
        """
        Create tasks of single and group activities for concurrently execution

        :return - before parameter for next page request. If it's the last page - 0.
        """
        comparsion_date: Optional[datetime] = self.filters.get('date')

        def validate_react_activity_info(activity_info: dict, raw_date: dict,
                                         group_mode: bool = False) -> Optional[ActivityInfo]:
            # date formatting
            activity_date: datetime = datetime.today()  # today
            if raw_date['displayDate'] == 'Yesterday':
                activity_date -= timedelta(days=1)
            elif raw_date['displayDate'] != 'Today':
                activity_date: datetime = datetime.strptime(raw_date['displayDate'], '%B %d, %Y')

            if comparsion_date is not None:
                # There is a date filter
                if ((comparsion_date.day, comparsion_date.month, comparsion_date.year) !=
                        (activity_date.day, activity_date.month, activity_date.year)):
                    # This activity has another date
                    return None

            # Activity date is in filter
            if not group_mode:
                title: str = activity_info['activityName']
                activity_type: str = activity_info['type']
                nickname: str = activity_info['athlete']['athleteName']
                href: str = 'https://www.strava.com/activities/' + str(activity_info['id'])

                routable: bool = False
                tmp_route_checker = activity_info['mapAndPhotos'].get('isRoutable')
                if tmp_route_checker is not None:
                    routable = tmp_route_checker
            else:
                routable: bool = activity_info['is_routable']
                href: str = 'https://www.strava.com/activities/' + str(activity_info['activity_id'])
                activity_type: str = activity_info['activity_class_name']
                nickname: str = activity_info['athlete_name']
                title: str = activity_info['name']

            return ActivityInfo(routable=routable,
                                title=title,
                                href=href,
                                nickname=nickname,
                                type=activity_type,
                                date=datetime.strftime(activity_date, '%Y-%m-%d'))

        before: int = 0
        try:
            response = await self._get_response(page_url)
        except ServerError as exc:
            LOGGER.info('status %s - %s', page_url, repr(exc))
            return 0

        soup = await self._get_soup(await response.text())
        activities: list = soup.select('div.content.web-feed-4-component')

        for activity in activities:
            activity_desc: dict = json.loads(activity.get('data-react-props'))
            before: int = activity_desc['cursorData']['updated_at']

            if activity_desc.get('activity') is not None:
                # Single mode
                validate_info: ActivityInfo = validate_react_activity_info(activity_desc['activity'],
                                                                           raw_date=activity_desc['activity'][
                                                                               'timeAndLocation'])
                if validate_info is None:
                    continue

                tasks.append(asyncio.create_task(
                    self._process_activity_page(activity_info=validate_info, activity_href=validate_info.href)))
            else:
                # Group mode
                for group_el in activity_desc.get('rowData').get('activities'):
                    validate_info: ActivityInfo = validate_react_activity_info(group_el, group_mode=True,
                                                                               raw_date=activity_desc.get(
                                                                                   'timeAndLocation'))
                    if validate_info is None:
                        continue

                    tasks.append(asyncio.create_task(self._process_activity_page(activity_info=validate_info,
                                                                                 activity_href=validate_info.href)))
        return before

    @staticmethod
    def results_validator(results: List[Activity]) -> dict:
        validate_results = list()
        for activity in results:
            if activity is not None:
                json_activity: dict = activity._asdict()

                tmp_activity_info: ActivityInfo = json_activity['info']
                json_activity['info']: ActivityInfo = tmp_activity_info._asdict()
                validate_results.append(json_activity)

        with open('results.json', 'w') as json_file:
            json.dump(validate_results, json_file)
        return {'results': validate_results}

    async def get_club_activities(self, club_id: int):
        """
        Get club activities, presented in https://www.strava.com/clubs/{club_id}/recent_activity page.
        Retrieves as single, as group activities.

        :return: the result generator, which yields objects of the Activity class
        """
        club_activities_page_url: str = f'https://www.strava.com/clubs/{str(club_id)}/feed?feed_type=club'

        # Start pages processing
        activities_tasks = list()
        before: int = await self._get_tasks(club_activities_page_url, activities_tasks)

        while before != 0:
            print(before)
            before: int = await self._get_tasks(
                club_activities_page_url + f'&before={before}&cursor={float(before)}',
                activities_tasks)

        return self.results_validator(await asyncio.gather(*activities_tasks))

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
async def strava_connector(login: str, password: str, filters: dict = None):
    """
    Context manager for working with instances of Strava class.

    Available RuntimeError: generator didn't yield
    :param login: strava login
    :param password: strava password
    :param filters:

    :raise StravaSessionFailed: if unable to reconnect or update strava session
    """

    small_strava = await Strava(login, password, filters if filters is not None else dict())

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
