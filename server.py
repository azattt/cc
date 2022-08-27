import asyncio
import logging
import sys
import time

import aiohttp
import aiohttp.web

from urllib.parse import quote

from yaclient.clients import STATUS_CAPTCHA, STATUS_OK, KinopoiskClient, YandexClient
from yaclient.exceptions import WrongCredentialsError
from yaclient.helpers import load_credentials


async def on_request_start(session, trace_config_ctx, params):
    logger = logging.getLogger(__name__)
    logger.debug("Starting request %s %s %s", session, trace_config_ctx, params)


async def on_request_end(session, trace_config_ctx, params):
    logger = logging.getLogger(__name__)
    logger.debug("Ending request")


print_ = print


def print(*args, **kwargs):
    print_(str(time.time()), *args, **kwargs)


trace_config = aiohttp.TraceConfig()
# trace_config.on_request_chunk_sent.append(on_request_start)
# trace_config.on_request_end.append(on_request_end)

routes = aiohttp.web.RouteTableDef()
app = aiohttp.web.Application(client_max_size=1024 * 2**30)
yandex_client = YandexClient()
kinopoisk_client = KinopoiskClient(yandex_client, trace_configs=[trace_config])


@routes.get("/")
async def index(_):
    print(1)
    return aiohttp.web.FileResponse("static/index.html")


@routes.get("/lotofdata")
async def lotofdata(request):
    response = await yandex_client.session.get("https://speedtest.selectel.ru/10MB")
    web_response = aiohttp.web.StreamResponse(status=response.status)
    web_response.content_length = response.content_length
    await web_response.prepare(request)
    async for data in response.content:
        print("data")
        await web_response.write(data)
    await web_response.write_eof()
    return web_response


@routes.get("/manifest")
async def manifest(request: aiohttp.web.Request):
    logger = logging.getLogger(__name__)
    logger.debug("manifest %s", repr(request))
    async with kinopoisk_client.session.get(
        request.query["url"]
    ) as response_from_kinopoisk:
        byts = await response_from_kinopoisk.read()
    return aiohttp.web.Response(
        headers={"content-type": response_from_kinopoisk.headers["content-type"]},
        body=byts,
    )


@routes.post("/drm")
async def drm(request: aiohttp.web.Request):
    logger = logging.getLogger(__name__)
    logger.debug("/drm %s", repr(request))
    data = await request.json()
    async with kinopoisk_client.session.post(
        request.query["url"], headers={"Referer": "https://hd.kinopoisk.ru/"}, json=data
    ) as response_from_kinopoisk:
        logger.debug(
            "drm %s %s", response_from_kinopoisk.status, response_from_kinopoisk.headers
        )
        byts = await response_from_kinopoisk.read()
    return aiohttp.web.Response(
        body=byts,
    )


@routes.get("/segment")
async def segment(request: aiohttp.web.Request):
    logger = logging.getLogger(__name__)
    logger.debug("/segment %s", request)
    async with kinopoisk_client.session.get(
        request.query["url"],
        headers={"Referer": "https://hd.kinopoisk.ru/"},
    ) as response_from_kinopoisk:
        logger.debug(
            "segment %s %s %s",
            response_from_kinopoisk.content_length,
            response_from_kinopoisk.status,
            response_from_kinopoisk.headers,
        )
        byts = await response_from_kinopoisk.read()
        resp = aiohttp.web.Response(body=byts)
    return resp


@routes.view("/api")
async def api_version_unspecified(request: aiohttp.web.Request):
    raise aiohttp.web.HTTPNotFound(body="{'error': 'Specify version.'}")


@routes.get("/api/v1/ping")
async def ping(_):
    raise aiohttp.web.HTTPOk()


@routes.post("/api/v1/log")
async def log(request: aiohttp.web.Request):
    # logger = logging.getLogger(__name__)
    # logger.debug("/log %s", await request.text())
    print(await request.text())
    raise aiohttp.web.HTTPOk()


@routes.get("/api/v1/checkKinopoiskAuth")
async def check_kinopoisk_auth(_):
    return aiohttp.web.json_response({"auth": False})
    # return aiohttp.web.json_response({"auth": await kinopoisk_client.check_login()})


@routes.post("/api/v1/loginKinopoisk")
async def login_kinopoisk(request: aiohttp.web.Request):
    data = await request.post()
    if "login" not in data or "password" not in data:
        return aiohttp.web.json_response(
            {"result": "error", "reason": "credentials not provided"}
        )

    try:
        need_to_continue = await yandex_client.try_login(
            data["login"], data["password"]
        )
    except WrongCredentialsError as exc:
        logger = logging.getLogger(__name__)
        logger.warning("Wrong credentials", exc_info=1)
        return aiohttp.web.json_response(
            {"result": "error", "reason": "wrong credentials", "verbose": str(exc)}
        )

    if not need_to_continue:
        return aiohttp.web.json_response({"result": "ok"})

    resp = {"result": "continue", "apiLocation": "/loginContinue", **need_to_continue}
    if "captchaUrl" in resp:
        resp["captchaUrl"] = "/api/v1/getCaptchaImg?url=" + quote(resp["captchaUrl"])

    return aiohttp.web.json_response(resp)


@routes.post("/api/v1/loginContinue")
async def login_continue(request: aiohttp.web.Request):
    request_json = await request.json()
    if request_json["type"] == "js-domik-captcha":
        print(request_json)
    return aiohttp.web.HTTPOk()


@routes.get("/api/v1/getCaptchaImg")
async def get_captcha_img(request: aiohttp.web.Request):
    resp = await yandex_client.session.get(request.query["url"])
    resp_body = await resp.read()
    return aiohttp.web.Response(
        body=resp_body, headers={"content-type": resp.headers["content-type"]}
    )


async def main():
    logger = logging.getLogger(__name__)
    logger_formatter = logging.Formatter(
        "[%(asctime)s][%(levelname)s][%(pathname)s:%(lineno)d] %(message)s"
    )
    logger_fh = logging.FileHandler("debug/main.log", mode="w+", encoding="utf8")
    logger_fh.setLevel(logging.DEBUG)
    logger_fh.setFormatter(logger_formatter)
    logger.addHandler(logger_fh)
    logger.setLevel(logging.DEBUG)

    logger_sh = logging.StreamHandler(sys.stdout)
    logger_sh.setLevel(logging.DEBUG)
    logger_sh.setFormatter(logger_formatter)

    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel(logging.DEBUG)
    asyncio_logger.addHandler(logger_sh)
    asyncio_logger.addHandler(logger_fh)

    aiohttp_loggers = [
        "aiohttp.access",
        "aiohttp.client",
        "aiohttp.internal",
        "aiohttp.server",
        "aiohttp.web",
        "aiohttp.websocket",
    ]
    for aiohttp_logger_name in aiohttp_loggers:
        aiohttp_logger = logging.getLogger(aiohttp_logger_name)
        aiohttp_logger.setLevel(logging.DEBUG)
        aiohttp_logger.addHandler(logger_sh)
        aiohttp_logger.addHandler(logger_fh)

    logger.info("Starting")
    yandex_client.save_cookies = False
    yandex_client.logger.setLevel(logging.DEBUG)
    yandex_client.logger.addHandler(logger_fh)
    yandex_client.logger.addHandler(logger_sh)
    kinopoisk_client.logger.setLevel(logging.DEBUG)
    kinopoisk_client.logger.addHandler(logger_fh)
    kinopoisk_client.logger.addHandler(logger_sh)
    await yandex_client.create_session()
    # await yandex_client.login(*(await load_credentials("credentials.txt")))
    await kinopoisk_client.create_session()
    # await kinopoisk_client.login()
    app.add_routes(routes)
    app.add_routes([aiohttp.web.static("/static", "static")])
    app.add_routes([aiohttp.web.static("/", "static")])
    # runner = aiohttp.web.AppRunner(app)
    # await runner.setup()
    # # ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # # ssl_context.load_cert_chain(certfile="cert.pem", keyfile="key.pem")
    # site = aiohttp.web.TCPSite(runner, host="localhost", port=8080)
    # await site.start()
    # await asyncio.Event().wait()
    return app


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
