import asyncio
import json
import status
import websockets
from smln_handler import SMLNHandler

INVALID_FORMAT = "invalid-format"
UNSPECIFIED_TYPE = "unspecified-type"


def auth_required(cor):
    async def new_cor(self, args):
        if self.user_id is None:
            st = status.auth_required()
            await self.send_json({"type": cor.__name__.replace("_", "-"), "status": st})
            return
        await cor(self, args)

    return new_cor


def required_fields(*fields):
    def decorator(cor):
        async def new_cor(self, args):
            absent = set(fields) - set(args.keys())
            if absent:
                st = status.absent_fields(absent)
                await self.send_json({"type": cor.__name__.replace("_", '-'), "status": st})
                return
            await cor(self, args)

        return new_cor

    return decorator


class Connection:
    smln = SMLNHandler()

    def __init__(self, ws: websockets.WebSocketServerProtocol):
        print("Connected")
        self.ws = ws

        self.user_id = None

        self.registry.register(self)

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
        await self.ws.send(json.dumps(msg))

    @smln.on_unknown_type
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
    async def on_server_error(self, type_):
        await self.send_json({"type": type_, "status": status.server_error()})

    @smln.handler
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

        self.user_id = user_id

        st = status.ok()

        user_found = await self.db.make_user_online(user_id)
        if not user_found:
            st = status.user_not_found(user_id)
            await self.send_json({"type": "auth", "status": st})
            return
        await asyncio.gather(
            self.send_json(
                {"type": "auth", "status": st, "args": {"id": user_id, "public-key": pub, "private-key": pr}}),
            self.registry.activity_update(user_id)
        )

    @smln.handler
    @auth_required
    async def people_with_messages(self, args):
        list_properties = args.get("list-properties", {})
        res, invalid_properties = await self.db.people_with_message(self.user_id,
                                                list_properties)
        if invalid_properties:
            st = status.invalid_list_properties(invalid_properties)
            await self.send_json({"type": "people-with-messages", "status": st})
            return
        await self.send_json({"type": "people-with-messages", "status": status.ok(), "args": {"chats": res}})

    @smln.handler
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
    @required_fields("get-user", "id")
    @auth_required
    async def get_user(self, args):
        other_user = args.get("user-id")
        res, user_found = await self.db.get_user(other_user)

        if not user_found:
            st = status.user_not_found(other_user)
            await self.send_json({"type": "get-user", "status": st})
            return

        await self.send_json({"type": "get-user", "status": status.ok(), "args": {"user": res}})

    @smln.handler
    @required_fields("receiver-id", "message_for_receiver")
    @auth_required
    def send(self, args):
        receiver_id = args.get("receiver-id")
        message = args.get("message_for_receiver")

        server_message, user_found, invalid_message_error = await self.db.send_message(self.user_id, receiver_id,
                                                                                       message)

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
            self.registry.message_received(server_message)
        )

    @smln.handler
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

    async def activity_update(self, user_id):
        res, user_found = await self.db.get_user(user_id)

        if not user_found:
            raise ValueError("No such user")

        await self.send_json({"type": "activity-update", "args": {"user-id": user_id, "is-online": res.is_online,
                                                                  "last-seen": res.last_seen}})

    async def message_received(self, message):
        await self.send_json({"type": "message_for_receiver-received", "args": {"message_for_receiver": message}})

    async def messages_read(self, user_id):
        await self.send_json({"type": "messages-read", "args": {"user-id": user_id}})

    async def handle(self):
        try:
            async for message in self.ws:
                type_, args = self.decode_message(message)
                await self.smln.handle(self, type_, args)
        except websockets.ConnectionClosedError:
            pass

        if self.user_id:
            # сначала делаем offline, потом activity-update
            await self.db.make_user_offline(self.user_id)
            await self.registry.activity_update(self.user_id),
            self.registry.unregister_authorized(self.user_id)

        print("Disconnected")  # TODO: logging

    @classmethod
    def connect(cls, registry, db):
        cls.registry = registry
        cls.db = db

        async def handler(ws):
            await cls(ws).handle()

        return handler

    def __hash__(self):
        return self.ws.__hash__()
