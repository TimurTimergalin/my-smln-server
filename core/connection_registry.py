class ConnectionRegistry:
    def __init__(self, logger):
        self.logger = logger
        self.unauthorized = set()
        self.authorized = {}

    def register(self, connection):
        self.unauthorized.add(connection)

    def authorize(self, connection, user_id):
        self.unauthorized.remove(connection)

        if self.authorized.get(user_id) is not None:
            raise ValueError("Such user is already authorized")
        self.authorized[user_id] = connection

        self.logger.info(f"Authentication succeeded. Connection: {connection.id}, user-id: {user_id}")

    def unregister_unauthorized(self, connection):
        self.unauthorized.remove(connection)

    def unregister_authorized(self, user_id):
        del self.authorized[user_id]

    def check_online(self, user_id):
        if user_id not in self.authorized:
            return False
        conn = self.authorized[user_id]

        if conn.closed:
            del self.authorized[user_id]
            return False
        return True

    async def activity_update(self, user_id):
        for id_, conn in self.authorized.items():
            if not self.check_online(id_):
                return
            await conn.activity_update(user_id)

    async def message_received(self, user_id, message):
        if not self.check_online(user_id):
            return
        if user_id in self.authorized:
            await self.authorized[user_id].message_received(message)

    async def messages_read(self, sender_id, reader_id):
        if not self.check_online(sender_id):
            return
        if sender_id in self.authorized:
            await self.authorized[sender_id].messages_read(reader_id)

