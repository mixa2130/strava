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

        await self._registration(login, password)

    async def _registration(self, strava_login: str, strava_password: str):
        html_text: str = await get_html(self._session, 'https://www.strava.com/login')
        token: list = await self._csrf_token(html_text)

        parameters = {'authenticity_token': token[0],
                      'email': strava_login,
                      'password': strava_password
                      }

        await self._session.post('https://www.strava.com/session', data=parameters)

    @staticmethod
    async def _csrf_token(text: str):
        tree = html.fromstring(text)
        return tree.xpath('//*[@name="csrf-token"]/@content')

    async def get_strava_nickname_from_uri(self, profile_uri: str) -> str:
        """
        If page not found - ''

        :param profile_uri:
        :return:
        """
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

    try:
        yield small_strava
    except Exception as exc:
        logger.error(repr(exc))
    finally:
        await small_strava.close()


async def get_nicknames(strava_obj):
    loop = asyncio.get_event_loop()
    uris_generator = await loop.run_in_executor(None, read_file, 'strava_uris.txt')
    tasks = [asyncio.create_task(strava_obj.get_strava_nickname_from_uri(uri)) for uri in uris_generator]
    results = await asyncio.gather(*tasks)
    print(results, len(results))


async def main():
    _login = os.getenv('LOGIN')
    _password = os.getenv('PASSWORD')

    async with strava_connector(_login, _password) as strava:
        await get_nicknames(strava)


if __name__ == '__main__':
    start = time.time()
    load_dotenv()
    asyncio.run(main())
    end = time.time() - start
    print(end)
