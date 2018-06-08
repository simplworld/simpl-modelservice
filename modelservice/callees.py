from autobahn.wamp import types

from .base import WampRegistry, RegisterDecorator


class CalleeRegistry(WampRegistry):
    OptionsClass = types.RegisterOptions


registry = CalleeRegistry()


class callee(RegisterDecorator):
    registry = registry
