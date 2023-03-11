# это сам сервер, его нужно запустить в отдельном контейнере


import asyncio

import websockets


async def handler(ws):
    async for mes in ws:
        await ws.send(f"Sending back your message: {mes}")


async def main():
    async with websockets.serve(
            handler,
            "0.0.0.0",
            port=8080
    ):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
