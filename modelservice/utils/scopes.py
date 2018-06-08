import inspect
import logging

from django.utils.safestring import mark_safe

from django_markup.markup import formatter

logger = logging.getLogger(__name__)


class MockSession(object):
    """
    A class mocking a WAMP Session.

    Used to instantiate Scopes outside of Crossbar, for introspection or testing.
    """
    log = logger
    messages = []

    def __init__(self):
        self.callees = []
        self.subscribers = []
        self.hooks = []

    def collect(self, method_type, name, method, topic, options):
        prop = getattr(self, method_type)
        prop.append({
            'name': name,
            'method': method,
            'topic': topic,
            'options': options,
            'docstring': method.__doc__,
            'docstring_html': mark_safe(
                method.__doc__ and formatter(method.__doc__,
                                             filter_name='restructuredtext' or None)),
            'signature': inspect.signature(method)
        })

    def register(self, method, topic, options):
        name = method.registered
        self.collect('callees', name, method, topic, options)

    def subscribe(self, method, topic, options):
        if hasattr(method, 'hooked'):
            name = method.hooked
            self.collect('hooks', name, method, topic, options)
        else:
            name = method.subscribed
            self.collect('subscribers', name, method, topic, options)

    def publish(self, *args, **kwargs):
        self.messages.append({'args': args, 'kwargs': kwargs})
