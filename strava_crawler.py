import asyncio
import aiohttp
import os
import time

from bs4 import BeautifulSoup as Bs
from lxml import html
from dotenv import load_dotenv
from async_class import AsyncClass
from typing import NoReturn


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

    async def get_strava_nickname_from_uri(self, profile_uri: str):
        subscriber_russian_athlete = profile_uri.find('Профиль пользователя ')
        if subscriber_russian_athlete != -1:
            return profile_uri[subscriber_russian_athlete + 21:profile_uri.find(' в Strava')]

        subscriber_foreign_athlete = profile_uri.find('Check out ')
        if subscriber_foreign_athlete != -1:
            return profile_uri[subscriber_foreign_athlete + 10:profile_uri.find(' on Strava')]

        response = await self._session.get(profile_uri)
        # if response.status != 200:
        #     raise ConnectionError
        loop = asyncio.get_event_loop()
        soup = await loop.run_in_executor(None, bs_object, await response.text())

        title = soup.select_one('title').text
        return title[(title.find('| ') + 2):]

    async def __adel__(self) -> None:
        await self._session.close()


async def main():
    login = os.getenv('LOGIN')
    password = os.getenv('PASSWORD')

    small_strava = await Strava(login, password)

    loop = asyncio.get_event_loop()
    uris_generator = await loop.run_in_executor(None, read_file, 'strava_uris.txt')
    tasks = [asyncio.create_task(small_strava.get_strava_nickname_from_uri(uri)) for uri in uris_generator]
    results = await asyncio.gather(*tasks)
    print(results, len(results))
    await small_strava.close()


if __name__ == '__main__':
    start = time.time()
    load_dotenv()
    asyncio.run(main())
    end = time.time() - start
    print(end)
