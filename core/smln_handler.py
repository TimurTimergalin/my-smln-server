class SMLNHandler:
    def __init__(self):
        self.handler_dict = {}
        self.invalid_type = None
        self.server_error = None

    def handler(self, func):
        self.handler_dict[func.__name__.replace('_', '-')] = func
        return func

    def on_unknown_type(self, func):
        self.invalid_type = func
        return func

    def on_server_error(self, func):
        self.server_error = func
        return func

    async def handle(self, conn, type_, args):
        handler = self.handler_dict.get(type_, None)
        if handler is None:
            await self.invalid_type(conn, type_)
        else:
            try:
                await handler(conn, args)
            except Exception as e:
                print(e.__traceback__)  # TODO: logging
                await self.server_error(conn, type_)
