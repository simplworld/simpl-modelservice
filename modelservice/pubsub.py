from autobahn.wamp import types

from .base import WampRegistry, RegisterDecorator


class PubSubRegistry(WampRegistry):
    OptionsClass = types.SubscribeOptions


registry = PubSubRegistry()


class subscriber(RegisterDecorator):
    registry = registry
