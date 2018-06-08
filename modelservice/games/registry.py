import types

from attr import attrs, attrib, validators, Factory

from modelservice.base import Registry


@attrs
class MethodRegistration(object):
    method = attrib(validator=validators.instance_of(types.FunctionType))
    name = attrib(validator=validators.instance_of((str)))
    options = attrib(validator=validators.instance_of(dict))


class MethodRegistry(list):
    def add(self, *args, **kwargs):
        registration = MethodRegistration(*args, **kwargs)
        self.append(registration)


@attrs
class ScopeRegistration(object):
    registered = attrib(default=Factory(MethodRegistry))
    subscribed = attrib(default=Factory(MethodRegistry))
    hooked = attrib(default=Factory(MethodRegistry))


methods_registry = ScopeRegistration()


class GameRegistry(Registry):
    def register(self, func, key):
        if key in self._registry:
            raise ValueError('Key `{}` is already registered.'.format(key))
        self._registry[key] = func


registry = GameRegistry()
