# это файл для теста подключения (в контейнере он не нужен, но если засунешь, ничего страшного)

import websockets
import asyncio


async def main():
    ip = "localhost"  # ip на котором запущен nginx
    port = 443  # порт, который прослушивает nginx (можешь взять любой)
    protocol = "wss"  # Используй ws, чтобы протестировать обычное подключение, чтобы проверить tls, измени на "wss"

    url = f"{protocol}://{ip}:{port}"

    async with websockets.connect(url) as conn:
        await asyncio.gather(
            conn.send('{"type": "auth", "args": {"login": "ljoerg", "pass": "oughierughu"}}'),
            conn.send("message 2"),
            conn.send("message 3")
        )

        for _ in range(3):
            print(await conn.recv())


if __name__ == '__main__':
    asyncio.run(main())
