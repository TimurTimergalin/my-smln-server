import os
import re
import uuid
import motor.motor_asyncio
import string
import time


class MongoDB:
    allowed_characters = set(string.ascii_letters + string.digits + " _-" +
                             ''.join(chr(x) for x in range(ord('А'), ord('Я') + 1)) + 'Ё' +
                             ''.join(chr(x) for x in range(ord('а'), ord('я') + 1)) + 'ё')

    def __init__(self, conn_str, password_hasher, message_encryptor):
        client = motor.motor_asyncio.AsyncIOMotorClient(conn_str)

        self.db = client["smln-server"]

        self.pswd = password_hasher
        self.msg = message_encryptor

    async def validate_password(self, login, password):
        if not isinstance(login, str):
            return False, None, None, None
        if not isinstance(password, str):
            return False, None, None, None

        users = self.db["users"]
        user = await users.find_one({"login": login})

        if user is None:
            return False, None, None, None

        hashed = user["password"]

        valid = self.pswd.check_password(password, hashed)

        if valid:
            return valid, user["_id"]
        return False, None, None, None

    async def _update_user_online_status(self, user_id, status):
        if not isinstance(user_id, int):
            return False
        users = self.db["users"]
        user = await users.find_one({"_id": user_id})

        if user is None:
            return False

        await self.db.find_one_and_update({"_id": user_id}, {"$set": {"is-online": status,
                                                                      "last-seen": int(time.time())}})

    async def make_user_online(self, user_id):
        return await self._update_user_online_status(user_id, True)

    async def make_user_offline(self, user_id):
        return await self._update_user_online_status(user_id, False)

    @staticmethod
    def _validate_people_filter(filter_: str):
        if filter_ is None:
            return True
        if not isinstance(filter_, str):
            return False
        filters = filter_.split('&')

        for f in filters:
            if f != "online" and not f.startswith("role=") and not f.startswith("name-startswith="):
                return False

            if not all(x in MongoDB.allowed_characters for x in f):
                return False

        return True

    @staticmethod
    def _remove_id_underscore(dct):
        dct["id"] = dct["_id"]
        del dct["_id"]

    async def people(self, list_properties):
        from_, count, invalid = self._validate_properties_range(list_properties)

        sort = list_properties.get("sort", "username")
        if sort not in ("username", "last-seen", "role"):
            invalid.add("sort")

        ascend = list_properties.get("is-ascending", sort != "last-seen")
        if not isinstance(ascend, bool):
            invalid.add("is-ascending")

        filter_ = list_properties.get("filter", None)
        if not self._validate_people_filter(filter_):
            invalid.add("filter")

        if invalid:
            return None, invalid

        users = self.db["users"]

        aggregate_pipeline = []

        project = {
            "_id": 0,
            "id": "$_id",
            "username": 1,
            "role": 1,
            "is-online": 1,
            "last-seen": 1,
            "public-key": 1
        }

        aggregate_pipeline.append({"$project": project})

        if filter_ is not None:
            match = {}

            for f in filter_.split("&"):
                if f == "online":
                    match["is-online"] = True
                elif f.startswith("role="):
                    role = f.split("=", 1)[1]
                    match["role"] = role
                elif f.startswith("name-startswith="):
                    prefix = f.split("=", 1)[1]
                    match["username"] = {"$regex": f"^{prefix}"}

            aggregate_pipeline.append({"$match": match})

        sort_ = {}

        asc = 2 * ascend - 1

        if sort == "last-seen":
            sort_["is-online"] = asc
            sort_["last-seen"] = asc
        else:
            sort_[sort] = asc

        aggregate_pipeline.append({"$sort": sort_})

        res = []

        async for x in users.aggregate(aggregate_pipeline):
            res.append(x)

        return res[slice(from_, (None if count is None else from_ + count))], None

    async def get_user(self, user_id):
        users = self.db['users']

        if not isinstance(user_id, int):
            return None, False

        res = await users.find_one({"_id": user_id}, {"username": 1, "role": 1, "is-online": 1, "last-seen": 1})

        if res is None:
            return res, False

        self._remove_id_underscore(res)
        return res, True

    file_expr = re.compile(r"^[A-Za-z0-9 _.]+[^.]$")

    def _validate_files(self, files):
        if not isinstance(files, list):
            return False
        for file in files:
            if not isinstance(file, dict):
                return False

            if not {"name, data"}.issubset(set(file.keys())):
                return False

            if not self.file_expr.match(file["name"]):
                return False

        return True

    async def save_files(self, files, owner_id):
        cfiles = self.db["files"]

        res = []
        for file in files:
            token = uuid.uuid5(uuid.NAMESPACE_DNS, str(os.urandom(16))).hex
            size = len(enc := file["data"].encode('utf-8'))

            with open(token, "wb") as f:
                f.write(enc)

            res.append({
                "name": file["name"],
                "toke": token,
                "size": size,
                "owner-id": owner_id
            })

        return await cfiles.insert_many(res), res

    async def send_message(self, sender_id, receiver_id, message_for_receiver, message_for_sender):
        if not isinstance(sender_id, int):
            return None, False, None

        if not isinstance(receiver_id, int):
            return None, False, None

        if not isinstance(message_for_receiver, dict):
            return None, None, "Message is not in correct format"
        if not isinstance(message_for_sender, dict):
            return None, None, "Message is not in correct format"

        users = self.db["users"]

        receiver = await users.find_one({"_id": receiver_id})

        if receiver is None:
            return None, False, None

        sender = await users.find_one({"_id": sender_id})

        if sender is None:
            raise ValueError("Unknown sender")

        for message in message_for_receiver, message_for_sender:

            text = message.get("text", "")
            files = message.get("files", [])

            if not (text or files):
                return None, None, "The message is empty"

            if not self._validate_files(files):
                return None, None, "invalid file"

        chats = self.db["chats"]

        chat = await chats.find_one({"users": {"$all": [sender_id, receiver_id]}})

        if chat is None:
            name = uuid.uuid5(uuid.NAMESPACE_DNS, str(os.urandom(16))).hex
        else:
            name = chat["name"]

        chat = self.db[name]

        timestamp = int(time.time())

        sender_ids, _ = await self.save_files(message_for_sender["files"], sender_id)
        receiver_ids, receiver_files = await self.save_files(message_for_receiver["files"], receiver_id)
        message = {
            "sender-id": sender_id,
            "receiver-id": receiver_id,
            "time": timestamp,
            "seen": False,
            "messages": [
                {
                    "target": sender_id,
                    "text": message_for_sender["text"],
                    "files": sender_ids
                },
                {
                    "target": receiver_id,
                    "text": message_for_receiver["text"],
                    "files": receiver_ids
                }
            ]
        }

        await chat.insert_one(message)

        server_message_for_receiver = {
            "sender": sender_id,
            "receiver": receiver_id,
            "seen": False,
            "text": message_for_receiver["text"],
            "time": timestamp,
        }

        for f in receiver_files:
            del f["owner-id"]

        server_message_for_receiver["files"] = receiver_files

        return server_message_for_receiver, True, None

    @staticmethod
    def _validate_properties_range(list_properties):
        invalid = set()

        from_ = list_properties.get("from", 0)
        if not isinstance(from_, int):
            invalid.add("from")
        elif from_ < 0:
            invalid.add("from")

        count = list_properties.get("count", None)
        if count is not None and not isinstance(count, int):
            invalid.add("count")
        elif isinstance(count, int) and count <= 0:
            invalid.add("count")

        return from_, count, invalid

    async def messages(self, target, other, list_properties):
        from_, count, invalid = self._validate_properties_range(list_properties)

        filter_ = list_properties.get("filter", None)
        if filter_ not in {"has-files", "new", None}:
            invalid.add("filter")

        if invalid:
            return None, None, invalid

        users = self.db["users"]

        receiver = await users.find_one({"_id": other})

        if receiver is None:
            return None, False, None

        sender = await users.find_one({"_id": target})

        if sender is None:
            raise ValueError("Unknown receiver")

        chats = self.db["chats"]

        chat = await chats.find_one({"users": {"$all": [target, other]}})

        if chat is None:
            return [], True, None
        name = chat["name"]
        chat = self.db[name]

        aggregation_pipeline = [
            {
                "$unwind": "$messages"
            },
            {
                "$match": {"messages.target": target}
            },
            {
                "$lookup": {
                    "from": "files",
                    "localField": "messages.files",
                    "foreignField": "_id",
                    "as": "messages.server_files"
                }
            }
        ]

        if filter_ == 'has-files':
            m = {
                "$exists": True,
                "$ne": []
            }

            aggregation_pipeline.append(m)
        elif filter_ == "new":
            m = {
                "seen": True
            }
            aggregation_pipeline.append(m)

        project = {
            "_id": 0,
            "sender": "$sender-id",
            "receiver": "$receiver-id",
            "time": 1,
            "text": "$messages.text",
            "seen": 1,
            "files": "$messages.server_files"
        }

        aggregation_pipeline.append(project)

        sort_ = {
            "time": -1
        }

        aggregation_pipeline.append(sort_)

        res = []

        async for mes in chat.aggregate(aggregation_pipeline):
            res.append(mes)

        return res[slice(from_, (None if count is None else from_ + count))], True, None

    async def people_with_messages(self, user_id, list_properties):
        if not isinstance(user_id, int):
            raise ValueError("Unknown user")

        from_, count, invalid = self._validate_properties_range(list_properties)
        if invalid:
            return None, invalid

        chats = self.db["chats"]
        aggregation_pipeline = [
            {
                "$match": {"users": user_id}
            },
            {
                "$unwind": "users"
            },
            {
                "$match": {"users": {"$ne": user_id}}
            },
            {
                "$lookup": {
                    "from": "users",
                    "let": {"user_id": "$users"},
                    "pipeline": [
                        {
                            "$match": {"_id": "$$user_id"},
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "id": "$_id",
                                "public-key": 1,
                                "username": 1,
                                "role": 1,
                                "is-online": 1,
                                "last-seen": 1
                            }
                        }
                    ],
                    "as": "user"
                }
            },
            {
                "$lookup": {
                    "from": "$name",
                    "pipeline": [
                        {
                            "$sort": {"time": -1}
                        },
                        {
                            "$limit": 1
                        },
                        {
                            "$unwind": "messages"
                        },
                        {
                            "$match": {"messages.target": user_id}
                        },
                        {
                            "$unwind": "message.files"
                        },
                        {
                            "$lookup": {
                                "from": "files",
                                "let": {"file_id": "$messages.files._id"},
                                "pipeline": [
                                    {
                                        "$match": {"_id": "$$file_id"}
                                    },
                                    {
                                        "$project": {
                                            "_id": 0,
                                            "name": 1,
                                            "token": 1,
                                            "size": 1
                                        }
                                    }
                                ],
                                "as": "files"
                            }
                        },
                        {
                            "$group": {
                                "_id": "$_id",
                                "files": {"$push": "$files"}
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "sender": "$sender-id",
                                "receiver": "$receiver-id",
                                "time": 1,
                                "seen": 1,
                                "text": "$messages.text",
                                "files": 1
                            }
                        }
                    ],
                    "as": "messages"
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "user": {"$arrayElementAt": ["$user", 0]},
                    "last-message": {"$arrayElementAt": ["$messages", 0]}
                }
            }
        ]

        res = []
        async for cht in chats.aggregate(aggregation_pipeline):
            res.append(cht)

        return res[slice(from_, (None if count is None else from_ + count))], None

    async def download(self, user_id, token):
        users = self.db["users"]

        user = await users.find_one({"_id": user_id})

        if user is None:
            raise ValueError("Unknown user")

        files = self.db["files"]

        file = await files.find_one({"token": token})

        if file is None:
            return None, False
        if file["owner-id"] != user_id:
            return None, False

        with open(token, "w", encoding="utf-8") as f:
            return f.read(), True

    async def read(self, reader_id, other_id):
        users = self.db["users"]

        reader = await users.find_one({"_id": reader_id})

        if reader is None:
            raise ValueError("Unknown user")

        other = await users.find_one({"_id": other_id})

        if other is None:
            return False

        chats = self.db["chats"]

        chat = await chats.find_one({"users": {"$all": [reader_id, other_id]}})

        if chat is None:
            return True

        chat = self.db[chat["name"]]
        await chat.update_many({"seen": False, "receiver": reader_id}, {"$set": {"seen": True}})

