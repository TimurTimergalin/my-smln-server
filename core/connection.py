import asyncio
import json

from bson import ObjectId

import core.status as status
import websockets
from core.smln_handler import SMLNHandler

INVALID_FORMAT = "invalid-format"
UNSPECIFIED_TYPE = "unspecified-type"


def auth_required(cor):

    name = cor.__name__

    async def new_cor(self, args):
        if self.user_id is None:
            st = status.auth_required()
            await self.send_json({"type": name.replace("_", "-"), "status": st})
            return
        await cor(self, args)

    new_cor.__name__ = name
    return new_cor


def check_type(type_dct):
    def dec(cor):
        name = cor.__name__

        async def new_cor(self, args):
            for key in args:
                if key in type_dct and not isinstance(args[key], type_dct[key]):
                    st = status.wrong_data_type(key)
                    await self.send_json({"type": name.replace("_", '-'), "status": st})
                    return
            await cor(self, args)

        new_cor.__name__ = name
        return new_cor
    return dec


def required_fields(*fields):
    def decorator(cor):
        name = cor.__name__

        async def new_cor(self, args):
            absent = set(fields) - set(args.keys())
            if absent:
                st = status.absent_fields(absent)
                await self.send_json({"type": name.replace("_", '-'), "status": st})
                return
            await cor(self, args)

        new_cor.__name__ = name
        return new_cor

    return decorator


class LogDec:
    def __init__(self, logger):
        self.logger = logger

    def __call__(self, cor):
        name = cor.__name__

        async def new_cor(self, *args):
            self.logger.debug(
                f"Handling request. Connection: {self.id}, func: {name}, args: {'; '.join(str(x) for x in args)}")
            self.logger.info(f"Connection {self.id} calls handler: {name}")
            await cor(self, *args)

        new_cor.__name__ = name
        return new_cor


class Connection:
    smln = SMLNHandler()
    logger = None
    handler_log = LogDec(logger)

    def __init__(self, ws: websockets.WebSocketServerProtocol):
        self.logger.info(f"Connection {ws.id} established")
        self.ws = ws

        self.user_id = None

        self.registry.register(self)

    @classmethod
    def set_logger(cls, logger):
        cls.logger = logger
        cls.handler_log.logger = logger

    @property
    def closed(self):
        return self.ws.closed

    @property
    def id(self):
        return self.ws.id

    @staticmethod
    def decode_message(m):
        try:
            dct = json.loads(m)
            if not isinstance(dct, dict):
                type_ = INVALID_FORMAT
                args = {}
            else:
                type_ = dct.get("type", UNSPECIFIED_TYPE)
                args = dct.get("args", {})

        except json.JSONDecodeError:
            type_ = INVALID_FORMAT
            args = {}

        return type_, args

    async def send_json(self, msg):
        self.logger.debug(f"Sending message. Connection: {self.id}, message: {msg}")
        log_message = f"Connection {self.id} sends message of type '{msg['type']}'"
        if "status" in msg:
            log_message += f" and status: {msg['status']}"
        try:
            await self.ws.send(json.dumps(msg, default=str, ensure_ascii=False))
            log_message += f". Sent successfully."
        except websockets.ConnectionClosed:
            log_message += f". Failed: connection was closed before receiving response"
        self.logger.info(log_message)

    @smln.on_unknown_type
    @handler_log
    async def on_unknown_type(self, type_):
        if type_ == INVALID_FORMAT:
            st = status.invalid_format()
        elif type_ == UNSPECIFIED_TYPE:
            st = status.unspecified_type()
        else:
            st = status.unknown_type(type_)

        message = {
            "type": type_,
            "status": st
        }

        await self.send_json(message)

    @smln.on_server_error
    @handler_log
    async def on_server_error(self, type_):
        await self.send_json({"type": type_, "status": status.server_error()})

    @smln.handler
    @handler_log
    @check_type({"login": str, "pass": str})
    @required_fields("login", "pass")
    async def auth(self, args):
        if self.user_id is not None:
            st = status.repeated_auth()
            await self.send_json({"type": "auth", "status": st})
            return

        login = args["login"]
        password = args["pass"]
        ok, user_id, pub, pr = await self.db.validate_password(login, password)
        if not ok:
            st = status.wrong_credentials()
            await self.send_json({"type": "auth", "status": st})
            return

        user_found = await self.db.make_user_online(user_id)
        if not user_found:
            st = status.user_not_found(user_id)
            await self.send_json({"type": "auth", "status": st})
            return
        try:
            self.registry.authorize(self, user_id)
        except ValueError:
            self.logger.warning(f"Someone trying to connect from another device, "
                                f"user {user_id} might have a compromised password")
            st = status.wrong_credentials()

            await self.send_json({"type": "auth", "status": st})
            return

        self.user_id = user_id

        st = status.ok()

        await asyncio.gather(
            self.send_json(
                {"type": "auth", "status": st, "args": {"id": user_id, "public-key": pub, "private-key": pr}}),
            self.registry.activity_update(user_id)
        )

    @smln.handler
    @handler_log
    @check_type({"list-properties": dict})
    @auth_required
    async def people_with_messages(self, args):
        list_properties = args.get("list-properties", {})
        res, invalid_properties = await self.db.people_with_messages(self.user_id,
                                                list_properties)
        if invalid_properties:
            st = status.invalid_list_properties(invalid_properties)
            await self.send_json({"type": "people-with-messages", "status": st})
            return
        await self.send_json({"type": "people-with-messages", "status": status.ok(), "args": {"chats": res}})

    @smln.handler
    @handler_log
    @check_type({"list-properties": dict})
    @auth_required
    async def people(self, args):
        list_properties = args.get("list-properties", {})
        res, invalid_properties = await self.db.people(list_properties)

        if invalid_properties:
            st = status.invalid_list_properties(invalid_properties)
            await self.send_json({"type": "people", "status": st})
            return

        await self.send_json({"type": "people", "status": status.ok(), "args": {"users": res}})

    @smln.handler
    @handler_log
    @check_type({"user-id": str, "list-properties": dict})
    @required_fields("user-id")
    @auth_required
    async def messages(self, args):
        other_user = args.get("user-id")
        list_properties = args.get("list-properties", {})
        res, user_found, invalid_properties = await self.db.messages(self.user_id, other_user,
                                                                     list_properties)

        if not user_found:
            st = status.user_not_found(other_user)
            await self.send_json({"type": "messages", "status": st})
            return

        if invalid_properties:
            st = status.invalid_list_properties(invalid_properties)
            await self.send_json({"type": "messages", "status": st})
            return

        await self.send_json({"type": "messages", "status": status.ok(), "args": {"messages": res}})

    @smln.handler
    @handler_log
    @check_type({"id": str})
    @required_fields("id")
    @auth_required
    async def get_user(self, args):
        other_user = args.get("id")
        res, user_found = await self.db.get_user(other_user)

        if not user_found:
            st = status.user_not_found(other_user)
            await self.send_json({"type": "get-user", "status": st})
            return

        await self.send_json({"type": "get-user", "status": status.ok(), "args": {"user": res}})

    @smln.handler
    @handler_log
    @check_type({"receiver-id": str, "message-for-receiver": dict, "message-for-sender": dict})
    @required_fields("receiver-id", "message-for-receiver", "message-for-sender")
    @auth_required
    async def send(self, args):
        receiver_id = args.get("receiver-id")
        message_for_receiver = args.get("message-for-receiver")
        message_for_sender = args.get("message-for-sender")

        server_message, user_found, invalid_message_error = await self.db.send_message(self.user_id, receiver_id,
                                                                                       message_for_receiver, message_for_sender)

        if not user_found:
            st = status.user_not_found(receiver_id)
            await self.send_json({"type": "send", "status": st})
            return

        if invalid_message_error is not None:
            st = status.status(3, invalid_message_error)
            await self.send_json({"type": "send", "status": st})
            return

        await asyncio.gather(
            self.send_json({"type": "send", "status": status.ok()}),
            self.registry.message_received(ObjectId(receiver_id), server_message)
        )

    @smln.handler
    @handler_log
    @check_type({"token": str})
    @required_fields("token")
    @auth_required
    async def download(self, args):
        token = args["token"]

        data, accessible = await self.db.download(self.user_id, token)

        if not accessible:
            st = status.file_not_accessible(token)
            await self.send_json({"type": "download", "status": st})
            return

        await self.send_json({"type": "download", "status": status.ok(), "args": {"data": data}})

    @smln.handler
    @handler_log
    @check_type({"user-id": str})
    @required_fields("user-id")
    @auth_required
    async def read(self, args):
        user_id = args["user-id"]

        user_found = await self.db.read(self.user_id, user_id)

        if not user_found:
            st = status.user_not_found(user_id)
            await self.send_json({"type": "read", "status": st})
            return

        await self.send_json({"type": "read", "status": status.ok()})

    @handler_log
    async def activity_update(self, user_id):
        res, user_found = await self.db.get_user(user_id)

        if not user_found:
            raise ValueError("No such user")

        await self.send_json({"type": "activity-update", "args": {"user-id": user_id, "is-online": res["is-online"],
                                                                  "last-seen": res["last-seen"]}})

    @handler_log
    async def message_received(self, message):
        await self.send_json({"type": "message-received", "args": {"message": message}})

    @handler_log
    async def messages_read(self, user_id):
        await self.send_json({"type": "messages-read", "args": {"user-id": user_id}})

    async def handle(self):
        try:
            async for message in self.ws:
                type_, args = self.decode_message(message)
                await self.smln.handle(self, type_, args)
        except websockets.ConnectionClosed:
            pass

        if self.user_id:
            # сначала делаем offline, потом activity-update
            self.registry.unregister_authorized(self.user_id)
            await self.db.make_user_offline(self.user_id)
            await self.registry.activity_update(self.user_id),

        self.logger.info(f"Connection {self.id} closed")

    @classmethod
    def connect(cls, registry, db, logger):
        cls.registry = registry
        cls.db = db
        cls.set_logger(logger)
        cls.smln.logger = logger

        async def handler(ws):
            await cls(ws).handle()

        return handler

    def __hash__(self):
        return self.ws.__hash__()
