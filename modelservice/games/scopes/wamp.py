import traceback

from autobahn.wamp import types
from autobahn.wamp.exception import ApplicationError
from django.conf import settings

from ..inspector import ScopeInspector
from ...utils.strings import no_format


class ScopeWamp(object):
    def __init__(self, scope):
        self.session = scope.session
        self.scope = scope

        self.subscriptions = []
        self.callees = []
        self.started = False

        super(ScopeWamp, self).__init__()

    async def join(self):
        if self.started is False:
            await self.register_methods()
            self.started = True

    async def leave(self):
        if self.started is True:
            await self.unregister_methods()
            self.started = False

    async def _register_callees(self):
        for name, method, options in ScopeInspector.callees(self.scope):
            uri = self.scope.get_routing(method.registered).format(self.scope)
            options = types.RegisterOptions(**options)
            try:
                registered = await self.session.register(
                    method, uri, options=options,
                )
                self.callees.append(registered)
                self.session.log.debug("procedure `{uri}` registered", uri=uri)
            except Exception as e:
                self.session.log.error(uri)
                self.session.log.error(
                    "could not register procedure `{uri}`: {e!r}",
                    uri=uri, e=e)
                self.session.log.error(no_format(traceback.format_exc()))

    async def _unregister_callees(self):
        for callee in self.callees:
            await callee.unregister()

    async def _register_subscribers(self):
        for name, method, options in ScopeInspector.subscribers(self.scope):
            topic = self.scope.get_routing(method.subscribed).format(
                self.scope)
            options = types.SubscribeOptions(**options)
            try:
                subscribed = await self.session.subscribe(
                    method, topic, options=options,
                )
                self.subscriptions.append(subscribed)
                self.session.log.debug("subscriber `{topic}` registered",
                                       topic=topic)
            except Exception as e:
                self.session.log.error(topic)
                self.session.log.error(
                    "could not register subscriber to `{uri}`: {e!r}",
                    uri=topic, e=e)
                self.session.log.error(no_format(traceback.format_exc()))

    async def _register_hooks(self):
        for name, method, options in ScopeInspector.hooks(self.scope):
            global_topic = '{}.webhooks.{}'.format(
                settings.ROOT_TOPIC, method.hooked
            ).format(self.scope)

            options = types.SubscribeOptions(**options)
            try:
                subscribed = await self.session.subscribe(
                    method, global_topic, options=options,
                )
                self.subscriptions.append(subscribed)
                self.session.log.debug("hook `{topic}` registered",
                                       topic=global_topic)
            except Exception as e:
                self.session.log.error(global_topic)
                self.session.log.error(
                    "could not register hook to `{topic}`: {e!r}",
                    topic=global_topic, e=e)
                self.session.log.error(no_format(traceback.format_exc()))

    async def _unregister_subscribers(self):
        for subscriber in self.subscriptions:
            await subscriber.unsubscribe()

    async def register_methods(self):
        await self._register_callees()
        await self._register_subscribers()
        await self._register_hooks()

    async def unregister_methods(self):
        await self._unregister_callees()
        await self._unregister_subscribers()
