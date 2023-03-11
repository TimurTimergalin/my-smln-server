import traceback
from io import StringIO


class SMLNHandler:
    def __init__(self, logger=None):
        self.logger = logger
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
            except Exception:
                with StringIO() as st:
                    traceback.print_exc(file=st)

                    self.logger.error(st.getvalue())
                await self.server_error(conn, type_)
