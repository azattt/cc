import json
import asyncio
import logging

import aiofiles

from yaclient.clients import YandexClient, KinopoiskClient
from yaclient.helpers import load_credentials


async def main():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    login, password = await load_credentials("credentials.txt")
    yandex_client = YandexClient()
    yandex_client.create_session()
    await yandex_client.login(login, password)

    print("starting kinopoisk")
    kinopoisk_client = KinopoiskClient(yandex_client)
    kinopoisk_client.create_session()

    await kinopoisk_client.login()
    # print(await kinopoisk_client.do_search("office"))

    office_kphdid = await kinopoisk_client.convert_kp_to_kphd_id(253245)
    print(office_kphdid)
    with open("debug/output.json", "w+", encoding="utf8") as file:
        file.write(
            json.dumps(
                await kinopoisk_client.get_film_children(office_kphdid), indent=4
            )
        )

    desired = "4a769a24279de0beb3bc1307115f383b"
    desired = "4d8e77796bc0a8f199b48f1b408ecdde"

    async with aiofiles.open("debug/output.json", mode="w+", encoding="utf8") as f:
        resp = await kinopoisk_client.get_streams(desired)
        await f.write(json.dumps(resp, indent=4))

    if not JUPYTER:
        await kinopoisk_client.close_session()
        await yandex_client.close_session()
        await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})


JUPYTER = False
CC_DEBUG = True
if __name__ == "__main__":
    asyncio.run(main())
