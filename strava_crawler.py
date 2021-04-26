import asyncio
import aiohttp
import os
import time
import logging

from bs4 import BeautifulSoup as Bs
from lxml import html
from dotenv import load_dotenv
from async_class import AsyncClass
from typing import NoReturn
from contextlib import asynccontextmanager
from sys import stdout
from exceptions import StravaSessionFailed

# Configure logging
logger = logging.getLogger('strava_crawler')
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(stdout)
handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                              datefmt='%Y-%m-%d %H:%M:%S')

handler.setFormatter(formatter)
logger.addHandler(handler)


async def get_html(session, uri):
    response = await session.get(uri)
    return await response.text()


def bs_object(text):
    return Bs(text, 'html.parser')


def read_file(file_name):
    with open(file_name, 'r') as file:
        for row in file:
            yield row.rstrip('\n')


class Strava(AsyncClass):
    async def __ainit__(self, login: str, password: str) -> NoReturn:
        self._session = aiohttp.ClientSession()
        self._login: str = login
        self._password: str = password
        self.connection_established: bool = False

        allowed_attempts: int = 2
        for check_counter in range(allowed_attempts):
            # This one will try to reconnect the session,
            # if connection wasn't established in the first attempt
            session_response = await self._registration()
            connection = await self.connection_check(session_response)
            if not connection:
                await asyncio.sleep(3)
                logger.error(f'{check_counter + 1} of {allowed_attempts} attempt to connect has failed')
            else:
                logger.info('Session established')
                self.connection_established = True
                break

        # Session connection failure would be proceed in a context manager

    async def _registration(self):
        html_text: str = await get_html(self._session, 'https://www.strava.com/login')
        token: list = await self._csrf_token(html_text)

        parameters = {'authenticity_token': token[0],
                      'email': self._login,
                      'password': self._password
                      }

        return await self._session.post('https://www.strava.com/session', data=parameters)

    @staticmethod
    async def _csrf_token(text: str):
        tree = html.fromstring(text)
        return tree.xpath('//*[@name="csrf-token"]/@content')

    @staticmethod
    async def connection_check(request_response):
        """
        Checks the strava page connection by parsing the html code

        # :param html_text: html code
        # :type html_text: str

        :returns: - True - the connection is establish;
                  - False - the connection isn't established.
        :rtype: bool
        """
        html_text = await request_response.text()

        if html_text[:500].find('logged-out') == -1:
            "We've logged-in"
            return True
        else:
            "Strava logged us out, maybe there is an alert message"
            soup_loop = asyncio.get_event_loop()
            soup = await soup_loop.run_in_executor(None, bs_object, html_text)

            alert_message = soup.select_one('div.alert-message')
            if alert_message is not None:
                logger.error(alert_message.text)

            return False

    def check_connection_setup(self):
        return self.connection_established

    # async def get_response(self, uri):
    #     """
    #     In my mind - this function has to proceed and return "get" request response.
    #     It has to proceed such errors, as 429, ServerDisconnectedError,
    #     aiohttp.ClientResponseError,
    #             aiohttp.ClientRequestError,
    #             aiohttp.ClientOSError,
    #             aiohttp.errors.ClientDisconnectedError,
    #             aiohttp.errors.ClientTimeoutError,
    #             asyncio.TimeoutError,
    #             aiohttp.errors.HttpProcessingError
    #
    #     :param url:
    #     :return:
    #     """
    #     try:
    #         raise aiohttp.ServerDisconnectedError
    #         return await self._session.get(uri)
    #     except aiohttp.ServerDisconnectedError:
    #         logger.info(f'ServerDisconnectedError in get_strava_nickname_from_uri')
    #
    #         if self.connection_established:
    #             self.connection_established = False
    #
    #             allowed_attempts: int = 2
    #             for check_counter in range(allowed_attempts):
    #                 # This one will try to reconnect the session,
    #                 # if connection wasn't established in the first attempt
    #                 session_response = await self._registration()
    #                 connection = await self.connection_check(session_response)
    #                 if not connection:
    #                     await asyncio.sleep(3)
    #                     logger.error(f'{check_counter + 1} of {allowed_attempts} attempt to connect has failed')
    #                 else:
    #                     logger.info('Session established')
    #                     self.connection_established = True
    #                     break
    #
    #             if not self.connection_established:
    #                 raise asyncio.CancelledError
    #
    #         else:
    #             while not self.connection_established:
    #                 await asyncio.sleep(2)
    #
    #         return await self._session.get(uri)

    async def get_strava_nickname_from_uri(self, profile_uri: str) -> str:
        """
        If page not found - ''

        :param profile_uri:
        :return:
        """
        # response = await self.get_response(profile_uri)
        try:
            response = await self._session.get(profile_uri)
        except aiohttp.ServerDisconnectedError:
            logger.info(f'ServerDisconnectedError in get_strava_nickname_from_uri {profile_uri}')
            await self._registration()
            response = await self._session.get(profile_uri)

        if response.status == 429:
            logger.info('429 - start waiting')
            await asyncio.sleep(4)
            try:
                response = await self._session.get(profile_uri)
            except aiohttp.ServerDisconnectedError:
                logger.info('ServerDisconnectedError in get_strava_nickname_from_uri')
                await self._registration()
                response = await self._session.get(profile_uri)

        if response.status != 200:
            logger.info(f'status {profile_uri} - {response.status}')
            return ''

        soup_loop = asyncio.get_event_loop()
        soup = await soup_loop.run_in_executor(None, bs_object, await response.text())

        title = soup.select_one('title').text
        return title[(title.find('| ') + 2):]

    async def __adel__(self) -> None:
        await self._session.close()


@asynccontextmanager
async def strava_connector(login, password):
    small_strava = await Strava(login, password)
    await asyncio.sleep(4)
    try:
        if not small_strava.check_connection_setup():
            logger.error('Unable to connect')
            raise StravaSessionFailed

        yield small_strava
    except Exception as exc:
        logger.error(repr(exc))
    finally:
        await small_strava.close()
        logger.info('Session closed')


async def get_nicknames(strava_obj):
    semaphore = asyncio.Semaphore(200)  # works as a resource counter
    async with semaphore:
        loop = asyncio.get_event_loop()
        uris_generator = await loop.run_in_executor(None, read_file, 'strava_uris.txt')
        tasks = [asyncio.create_task(strava_obj.get_strava_nickname_from_uri(uri)) for uri in uris_generator]
        results = await asyncio.gather(*tasks)
        print(results[0], results[len(results) - 1], len(results))


async def main():
    _login = os.getenv('LOGIN')
    _password = os.getenv('PASSWORD')

    async with strava_connector(_login, _password) as strava:
        await get_nicknames(strava)
        await get_nicknames(strava)
        await get_nicknames(strava)
        await get_nicknames(strava)
        await get_nicknames(strava)


# https://github.com/aio-libs/aiohttp/issues/850
if __name__ == '__main__':
    start = time.time()
    load_dotenv()
    asyncio.run(main())
    end = time.time() - start
    print(end)
