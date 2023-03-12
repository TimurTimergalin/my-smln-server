import asyncio
import logging
import os
from sys import argv
import db as drivers
import websockets
from core.connection import Connection
from core.connection_registry import ConnectionRegistry
from encryption import *
from config import yaml_config


def init_file_system():
    if not os.path.isdir("files"):
        os.mkdir("files")

    if not os.path.isdir("logs"):
        os.mkdir("logs")


async def main():
    init_file_system()

    cfg = yaml_config(argv[1])
    logging.basicConfig(
        filename=f"logs/{cfg.logging.file_name}",
        level=getattr(logging, cfg.logging.level),
        format=cfg.logging.format,
        datefmt=cfg.logging.datetime_format
    )

    driver = drivers.get(cfg.db.driver)

    db = driver(cfg.db.connection_string, PasswordHasher(cfg.crypto.hash_alg))
    async with websockets.serve(Connection.connect(ConnectionRegistry(logging), db, logging), cfg.ip, cfg.port):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
