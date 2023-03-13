import asyncio
import time
import motor.motor_asyncio as motor
from sys import argv
from encryption.rsa import RsaKeyGenerator
from encryption.passwords import PasswordHasher
from getpass import getpass
import re
from config import yaml_config


# используется для ручного индексирования коллекций в базе
# init-mongo.js делает это автоматически
async def init_db(db: motor.AsyncIOMotorDatabase):
    users = db["users"]

    await users.create_index("login", unique=True)

    files = db["files"]

    await files.create_index("token", unique=True)

    chats = db["chats"]

    await chats.create_index("users")


async def create_user(db: motor.AsyncIOMotorDatabase, pswd):
    username = input("Введите имя и фамилию пользователя: ")
    if not re.match(r'[A-Za-zА-ЯЁа-яё0-9 ]+', username):
        print("Некорректное имя пользователя")
        return
    login = input("Введите логин пользователя, с помощью которого он будет входить в систему: ")
    if not re.match(r'[A-Za-z_]', login):
        print("Некорректный логин")
    role = input("Введите должность пользователя в компании: ")
    if not re.match(r'[A-Za-zА-ЯЁа-яё0-9 ]+', role):
        print("Некорректная должность пользователя")
        return
    password = getpass("Введите пароль: ")
    rep = getpass("Повторите пароль: ")
    if password != rep:
        print("Пароли не совпадают")
        return

    users = db["users"]

    enc = RsaKeyGenerator(1024)

    pub, pr = enc.generate_key_pair(password)

    hashed = pswd.hash_password(password)

    user = {
        "login": login,
        "username": username,
        "password": hashed,
        "public-key": pub,
        "private-key": pr,
        "role": role,
        "is-online": False,
        "last-seen": int(time.time())
    }

    print("Пользователь успешно добавлен в систему")

    await users.insert_one(user)


async def main():
    cfg = yaml_config(argv[1])

    auth = ""
    if hasattr(cfg.db, "login"):
        auth = f"{cfg.db.login}:{cfg.db.password}@"

    connection_string = f"mongodb://{auth}localhost:27017"

    client = motor.AsyncIOMotorClient(connection_string)
    db = client['smln-server']
    password_hasher = PasswordHasher(cfg.crypto.hash_alg)

    try:
        if argv[2] == "init_db":
            await init_db(db)

        elif argv[2] == 'create_user':
            await create_user(db, password_hasher)
        else:
            raise ValueError("Unknown command")
    except Exception as e:
        print(f"Failed: {'; '.join(str(x) for x in e.args)}")


if __name__ == '__main__':
    asyncio.run(main())