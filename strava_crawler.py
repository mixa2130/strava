import asyncio
import aiohttp
from bs4 import BeautifulSoup as Bs
from lxml import html
from dotenv import load_dotenv
import os
import time


def read_file(file_name):
    with open(file_name, 'r') as file:
        for row in file:
            yield row.rstrip('\n')


def bs_object(text):
    return Bs(text, 'html.parser')


async def get_html(session, uri):
    response = await session.get(uri)
    return await response.text()


async def csrf_token(text):
    tree = html.fromstring(text)
    return tree.xpath('//*[@name="csrf-token"]/@content')


async def registration(session, strava_login, strava_password):
    html_text = await get_html(session, 'https://www.strava.com/login')
    token = await csrf_token(html_text)

    parameters = {'authenticity_token': token[0],
                  'email': strava_login,
                  'password': strava_password
                  }

    await session.post('https://www.strava.com/session', data=parameters)


async def get_strava_nickname_from_url(session, profile_url):
    subscriber_russian_athlete = profile_url.find('Профиль пользователя ')
    if subscriber_russian_athlete != -1:
        return profile_url[subscriber_russian_athlete + 21:profile_url.find(' в Strava')]

    subscriber_foreign_athlete = profile_url.find('Check out ')
    if subscriber_foreign_athlete != -1:
        return profile_url[subscriber_foreign_athlete + 10:profile_url.find(' on Strava')]

    # function can take not only url, but already a ready-made nickname
    url_start_index = profile_url.find('https://www.strava.com/athletes/')

    if url_start_index != -1:
        url = profile_url[url_start_index:len(profile_url)]

        response = await session.get(url)
        # print(url)
        # print(response.status)
        # if response.status != 200:
        #     raise ConnectionError
        loop = asyncio.get_event_loop()
        soup = await loop.run_in_executor(None, bs_object, await response.text())
        #     soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.select_one('title').text
        # print(title[(title.find('| ') + 2):])
        return title[(title.find('| ') + 2):]
    # print(profile_url.strip())
    return profile_url.strip()


async def get_strava_nicknames(session):
    loop = asyncio.get_event_loop()
    uris_generator = await loop.run_in_executor(None, read_file, 'strava_uris.txt')
    tasks = [asyncio.create_task(get_strava_nickname_from_url(session, uri)) for uri in uris_generator]
    results = await asyncio.gather(*tasks)
    # print(results)
    return results
    # for i in uris_generator:
    #     print(i)


async def main():
    print(f'start: {time.time()}')
    login = os.getenv('LOGIN')
    password = os.getenv('PASSWORD')

    async with aiohttp.ClientSession() as session:
        await registration(session, login, password)
        data = await get_strava_nicknames(session)
        print(data)
        print(len(data))
        print(f'end: {time.time()}')


if __name__ == '__main__':
    load_dotenv()
    asyncio.run(main())
