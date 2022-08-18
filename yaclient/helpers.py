"""YaClient helpers"""
import sys
import asyncio
import aiofiles
import aiohttp


async def ainput(string: str) -> str:
    await asyncio.get_event_loop().run_in_executor(
        None, lambda s=string: sys.stdout.write(s + " ")
    )
    return await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)


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
