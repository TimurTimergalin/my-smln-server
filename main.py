import asyncio
import logging
import os

from db import MongoDB
import websockets
from core.connection import Connection
from core.connection_registry import ConnectionRegistry
from encryption import *


def init_file_system():
    if not os.path.isdir("files"):
        os.mkdir("files")

    if not os.path.isdir("logs"):
        os.mkdir("logs")


async def main():
    init_file_system()

    logging.basicConfig(
        filename="logs/smln_server.log",
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%d/%b/%Y %H:%M:%S",
    )

    db = MongoDB("mongodb://localhost:27017", PasswordHasher("sha3_256"))
    async with websockets.serve(Connection.connect(ConnectionRegistry(logging), db, logging), "0.0.0.0", 8080):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
