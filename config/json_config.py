import json
from config import Config


def json_config(path):
    with open(path) as f:
        res = json.loads(f.read(), object_hook=Config)
        return res
