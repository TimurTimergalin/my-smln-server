class Config(dict):
    def __init__(self, *args, _check_children=False, **kwargs):
        super().__init__(*args, **kwargs)
        if _check_children:
            cls = type(self)
            for key, val in self.items():
                if isinstance(val, dict):
                    self[key] = cls(val)

    def __getattr__(self, item):
        if item in self:
            return self[item]
        raise AttributeError(item)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, item):
        if item in self:
            del self[item]

        raise AttributeError(item)


from config.json_config import json_config

try:
    from config.yaml_config import yaml_config
except ImportError:
    pass
