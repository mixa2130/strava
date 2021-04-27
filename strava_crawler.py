import asyncio
import os
import async_strava

from dotenv import load_dotenv


def read_file(file_name):
    with open(file_name, 'r') as file:
        for row in file:
            yield row.rstrip('\n')


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

    async with async_strava.strava_connector(_login, _password) as strava_obj:
        await get_nicknames(strava_obj)
        # await get_nicknames(strava_obj)
        # await get_nicknames(strava_obj)
        # await get_nicknames(strava_obj)
        # await get_nicknames(strava_obj)


if __name__ == '__main__':
    # start = time.time()

    load_dotenv()
    asyncio.run(main())

    # end = time.time() - start
    # print(end)
