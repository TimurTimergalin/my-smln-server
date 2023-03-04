import asyncio
from db import MongoDB
import websockets
from core.connection import Connection
from core.connection_registry import ConnectionRegistry
from encryption import *


async def main():
    db = MongoDB("mongodb://localhost:27017", PasswordHasher("sha3_256"), RsaAesHybridEncryptor(1024))
    async with websockets.serve(Connection.connect(ConnectionRegistry(), db), "localhost", 8080):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
