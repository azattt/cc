import re
import asyncio
import aiohttp
import aiofiles
import pathlib


async def save_page(filename: str, request: aiohttp.ClientResponse):
    async with aiofiles.open(
        "debug/" + filename + ".html", "w+", encoding="utf8"
    ) as file:
        await file.write(await request.text())


async def load_credentials(filename: str) -> list[str, str]:
    async with aiofiles.open(filename) as file:
        login = await file.readline()
        password = await file.readline()
    return (login, password)


class YandexCaptcha:
    def __init__(self, url: str):
        pass

    def download(self, path: str):
        pass


class YandexClient:
    FAKE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36 OPR/89.0.4447.83"

    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.session.headers.update({"user-agent": YandexClient.FAKE_USER_AGENT})

    def save_cookies(self, path: str):
        self.session.cookie_jar.save(path)

    def load_cookies(self, path: str):
        self.session.cookie_jar.load(path)

    async def raise_and_exit(self, exc: Exception):
        await self.close()
        raise exc

    async def check_login(self):
        async with self.session.get("https://passport.yandex.ru") as resp:
            if "profile" in str(resp.url):
                return True
            elif "auth" in str(resp.url):
                return False
            else:
                await self.raise_and_exit(RuntimeError("Unexpected URL"))

    async def _download_captcha(self, url):
        async with self.session.get(url) as resp:
            f = await aiofiles.open("debug/captcha.jpg", mode="wb+")
            await f.write(await resp.read())
            await f.close()

    async def login_yandex(self, login, password):
        # TODO: support for two-factor authentication
        auth_data = {"login": login, "passwd": password}
        async with self.session.post(
            "https://passport.yandex.ru/auth", data=auth_data
        ) as resp:
            await save_page("passport.yandex.ru_auth", resp)
            resp_text = await resp.text()
            if "challenge" in str(resp.url):
                resp_text = await resp.text()
                phoneId_found = re.findall(r"(?<=\"phoneId\":).*?(?=})", resp_text)
                csrf_found = re.findall(r"(?<=\"csrf\":\").*?(?=\")", resp_text)
                track_id_found = re.findall(r"(?<=\"track_id\":\").*?(?=\")", resp_text)
                if not phoneId_found or not csrf_found or not track_id_found:
                    raise RuntimeError(
                        "Challenge: phoneId_found, csrf_found or track_id_found are not found"
                    )
                await self.session.post(
                    "https://passport.yandex.ru/registration-validations/auth/validate_phone_by_id",
                    data={
                        "phoneId": phoneId_found[0],
                        "csrf_token": csrf_found[0],
                        "track_id": track_id_found[0],
                    },
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
                await self.session.post(
                    "https://passport.yandex.ru/registration-validations/phone-confirm-code-submit",
                    data={
                        "phone_id": phoneId_found[0],
                        "csrf_token": csrf_found[0],
                        "track_id": track_id_found[0],
                        "confirm_method": "by_sms",
                        "isCodeWithFormat": "true",
                    },
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
                code_input = input("Enter code from SMS:")
                await self.session.post(
                    "https://passport.yandex.ru/registration-validations/phone-confirm-code",
                    data={
                        "code": code_input,
                        "csrf_token": csrf_found[0],
                        "track_id": track_id_found[0],
                    },
                    headers={"X-Requested-With": "XMLHttpRequest"},
                )
            elif "js-domik-captcha" in resp_text:
                while True:
                    captcha_url_found = re.findall(
                        r"(?<=t\" src=\").*?(?=\")", resp_text
                    )
                    if not captcha_url_found:
                        await self.raise_and_exit(
                            RuntimeError("Captcha URL not found in HTML")
                        )
                    await self._download_captcha(captcha_url_found[0])
                    captcha_input = input("Captcha: ")
                    auth_data.update(
                        {
                            "answer": captcha_input,
                            "key": captcha_url_found[0][-32:],
                        }
                    )
                    result = await self.session.post(
                        "https://passport.yandex.ru/auth", data=auth_data
                    )
                    print(result)

    async def login_kinopoisk(self):
        # kinopoisk_auth = await self.session.post(
        #     "https://passport.yandex.ru/auth?origin=kinopoisk"
        # )
        # await save_page("kino", kinopoisk_auth)
        async with self.session.get(
            "https://hd.kinopoisk.ru/",
            headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "pragma": "no-cache",
                "sec-ch-ua": '"Opera";v="89", "Chromium";v="103", "_Not:A-Brand";v="24"',
            },
        ) as kinopoisk_request:
            print(
                kinopoisk_request.url,
                kinopoisk_request.url == kinopoisk_request.real_url,
                len(str(kinopoisk_request.url)),
            )
            if kinopoisk_request.status != 200:
                await save_page("fail", kinopoisk_request)
                await self.close()
                await self.raise_and_exit(
                    RuntimeError(
                        '"https://hd.kinopoisk.ru" didn\'t return 200. Maybe you are not logged in Yandex.'
                    )
                )

            # if "captcha" in kinopoisk_request.url:
            #     captcha_url_found = re.findall(
            #         r"(?<=action=\").*?(?=\")", kinopoisk_request.text)
            #     if not captcha_url_found:
            #         raise RuntimeError("Captcha error: no captcha url")
            #     captcha_url = captcha_url_found[0]
            #     showcaptcha = self.session.post(
            #         "https://hd.kinopoisk.ru"+captcha_url)
            #     captcha_image_found = re.findall(
            #         r"(?<=src\=\"http://hd.kinopoisk.ru/captchaimg\?).*?(?=\")", showcaptcha.text)
            #     if not captcha_image_found:
            #         raise RuntimeError("Captcha image not found")
            #     captcha_image_url = captcha_image_found[0]

    async def close(self):
        await self.session.close()


async def main():
    login, password = await load_credentials("credentials.txt")
    client = YandexClient()
    # print("Trying to find cookies file...")
    # try:
    #     client.load_cookies("debug/test.bin")
    # except FileNotFoundError:
    #     print("Didn't find the file with cookies, need to login again...")
    #     await client.login_yandex(login, password)
    #     client.save_cookies("debug/test.bin")
    # else:
    #     print("Found the file with cookies")
    #     if not await client.check_login():
    #         print("Cookies are outdated, need to login again.")
    #         await client.login_yandex(login, password)
    #     else:
    #         print("Cookies are relevant, no need to login again.")
    # print("Successfully logined")

    await client.login_kinopoisk()
    await client.close()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
