import json
import re
import asyncio
import logging
import sys
import uuid
import aiohttp
import aiofiles


async def save_page(filename: str, request: aiohttp.ClientResponse):
    async with aiofiles.open(
        "debug/" + filename + ".html", "w+", encoding="utf8"
    ) as file:
        await file.write(await request.text())


async def load_credentials(filename: str) -> list[str, str]:
    async with aiofiles.open(filename) as file:
        login = (await file.readline()).strip()
        password = (await file.readline()).strip()
    return (login, password)


async def ainput(string: str) -> str:
    if JUPYTER:
        print(string, end="")
        return await global_queue.get()
    await asyncio.get_event_loop().run_in_executor(
        None, lambda s=string: sys.stdout.write(s + " ")
    )
    return await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)


async def i(s):
    await global_queue.put(s)


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
        self.cookie_save_path = "debug/cookie.bin"
        self.logger = logging.getLogger()
        self.kinopoisk_retries = 10

    async def save_cookies(self):
        await asyncio.get_event_loop().run_in_executor(
            None, self.session.cookie_jar.save, self.cookie_save_path
        )

    async def load_cookies(self):
        await asyncio.get_event_loop().run_in_executor(
            None, self.session.cookie_jar.load, self.cookie_save_path
        )

    async def captcha_proof_request(
        self,
    ):
        self.raise_and_exit(NotImplementedError("Not implemented yet"))

    async def _handle_challenge(self, resp: aiohttp.ClientResponse):
        self.raise_and_exit(RuntimeError("challenge"))
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
        while True:
            code_input = await input("Enter code from SMS:")
            code_confirm_resp = await self.session.post(
                "https://passport.yandex.ru/registration-validations/phone-confirm-code",
                data={
                    "code": code_input,
                    "csrf_token": csrf_found[0],
                    "track_id": track_id_found[0],
                },
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            code_confirm_json = await code_confirm_resp.json()
            if code_confirm_json["status"] == "ok":
                asyncio.create_task(self.save_cookies())
                return
            if code_confirm_json["status"] == "error" and code_confirm_json[
                "errors"
            ] == ["code.invalid"]:
                continue
            self.raise_and_exit(RuntimeError(f"Unexpected error {code_confirm_json}"))

    async def _handle_kinopoisk_captcha(self, req: aiohttp.ClientResponse):
        captcha_url_found = re.findall(r"(?<=action=\").*?(?=\")", await req.text())
        if not captcha_url_found:
            await self.raise_and_exit(RuntimeError("Captcha error: no captcha url"))
        captcha_url = captcha_url_found[0]
        showcaptcha = await self.session.post("http://kinopoisk.ru" + captcha_url)
        showcaptcha_text = await showcaptcha.text()
        captcha_image_found = re.findall(
            r"(?<=src\=\"http://kinopoisk.ru/captchaimg\?).*?(?=\")",
            showcaptcha_text,
        )
        if not captcha_image_found:
            await self.raise_and_exit(RuntimeError("Captcha image not found"))
        captcha_image_url = captcha_image_found[0]
        await self._download_captcha(
            "http://kinopoisk.ru/captchaimg?" + captcha_image_url
        )
        captcha_input = await ainput("Enter captcha:")
        print("got")
        checkcaptcha_found = re.findall(
            r"(?<=checkcaptcha\?).*?(?=\")", showcaptcha_text
        )
        aesKey_found = re.findall(r"(?<=aesKey:\").*?(?=\")", showcaptcha_text)
        signKey_found = re.findall(r"(?<=aesSign:\").*?(?=\")", showcaptcha_text)
        if not checkcaptcha_found or not aesKey_found or not signKey_found:
            await self.raise_and_exit(
                RuntimeError(
                    "not checkcaptcha_found or not aesKey_found or not signKey_found"
                )
            )
        checkcaptcha = await self.session.get(
            "http://kinopoisk.ru/checkcaptcha?" + checkcaptcha_found[0],
            data={
                "rep": captcha_input,
                "aesKey": aesKey_found[0],
                "signKey": signKey_found[0],
            },
            params={"rep": captcha_input},
        )
        if str(checkcaptcha.url) != "https://www.kinopoisk.ru/":
            self.raise_and_exit(NotImplementedError("Unlucky :( , try again..."))

    async def raise_and_exit(self, exc: Exception):
        await self.close()
        raise exc

    async def check_yandex_login(self):
        async with self.session.get("https://passport.yandex.ru") as resp:
            if "profile" in str(resp.url):
                return True
            if "auth" in str(resp.url):
                return False
            await self.raise_and_exit(RuntimeError("Unexpected URL"))

    async def check_kinopoisk_login(self):
        async with self.session.get("http://hd.kinopoisk.ru/personal") as resp:
            if "personal" in str(resp.url):
                return True
            return False

    async def _download_captcha(self, url):
        async with self.session.get(url) as resp:
            f = await aiofiles.open("debug/captcha.jpg", mode="wb+")
            await f.write(await resp.read())
            await f.close()

    async def login_yandex(self, login, password):
        # TODO: support for two-factor authentication
        try:
            await self.load_cookies()
        except FileNotFoundError:
            pass
        except EOFError:
            self.logger.warning("Cookie file may be corrupted", exc_info=1)
        else:
            is_logined = await self.check_yandex_login()
            if is_logined:
                return

        auth_data = {"login": login, "passwd": password}
        initial_visit_resp = await self.session.post(
            "https://passport.yandex.ru/auth", data=auth_data
        )
        resp_text = await initial_visit_resp.text()
        if "challenge" in str(initial_visit_resp.url):
            await self._handle_challenge(initial_visit_resp)
        elif "Нет аккаунта" in resp_text:
            await self.raise_and_exit(RuntimeError("Wrong credentials (login)"))
        elif "Неправильный логин" in resp_text:
            await self.raise_and_exit(RuntimeError("Wrong credentials (password)"))
        elif "js-domik-captcha" in resp_text:
            await save_page("test", initial_visit_resp)
            while True:
                captcha_url_found = re.findall(r"(?<=t\" src=\").*?(?=\")", resp_text)
                if not captcha_url_found:
                    await self.raise_and_exit(
                        RuntimeError("Captcha URL not found in HTML")
                    )
                await self._download_captcha(captcha_url_found[0])
                track_id_found = resp_text.split('" name="track_id')[0].split('"')[-1]
                if not track_id_found:
                    await self.raise_and_exit(RuntimeError("track_id not found"))
                captcha_input = await ainput("Enter captcha:")
                auth_data.update(
                    {
                        "answer": captcha_input,
                        "key": captcha_url_found[0][-32:],
                        "track_id": track_id_found,
                        "captcha_mode": "text",
                        "state": "submit",
                    }
                )
                visit_resp = await self.session.post(
                    "https://passport.yandex.ru/auth", data=auth_data
                )
                resp_text = await visit_resp.text()
                await save_page("test1", visit_resp)
                if "Нет аккаунта" in resp_text:
                    await self.raise_and_exit(RuntimeError("Wrong credentials (login)"))
                elif "Неправильный логин или пароль" in resp_text:
                    await self.raise_and_exit(
                        RuntimeError("Wrong credentials (password)")
                    )
                elif "Вы неверно ввели символы" in resp_text:
                    # wrong captcha
                    continue
                elif "profile" in str(visit_resp.url):
                    # means success
                    asyncio.create_task(self.save_cookies())
                    break
                else:
                    await self.raise_and_exit(RuntimeError("Unknown error"))
        else:
            # means success
            asyncio.create_task(self.save_cookies())

    async def login_kinopoisk(self):
        try:
            await self.load_cookies()
        except FileNotFoundError:
            pass
        except EOFError:
            pass
        else:
            if await self.check_kinopoisk_login():
                pass

        kinopoisk_request = await self.session.get("http://kinopoisk.ru/")

        if kinopoisk_request.status != 200:
            await save_page("fail", kinopoisk_request)
            await self.raise_and_exit(
                RuntimeError('"http://kinopoisk.ru" didn\'t return 200')
            )

        if "captcha" in str(kinopoisk_request.url):
            self._handle_kinopoisk_captcha(kinopoisk_request)

        r = await client.session.get(
            "https://passport.yandex.ru/auth?origin=kinopoisk&retpath=https%3A%2F%2Fsso.passport.yandex.ru%2Fpush%3Fretpath%3Dhttps%253A%252F%252Fwww.kinopoisk.ru%252Fapi%252Fprofile-pending%252F%253Fretpath%253Dhttps%25253A%25252F%25252Fwww.kinopoisk.ru%25252F%26"
        )
        await save_page("sso", r)
        r_text = await r.text()
        sso_found = r_text.split("https://sso.passport.yandex.ru/push")[1].split('"')[0]
        if not sso_found:
            raise RuntimeError("sso not found")
        my_uuid = uuid.uuid4()
        sso_found = sso_found.replace("&amp;", "&uuid=" + str(my_uuid))
        r1 = await client.session.get("https://sso.passport.yandex.ru/push" + sso_found)
        await save_page("sso1", r1)
        element_2_found = (await r1.text()).split("element2.value = '")[1].split("'")[0]
        r2 = await client.session.post(
            "https://sso.kinopoisk.ru/install?uuid=" + str(my_uuid),
            data={
                "retpath": "https://www.kinopoisk.ru/api/profile-pending/?retpath=https%3A%2F%2Fwww.kinopoisk.ru%2F",
                "container": element_2_found,
            },
        )
        await save_page("sso2", r2)
        r3 = await client.session.get(
            "http://www.kinopoisk.ru/api/profile-pending/?retpath=https%3A%2F%2Fwww.kinopoisk.ru%2F"
        )
        await save_page("sso3", r3)

        asyncio.create_task(self.save_cookies())

    async def close(self):
        await self.session.close()


client = 0
global_queue = asyncio.Queue()


async def main():
    global client
    # logger = logging.getLogger()
    # logger.setLevel(logging.DEBUG)
    # ch = logging.StreamHandler()
    # ch.setLevel(logging.DEBUG)
    # formatter = logging.Formatter(
    #     "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # )
    # ch.setFormatter(formatter)
    # logger.addHandler(ch)
    # logging.getLogger("asyncio").setLevel(logging.WARNING)

    login, password = await load_credentials("credentials.txt")
    client = YandexClient()
    await client.login_yandex(login, password)
    print("starting kinopoisk")
    await client.login_kinopoisk()

    r2 = await client.session.get("https://www.kinopoisk.ru/api/mda-status/")
    await save_page("sso4", r2)
    if not JUPYTER:
        await client.close()
        await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})


JUPYTER = False
if __name__ == "__main__":
    print("__main__")
    asyncio.run(main())
