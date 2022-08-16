import copy
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


class YaClient:
    def __init__(self, cookie_save_path: str = "cookie.bin") -> None:
        self.session: aiohttp.ClientSession
        self.cookie_save_path = cookie_save_path
        self.logger: logging.Logger

    def create_session(self, user_agent: str) -> aiohttp.ClientSession:
        session = aiohttp.ClientSession()
        session.headers.update({"user-agent": user_agent})
        return session

    async def close_session(self):
        await self.session.close()

    async def save_cookies(self):
        await asyncio.get_event_loop().run_in_executor(
            None, self.session.cookie_jar.save, self.cookie_save_path
        )

    async def load_cookies(self):
        await asyncio.get_event_loop().run_in_executor(
            None, self.session.cookie_jar.load, self.cookie_save_path
        )

    async def _download_captcha(self, url):
        async with self.session.get(url) as resp:
            f = await aiofiles.open("debug/captcha.jpg", mode="wb+")
            await f.write(await resp.read())
            await f.close()

    async def raise_and_exit(self, exc: Exception):
        await self.close_session()
        raise exc


class YandexClient(YaClient):
    FAKE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36 OPR/89.0.4447.83"

    def __init__(self, user_agent: str = FAKE_USER_AGENT):
        super().__init__()
        self.logger = logging.getLogger("yandex_client")
        self.kinopoisk_retries = 10
        self.session = self.create_session(user_agent)
        self.user_agent = user_agent

    async def captcha_proof_request(
        self,
    ):
        self.raise_and_exit(NotImplementedError("Not implemented yet"))

    async def _handle_challenge(self, resp: aiohttp.ClientResponse):
        resp_text = await resp.text()
        phoneId_found = re.findall(r"(?<=\"phoneId\":).*?(?=})", resp_text)
        csrf_found = re.findall(r"(?<=\"csrf\":\").*?(?=\")", resp_text)
        track_id_found = re.findall(r"(?<=\"track_id\":\").*?(?=\")", resp_text)
        if not phoneId_found or not csrf_found or not track_id_found:
            raise RuntimeError(
                "Challenge: phoneId_found, csrf_found or track_id_found are not found"
            )

        validate_phone_by_id = await self.session.post(
            "https://passport.yandex.ru/registration-validations/auth/validate_phone_by_id",
            data={
                "phoneId": phoneId_found[0],
                "csrf_token": csrf_found[0],
                "track_id": track_id_found[0],
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        validate_phone_by_id_json = await validate_phone_by_id.json()
        if validate_phone_by_id_json["status"] != "ok":
            await self.raise_and_exit(
                RuntimeError('Challenge: "validate_phone_by_id" status != ok')
            )
        code_submit = await self.session.post(
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
        code_submit_json = await code_submit.json()
        if code_submit_json["status"] != "ok":
            await self.raise_and_exit(
                RuntimeError('Challenge: "code_submit" status != ok')
            )
        while True:
            code_input = await ainput("Enter code from SMS:")
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

    async def check_login(self):
        async with self.session.get(
            "https://api.passport.yandex.ru/all_accounts"
        ) as resp:
            resp_json = await resp.json()
            if "accounts" not in resp_json:
                return False
            if resp_json["accounts"]:
                return True
            if CC_DEBUG:
                await save_page("error", resp)
            await self.raise_and_exit(RuntimeError("Unexpected response"))

    async def login(self, login, password):
        # TODO: support for two-factor authentication
        try:
            await self.load_cookies()
        except FileNotFoundError:
            self.logger.warning("Cookie file not found", exc_info=1)
        except EOFError:
            self.logger.warning("Cookie file may be corrupted", exc_info=1)
        else:
            is_logined = await self.check_login()
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


class KinopoiskClient(YaClient):
    FAKE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36 OPR/89.0.4447.83"

    def __init__(self, yandex_client_already_logined: YandexClient) -> None:
        super().__init__()
        self.kinopoisk_retries = 10
        self.logger = logging.getLogger("kinopoisk_client")
        self.bound_yandex_client = yandex_client_already_logined
        self.session = self.create_session(yandex_client_already_logined.user_agent)
        self.session.cookie_jar._cookies = copy.deepcopy(
            yandex_client_already_logined.session.cookie_jar._cookies
        )

    async def check_login(self):
        async with self.session.get("https://www.kinopoisk.ru/api/mda-status/") as resp:
            resp_json = await resp.json()
            if resp_json["sessionStatus"]:
                return True
            return False

    async def login(self):
        try:
            await self.load_cookies()
        except FileNotFoundError:
            pass
        except EOFError:
            pass
        else:
            if await self.check_login():
                return

        for i in range(self.kinopoisk_retries):
            kinopoisk_request = await self.session.get("http://kinopoisk.ru/")
            if kinopoisk_request.status == 200:
                if i != 0:
                    self.logger.warning(
                        "Kinopoisk request succeded only from %i-th retry", i + 1
                    )
                break
        else:
            if kinopoisk_request.status != 200:
                await save_page("fail", kinopoisk_request)
                await self.raise_and_exit(
                    RuntimeError('"http://kinopoisk.ru" didn\'t return 200')
                )

        await self._handle_captcha(kinopoisk_request)

        auth = await self.session.get(
            "https://passport.yandex.ru/auth?origin=kinopoisk&retpath=https%3A%2F%2Fsso.passport.yandex.ru%2Fpush%3Fretpath%3Dhttps%253A%252F%252Fwww.kinopoisk.ru%252Fapi%252Fprofile-pending%252F%253Fretpath%253Dhttps%25253A%25252F%25252Fwww.kinopoisk.ru%25252F%26"
        )
        auth_text = await auth.text()
        sso_found = auth_text.split("https://sso.passport.yandex.ru/push")[1].split(
            '"'
        )[0]
        if not sso_found:
            self.raise_and_exit(RuntimeError("sso not found"))
        my_uuid = uuid.uuid4()
        sso_found = sso_found.replace("&amp;", "&uuid=" + str(my_uuid))
        sso_push = await self.session.get(
            "https://sso.passport.yandex.ru/push" + sso_found
        )
        try:
            container_found = (
                (await sso_push.text()).split("element2.value = '")[1].split("'")[0]
            )
        except IndexError:
            self.raise_and_exit(
                RuntimeError(
                    "Kinopoisk login: couldn't find container for https://sso.kinopoisk.ru/install"
                )
            )

        install = await self.session.post(
            "https://sso.kinopoisk.ru/install?uuid=" + str(my_uuid),
            data={
                "retpath": "https://www.kinopoisk.ru/api/profile-pending/?retpath=https%3A%2F%2Fwww.kinopoisk.ru%2F",
                "container": container_found,
            },
        )
        if install.status != 200:
            self.raise_and_exit(
                RuntimeError(
                    "Kinopoisk login: https://sso.kinopoisk.ru/install didn't return status 200"
                )
            )
        final_auth = await self.session.get(
            "http://www.kinopoisk.ru/api/profile-pending/?retpath=https%3A%2F%2Fwww.kinopoisk.ru%2F"
        )
        if final_auth.status != 200:
            await self.raise_and_exit(
                RuntimeError(
                    "Kinopoisk login: final auth request didn't return status 200"
                )
            )
        asyncio.create_task(self.save_cookies())

    async def _handle_captcha(self, req: aiohttp.ClientResponse):
        if "captcha" not in str(req.url):
            return

        while True:
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
            captcha_input = await ainput("Enter captcha:")
            checkcaptcha = await self.session.get(
                "http://kinopoisk.ru/checkcaptcha?" + checkcaptcha_found[0],
                data={
                    "rep": captcha_input,
                    "aesKey": aesKey_found[0],
                    "signKey": signKey_found[0],
                },
                params={"rep": captcha_input},
            )
            if "showcaptcha" in str(checkcaptcha.url):
                req = checkcaptcha
                continue
            if str(checkcaptcha.url) == "https://www.kinopoisk.ru/":
                break
            await self.raise_and_exit(
                RuntimeError(
                    f"Kinopoisk login captcha: unexpected response {checkcaptcha.url}"
                )
            )
        return req


client = 0
global_queue = asyncio.Queue()


async def main():
    global client
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
    await yandex_client.login(login, password)
    print("starting kinopoisk")
    kinopoisk_client = KinopoiskClient(yandex_client)
    await kinopoisk_client.login()
    print(
        await (
            await kinopoisk_client.session.get(
                "https://api.ott.kinopoisk.ru/v12/profiles/me?serviceId=25"
            )
        ).text()
    )

    if not JUPYTER:
        await kinopoisk_client.close_session()
        await yandex_client.close_session()
        await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})


JUPYTER = False
CC_DEBUG = True
if __name__ == "__main__":
    print("__main__")
    asyncio.run(main())
