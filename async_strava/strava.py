import logging
import re
import asyncio

from typing import NoReturn, NamedTuple, List
from contextlib import asynccontextmanager
from sys import stdout

import aiohttp

from datetime import datetime, timezone
from bs4 import BeautifulSoup as Bs
from lxml import html
from urllib.parse import urljoin
from async_class import AsyncClass
from .exceptions import StravaSessionFailed, StravaTooManyRequests

# Configure logging
LOGGER = logging.getLogger('strava_crawler')
LOGGER.setLevel(logging.DEBUG)

handler = logging.StreamHandler(stdout)
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')

handler.setFormatter(formatter)
LOGGER.addHandler(handler)


class Activity(NamedTuple):
    route_exist: bool
    activity_datetime: datetime
    user_nickname: str


def bs_object(text):
    return Bs(text, 'html.parser')


class Strava(AsyncClass):
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
        html_text: str = await self._get_html('https://www.strava.com/login')
        csrf_token: str = self._csrf_token(html_text)

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
                await asyncio.sleep(7)
                LOGGER.error('%i of %i attempt to connect has failed', check_counter + 1, allowed_attempts)
            else:
                LOGGER.info('Session established')
                return 0

        # Can't reconnect
        return -1

    @staticmethod
    def _csrf_token(text: str) -> str:
        """
        Extracts the csrf token from the passed html text.

        :param text: html page code
        :return: csrf token from page code
        """
        tree = html.fromstring(text)
        tokens: list = tree.xpath('//*[@name="csrf-token"]/@content')

        return tokens[0]

    async def _get_html(self, uri) -> str:
        """Gets html page code """
        response = await self._session.get(uri)
        return await response.text()

    @staticmethod
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

    @staticmethod
    async def connection_check(request_response) -> bool:
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
        soup_loop = asyncio.get_running_loop()()
        soup = await soup_loop.run_in_executor(None, bs_object, html_text)

        alert_message = soup.select_one('div.alert-message')
        if alert_message is not None:
            LOGGER.error('alert message in a page: %s', alert_message.text)

        return False

    async def get_response(self, uri):
        """
        In my mind - this function has to proceed and return "get" request response.
        It has to proceed such errors, as 429, ServerDisconnectedError, ..


        :param uri: requested page

        :raise StravaSessionFailed: if unable to reconnect or update strava session
        :return: request result obj
        """
        try:
            return await self._session.get(uri)
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
        response = await self.get_response(profile_uri)

        if response.status == 429:
            raise StravaTooManyRequests

        if response.status != 200:
            LOGGER.info('status %s - %i', profile_uri, response.status)
            return ''

        soup_loop = asyncio.get_running_loop()
        soup = await soup_loop.run_in_executor(None, bs_object, await response.text())

        title = soup.select_one('title').text
        return title[(title.find('| ') + 2):]

    # async def _process_activity_page(self, activity_href: str):
    #     resp = await self.get_response(activity_href)

    async def _process_activity_cluster(self, activity_cluster) -> Activity:
        # activity_cluster is a bs object: class 'bs4.element.Tag'
        reg = re.compile('[\n]')
        entry_head = activity_cluster.select_one('div.entry-head')

        timestamp = entry_head.select_one('time.timestamp').get('datetime')
        local_dt = self.utc_to_local(timestamp)

        raw_nickname = reg.sub('', entry_head.select_one('a.entry-athlete').text)
        subscriber_index = raw_nickname.find('Subscriber')
        nickname = raw_nickname[0:subscriber_index] if subscriber_index != -1 else raw_nickname

        route = True if activity_cluster.select('a.entry-image.activity-map') else False
        activity_href = activity_cluster.select_one('h3.entry-title.activity-title').select_one('strong') \
            .select_one('a').get('href')

        return Activity(route, local_dt, nickname)

    async def get_club_activities(self, club_id: int):
        club_activities_page_url = 'https://www.strava.com/clubs/%s/recent_activity' % club_id
        response = await self.get_response(club_activities_page_url)

        soup_loop = asyncio.get_running_loop()
        soup = await soup_loop.run_in_executor(None, bs_object, await response.text())

        single_activities_blocks = soup.select('div.activity.entity-details.feed-entry')
        # As for single, as for group activities
        activities_tasks = [asyncio.create_task(self._process_activity_cluster(cluster)) for cluster in
                            single_activities_blocks]

        results: List[Activity] = await asyncio.gather(*activities_tasks)
        # print(results)

    def check_connection_setup(self) -> bool:
        return self.connection_established

    async def __adel__(self) -> None:
        await self._session.close()


@asynccontextmanager
async def strava_connector(login: str, password: str):
    """
    Context manager for working with instances of Strava class.

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
        LOGGER.info('Session closed')
