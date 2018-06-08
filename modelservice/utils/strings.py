import base64
import json


def encode_dict(dict_):
    return base64.b64encode(json.dumps(dict_).encode('utf8')).decode('utf8')


class UnformattableString(str):
    def format(self, *args, **kwargs):
        return self


def no_format(some_string):
    return UnformattableString(some_string)
