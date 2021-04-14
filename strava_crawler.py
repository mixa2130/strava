import asyncio
import aiohttp
from bs4 import BeautifulSoup as Bs
from lxml import html
from dotenv import load_dotenv
import os


# def html_writer(text: str):
#     with open('page.html', 'w') as file:
#         file.write(text)


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


async def main():
    login = os.getenv('LOGIN')
    password = os.getenv('PASSWORD')

    async with aiohttp.ClientSession() as session:
        await registration(session, login, password)


if __name__ == '__main__':
    load_dotenv()
    asyncio.run(main())
