import asyncio
import aiohttp
import aiohttp.web

from yaclient.clients import KinopoiskClient, YandexClient
from yaclient.helpers import load_credentials


async def on_request_start(session, trace_config_ctx, params):
    print("Starting request", session, trace_config_ctx, params)


async def on_request_end(session, trace_config_ctx, params):
    print("Ending request")


trace_config = aiohttp.TraceConfig()
# trace_config.on_request_chunk_sent.append(on_request_start)
# trace_config.on_request_end.append(on_request_end)

routes = aiohttp.web.RouteTableDef()
app = aiohttp.web.Application()
yandex_client = YandexClient()
kinopoisk_client = KinopoiskClient(yandex_client, trace_configs=[trace_config])


@routes.get("/")
async def index(_):
    return aiohttp.web.FileResponse("static/index.html")


@routes.get("/lotofdata")
async def lotofdata(request):
    response = await yandex_client.session.get("https://speedtest.selectel.ru/100MB")
    web_response = aiohttp.web.StreamResponse(
        status=response.status, headers=response.headers
    )
    web_response.content_length = response.content_length
    await web_response.prepare(request)
    async for data in response.content.iter_any():
        await web_response.write(data)
    await web_response.write_eof()
    return web_response


@routes.get("/dash")
async def dash(request: aiohttp.web.Request):
    response = await kinopoisk_client.session.get(request.query["url"])
    web_response = aiohttp.web.StreamResponse(status=response.status)
    web_response.content_length = response.content_length
    await web_response.prepare(request)
    async for data in response.content.iter_any():
        await web_response.write(data)
    return web_response


@routes.post("/drm")
async def drm(request: aiohttp.web.Request):
    data = await request.json()
    response = await kinopoisk_client.session.post(
        request.query["url"], headers={"Referer": "https://hd.kinopoisk.ru/"}, json=data
    )
    print(response.status, response.headers)
    web_response = aiohttp.web.StreamResponse(status=response.status)
    web_response.content_length = response.content_length
    await web_response.prepare(request)
    async for data in response.content.iter_any():
        await web_response.write(data)
    return web_response


async def main():

    yandex_client.create_session()
    await yandex_client.login(*(await load_credentials("credentials.txt")))
    kinopoisk_client.create_session()
    await kinopoisk_client.login()
    app.add_routes(routes)
    app.add_routes([aiohttp.web.static("/static", "static")])
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host="127.0.0.1", port=80)
    await site.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
    asyncio.get_event_loop().run_forever()
