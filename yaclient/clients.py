"""Clients to interact with Yandex services"""
import logging
import re
import asyncio
import copy
import uuid

import aiohttp
import aiofiles

from yaclient.helpers import ainput, save_page
from yaclient.exceptions import LicenseNotApprovedError, WrongCredentialsError

STATUS_OK = 0
STATUS_CAPTCHA = 1
STATUS_WRONG_CAPTCHA = 2


class YaClient:
    def __init__(self, save_cookies: bool = True, cookie_save_path: str = "cookie.bin"):
        self.session: aiohttp.ClientSession
        self.cookie_save_path = cookie_save_path
        self.logger: logging.Logger
        self.user_agent: str
        self.save_cookies: bool = save_cookies

    async def create_session(self, trace_configs: list[aiohttp.TraceConfig] = None):
        self.session = aiohttp.ClientSession(trace_configs=trace_configs)
        self.session.headers.update({"user-agent": self.user_agent})

    async def close_session(self):
        await self.session.close()

    async def do_save_cookies(self):
        if self.save_cookies:
            await asyncio.get_event_loop().run_in_executor(
                None, self.session.cookie_jar.save, self.cookie_save_path
            )

    async def load_cookies(self):
        await asyncio.get_event_loop().run_in_executor(
            None, self.session.cookie_jar.load, self.cookie_save_path
        )

    async def _download_captcha(self, url: str):
        async with self.session.get(url) as resp:
            async with aiofiles.open("debug/captcha.jpg", mode="wb+") as f:
                await f.write(await resp.read())


class YandexClient(YaClient):
    FAKE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36 OPR/89.0.4447.83"

    def __init__(self, save_cookies: bool = True, user_agent: str = FAKE_USER_AGENT):
        super().__init__(save_cookies=save_cookies)
        self.kinopoisk_retries = 10
        self.user_agent = user_agent
        self.input_mode = ainput
        self.debug = False
        self.logger = logging.getLogger("YandexClient")

    async def handle_challenge(self, data: dict):
        validate_phone_by_id = await self.session.post(
            data["url"],
            data=data["data"],
            headers=data["headers"],
        )
        validate_phone_by_id_json = await validate_phone_by_id.json()
        if validate_phone_by_id_json["status"] != "ok":
            raise RuntimeError('Challenge: "validate_phone_by_id" status != ok')
        code_submit = await self.session.post(
            "https://passport.yandex.ru/registration-validations/phone-confirm-code-submit",
            data={
                **data["data"],
                "confirm_method": "by_sms",
                "isCodeWithFormat": "true",
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        code_submit_json = await code_submit.json()
        if code_submit_json["status"] != "ok":
            raise RuntimeError('Challenge: "code_submit" status != ok')

        while True:
            code_input = await ainput("Enter code from SMS:")
            code_confirm_resp = await self.session.post(
                "https://passport.yandex.ru/registration-validations/phone-confirm-code",
                data={
                    "code": code_input,
                    "csrf_token": data["csrf_token"],
                    "track_id": data["track_id"],
                },
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            code_confirm_json = await code_confirm_resp.json()
            if code_confirm_json["status"] == "ok":
                asyncio.create_task(self.do_save_cookies())
                return
            if code_confirm_json["status"] == "error" and code_confirm_json[
                "errors"
            ] == ["code.invalid"]:
                continue
            raise RuntimeError(f"Unexpected error {code_confirm_json}")

    async def check_login(self):
        async with self.session.get(
            "https://api.passport.yandex.ru/all_accounts"
        ) as resp:
            resp_json = await resp.json()
            if "accounts" not in resp_json:
                return False
            if resp_json["accounts"]:
                return True
            if self.debug:
                await save_page("error", resp)
            raise RuntimeError("Unexpected response")

    async def try_login(self, login, password):
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
                return 0

        auth_data = {"login": login, "passwd": password}
        initial_visit_resp = await self.session.post(
            "https://passport.yandex.ru/auth", data=auth_data
        )
        resp_text = await initial_visit_resp.text()
        if "challenge" in str(initial_visit_resp.url):
            self.logger.info("Challenge from Yandex")
            phoneId_found = re.findall(r"(?<=\"phoneId\":).*?(?=})", resp_text)
            csrf_found = re.findall(r"(?<=\"csrf\":\").*?(?=\")", resp_text)
            track_id_found = re.findall(r"(?<=\"track_id\":\").*?(?=\")", resp_text)
            if not phoneId_found or not csrf_found or not track_id_found:
                raise RuntimeError(
                    "Challenge: phoneId_found, csrf_found or track_id_found are not found"
                )
            return {
                "type": "challenge",
                "url": "https://passport.yandex.ru/registration-validations/auth/validate_phone_by_id",
                "headers": {"X-Requested-With": "XMLHttpRequest"},
                "data": {
                    "phoneId": phoneId_found[0],
                    "csrf_token": csrf_found[0],
                    "track_id": track_id_found[0],
                },
            }
        if "Нет аккаунта" in resp_text:
            self.logger.info("Wrong credentials (login)")
            raise WrongCredentialsError("Wrong credentials (login)")
        if "Неправильный логин" in resp_text:
            self.logger.info("Wrong credentials (password)")
            raise WrongCredentialsError("Wrong credentials (password)")
        if "js-domik-captcha" in resp_text:
            self.logger.info("Yandex captcha")
            captcha_url_found = re.findall(r"(?<=t\" src=\").*?(?=\")", resp_text)
            track_id_found = resp_text.split('" name="track_id')[0].split('"')[-1]
            if not track_id_found:
                raise RuntimeError("track_id not found")
            if not captcha_url_found:
                raise RuntimeError("Captcha URL not found in HTML")

            auth_data.update(
                {
                    "key": captcha_url_found[0][-32:],
                    "track_id": track_id_found,
                    "captcha_mode": "text",
                    "state": "submit",
                }
            )

            return {
                "type": "js-domik-captcha",
                "captchaUrl": captcha_url_found[0],
                "url": "https://passport.yandex.ru/auth",
                "data": auth_data,
            }
        # success
        asyncio.create_task(self.do_save_cookies())
        return 0

    async def continue_captcha(self, data: dict, captcha_input: str):
        data["answer"] = captcha_input

        resp = await self.session.post(
            "https://passport.yandex.ru/auth", data=data["data"]
        )
        resp_text = await resp.text()
        if "Нет аккаунта" in resp_text:
            raise WrongCredentialsError("Wrong credentials (login)")
        if "Неправильный логин или пароль" in resp_text:
            raise WrongCredentialsError("Wrong credentials (password)")
        if "Вы неверно ввели символы" in resp_text:
            # wrong captcha
            return STATUS_WRONG_CAPTCHA
        if "profile" in str(resp.url):
            # means success
            asyncio.create_task(self.do_save_cookies())
            return 0

        raise RuntimeError(f"Unknown error {str(resp.url)}")


class KinopoiskClient(YaClient):
    FAKE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36 OPR/89.0.4447.83"

    def __init__(
        self,
        yandex_client_already_logined: YandexClient,
        save_cookies: bool = True,
        trace_configs: list[aiohttp.TraceConfig] = None,
    ) -> None:
        super().__init__(save_cookies=save_cookies)
        self.kinopoisk_retries = 10
        self.parent_yandex_client = yandex_client_already_logined
        self.trace_configs = trace_configs
        self.user_agent = yandex_client_already_logined.user_agent
        self.schemas_directory = "graphql_schema/"
        self.graphql_schemas: dict[str, str] = {}
        self.logger = logging.getLogger("KinopoiskClient")

    async def create_session(self, trace_configs: list[aiohttp.TraceConfig] = None):
        await super().create_session(trace_configs=trace_configs)
        self.session.cookie_jar._cookies = copy.deepcopy(
            self.parent_yandex_client.session.cookie_jar._cookies
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
                raise RuntimeError('"http://kinopoisk.ru" didn\'t return 200')

        captcha_info = await self._handle_captcha(kinopoisk_request)

        auth = await self.session.get(
            "https://passport.yandex.ru/auth?origin=kinopoisk&retpath=https%3A%2F%2Fsso.passport.yandex.ru%2Fpush%3Fretpath%3Dhttps%253A%252F%252Fwww.kinopoisk.ru%252Fapi%252Fprofile-pending%252F%253Fretpath%253Dhttps%25253A%25252F%25252Fwww.kinopoisk.ru%25252F%26"
        )
        auth_text = await auth.text()
        sso_found = auth_text.split("https://sso.passport.yandex.ru/push")[1].split(
            '"'
        )[0]
        if not sso_found:
            raise RuntimeError("sso not found")
        my_uuid = uuid.uuid4()
        sso_found = sso_found.replace("&amp;", "&uuid=" + str(my_uuid))
        sso_push = await self.session.get(
            "https://sso.passport.yandex.ru/push" + sso_found
        )
        try:
            container_found = (
                (await sso_push.text()).split("element2.value = '")[1].split("'")[0]
            )
        except IndexError as exc:
            raise RuntimeError(
                "Kinopoisk login: couldn't find container for https://sso.kinopoisk.ru/install"
            ) from exc

        install = await self.session.post(
            "https://sso.kinopoisk.ru/install?uuid=" + str(my_uuid),
            data={
                "retpath": "https://www.kinopoisk.ru/api/profile-pending/?retpath=https%3A%2F%2Fwww.kinopoisk.ru%2F",
                "container": container_found,
            },
        )
        if install.status != 200:
            raise RuntimeError(
                "Kinopoisk login: https://sso.kinopoisk.ru/install didn't return status 200"
            )
        final_auth = await self.session.get(
            "http://www.kinopoisk.ru/api/profile-pending/?retpath=https%3A%2F%2Fwww.kinopoisk.ru%2F"
        )
        if final_auth.status != 200:
            raise RuntimeError(
                "Kinopoisk login: final auth request didn't return status 200"
            )
        asyncio.create_task(self.do_save_cookies())

    async def _handle_captcha(self, req: aiohttp.ClientResponse):
        if "captcha" not in str(req.url):
            return

        captcha_url_found = re.findall(r"(?<=action=\").*?(?=\")", await req.text())
        if not captcha_url_found:
            raise RuntimeError("Captcha error: no captcha url")
        captcha_url = captcha_url_found[0]
        showcaptcha = await self.session.post("http://kinopoisk.ru" + captcha_url)
        showcaptcha_text = await showcaptcha.text()
        captcha_image_found = re.findall(
            r"(?<=src\=\"http://kinopoisk.ru/captchaimg\?).*?(?=\")",
            showcaptcha_text,
        )
        if not captcha_image_found:
            raise RuntimeError("Captcha image not found")
        captcha_image_url = captcha_image_found[0]
        checkcaptcha_found = re.findall(
            r"(?<=checkcaptcha\?).*?(?=\")", showcaptcha_text
        )
        aesKey_found = re.findall(r"(?<=aesKey:\").*?(?=\")", showcaptcha_text)
        signKey_found = re.findall(r"(?<=aesSign:\").*?(?=\")", showcaptcha_text)
        if not checkcaptcha_found or not aesKey_found or not signKey_found:
            raise RuntimeError(
                "not checkcaptcha_found or not aesKey_found or not signKey_found"
            )
        return {
            "type": "kinopoisk-captcha",
            "captcha_url": captcha_image_url,
            "url": "http://kinopoisk.ru/checkcaptcha?" + checkcaptcha_found[0],
            "data": {
                "aesKey": aesKey_found[0],
                "signKey": signKey_found[0],
            },
            "checkcaptcha_url": "http://kinopoisk.ru/checkcaptcha?"
            + checkcaptcha_found[0],
        }

    async def confirm_kinopoisk_captcha(self, data: dict, captcha_input: str):
        checkcaptcha = await self.session.get(
            "http://kinopoisk.ru/checkcaptcha?" + data["checkcaptcha_url"],
            data={"rep": captcha_input, **data["data"]},
            params={"rep": captcha_input},
        )
        if "showcaptcha" in str(checkcaptcha.url):
            req = checkcaptcha
        if str(checkcaptcha.url) == "https://www.kinopoisk.ru/":
            return 0
        raise RuntimeError(
            f"Kinopoisk login captcha: unexpected response {checkcaptcha.url}"
        )

    async def get_graphql_schema(self, name: str):
        if name not in self.graphql_schemas:
            async with aiofiles.open(
                self.schemas_directory + name, encoding="utf8"
            ) as file:
                self.graphql_schemas[name] = await file.read()
        return self.graphql_schemas[name]

    async def do_search(self, query: str, limit: int = 5):
        """search everything, just like from top input box on main kinopoisk page"""
        schema = await self.get_graphql_schema("SuggestSearch.graphql")

        resp = await self.session.post(
            "https://graphql.kinopoisk.ru/graphql/?operationName=SuggestSearch",
            json={
                "operationName": "SuggestSearch",
                "query": schema,
                "variables": {"keyword": query, "limit": limit},
            },
            headers={"service-id": "25"},
        )

        return await resp.json()

    async def do_hd_search(self, query: str, limit: int = 5):
        """Search movies avaliable to watch on hd.kinopoisk.ru"""
        schema = await self.get_graphql_schema("SuggestSearchOnline.graphql")

        resp = await self.session.post(
            "https://graphql.kinopoisk.ru/graphql/?operationName=SuggestSearchOnline",
            json={
                "operationName": "SuggestSearchOnline",
                "query": schema,
                "variables": {"keyword": query, "limit": limit},
            },
            headers={"service-id": "25"},
        )

        return await resp.json()

    async def do_old_search(self):
        """Search old kinopoisk(before yandex) way"""
        raise NotImplementedError()

    async def convert_kp_to_kphd_id(self, kp_id: int) -> str:
        resp = await self.session.get(
            f"https://www.kinopoisk.ru/film/{kp_id}/watch/", allow_redirects=False
        )
        return resp.headers["location"][:-1].split("/")[-1]

    async def get_film_children(self, kphd_id: str) -> dict:
        resp = await self.session.get(
            f"https://api.ott.kinopoisk.ru/v12/hd/content/{kphd_id}/children"
        )
        return await resp.json()

    async def get_streams(self, content_id: str) -> dict:
        resp = await self.session.get(
            f"https://api.ott.kinopoisk.ru/v12/hd/content/{content_id}/streams?serviceId=25"
        )
        return await resp.json()

    async def create_web_streams(self, streams_from_get_streams_function: dict) -> bool:
        """call get_streams and pass output to this function"""
        if streams_from_get_streams_function["licenseStatus"] != "APPROVED":
            raise LicenseNotApprovedError()
        if len(streams_from_get_streams_function["streams"]) > 1:
            raise NotImplementedError("(temporarily) got more than 1 stream")

        stream = streams_from_get_streams_function["streams"][0]
        supported_drm_types = ["widevine"]
        if stream["drmType"] not in supported_drm_types:
            raise NotImplementedError(f"{stream['drmType']}")

        async with self.session.get(stream["uri"]) as resp:
            async with aiofiles.open("web/test.mpd", mode="wb+") as f:
                await f.write(await resp.read())
        async with self.session.get(stream["drmConfig"]) as resp:
            async with aiofiles.open("web/key.bin", mode="wb+") as f:
                await f.write(await resp.read())
