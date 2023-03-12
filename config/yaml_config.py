import yaml
from config import Config


def yaml_config(path):
    with open(path) as f:
        res = yaml.safe_load(f)
    return Config(res, _check_children=True)
