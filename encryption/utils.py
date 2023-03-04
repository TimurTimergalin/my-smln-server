import base64
import os


def generate_salt():
    return base64.b64encode(os.urandom(16))
