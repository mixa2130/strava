"""An example of using Strava.get_strava_nickname_from_uri from async_class package"""
import asyncio
import os

from typing import List, NoReturn
from dotenv import load_dotenv
# from async_strava.attributes import Activity, ActivityValues
# import datetime
# import async_strava
from async_strava import strava_connector, write_club_activities_to_file, Strava


def read_file(file_name='strava_uris.txt'):
    """
    Generator, which yield's file line by line

    :param file_name: file path
    """
    with open(file_name, 'r') as file:
        for row in file:
            yield row.rstrip('\n')


async def get_nicknames(strava_obj) -> List[str]:
    """
    Asynchronously retrieves nicknames from links in a 'strava_uris.txt' file

    :param strava_obj: instance of the Strava class

    :return: list of users nicknames, if uri is invalid - item will be ''
    """
    semaphore = asyncio.Semaphore(200)  # works as a resource counter
    async with semaphore:
        uris_generator = read_file()
        tasks = [asyncio.create_task(strava_obj.get_strava_nickname_from_uri(uri)) for uri in uris_generator]

        results: list = await asyncio.gather(*tasks)
        return results


async def main() -> NoReturn:
    """Example executor"""
    _login: str = os.getenv('LOGIN')
    _password: str = os.getenv('PASSWORD')

    async with strava_connector(_login, _password) as strava_obj:
        nicknames: list = await get_nicknames(strava_obj)
        print(nicknames)


if __name__ == '__main__':
    load_dotenv()

    asyncio.run(main())
