class ConnectionRegistry:
    def __init__(self):
        self.unauthorized = set()
        self.authorized = {}

    def register(self, connection):
        self.unauthorized.add(connection)

    def authorize(self, connection, user_id):
        self.unauthorized.remove(connection)

        if self.authorized.get(user_id) is not None:
            raise ValueError("Such user is already authorized")
        self.authorized[user_id] = connection

    def unregister_unauthorized(self, connection):
        self.unauthorized.remove(connection)

    def unregister_authorized(self, user_id):
        del self.authorized[user_id]

    async def activity_update(self, user_id):
        for conn in self.authorized.values():
            await conn.activity_update(user_id)

    async def message_received(self, user_id, message):
        if user_id in self.authorized:
            await self.authorized[user_id].message_received(message)

    async def messages_read(self, sender_id, reader_id):
        if sender_id in self.authorized:
            await self.authorized[sender_id].messages_read(reader_id)


registry = ConnectionRegistry()
