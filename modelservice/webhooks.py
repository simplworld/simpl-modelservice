from collections import defaultdict

from autobahn.wamp import types
from twisted.logger import Logger

from .base import Registry, RegisterDecorator

from .games.scopes.constants import SCOPE_PARENT_GRAPH
from .games.scopes.exceptions import ScopeNotFound
from .simpl import games_client

log = Logger()


class WebhookRegistry(Registry):
    OptionsClass = types.RegisterOptions

    _registry = defaultdict(list)

    def register(self, func, key):
        log.info("Registering webhook {key}", key=key)
        self._registry[key].append(func)


registry = WebhookRegistry()


class CallbackDispatcher(object):
    def __init__(self, registry):
        self.registry = registry

    async def forward_runuser(self, game, event, data):
        # TODO eliminate RunUser special casing and treat like a Scope
        resource_name = 'run'
        pk = data['run']
        action = event.rsplit('.', 1)[-1]
        try:
            scope = game.get_scope(resource_name, pk)
            await getattr(scope, 'runuser_{}'.format(action))(payload=data)
        except ScopeNotFound:
            pass

    def dispatch(self, data):
        event = data['event']
        payload = data['data']
        ref = data['ref']

        log.debug(
            "Dispatch Event: {event} ref: {ref} payload:{payload!r}",
            event=event,
            ref=ref,
            payload=payload,
        )

        # TODO: call non-blocking tasks or functions
        for func in self.registry[event]:
            log.info("Calling {func!r}", func=func)
            func(**payload)

    async def forward(self, game, data):
        event = data['event']
        payload = data['data']
        ref = data['ref']

        log.debug(
            "Forward Event: {event} ref: {ref} payload:{payload!r}",
            event=event,
            ref=ref,
            payload=payload,
        )

        if event.startswith('user'):
            resource_name, action = event.rsplit('.', 2)
        else:
            _, resource_name, action = event.rsplit('.', 2)

        # `User`s and `RunUser`s
        # TODO eliminate RunUser special casing and treat like a Scope
        if resource_name == 'user':
            runusers = \
                await games_client.runusers.filter(user=payload['id'],
                                                   game_slug=game.slug)
            for runuser in runusers:
                await self.forward_runuser(game, event, runuser.payload)
        elif resource_name == 'runuser':
            await self.forward_runuser(game, event, payload)

        elif resource_name == 'game':
            # TODO: the best thing to do here is to send a very loud message
            # TODO: advising not to delete games and informing that the
            # TODO: modelservice needs to be restarted
            game.log.error(
                "Deleting games is not recommended. Please restart the modelservice for game `{game_slug}`",
                game_slug=game.slug)
            return

        # Scopes -- each scope instance has a single parent
        parent_resources = SCOPE_PARENT_GRAPH[resource_name]
        for parent_resource in parent_resources:
            parent_pk = payload[parent_resource]
            if parent_pk is None:
                continue

            pk = payload['id']

            # Make sure the parent had the time to be instantiantiated
            if action == 'created':
                try:
                    if parent_resource == 'game':
                        await game.add_child_webhook(resource_name, payload)
                    else:
                        scope = game.get_scope(parent_resource, parent_pk)
                        await scope.add_child_webhook(resource_name, payload)
                except ScopeNotFound:
                    log.debug(
                        "ScopeNotFound action:{action} parent:{parent} pk:{pk} child:{child} payload:{payload!r} not found in forward",
                        action=action,
                        parent=parent_resource,
                        pk=parent_pk,
                        child=resource_name,
                        payload=payload,
                    )
                    return

            elif action == 'deleted':
                try:
                    scope = game.get_scope(resource_name, pk)
                    await scope.remove()
                except ScopeNotFound:
                    log.debug(
                        "ScopeNotFound action:{action} pk:{pk} resource:{child} payload:{payload!r} not found in forward",
                        action=action,
                        pk=parent_pk,
                        resource=resource_name,
                        payload=payload,
                    )
                    return

            elif action == 'changed':
                try:
                    scope = game.get_scope(resource_name, pk)
                    scope.update_webhook(resource_name, payload)
                except ScopeNotFound:
                    log.debug(
                        "ScopeNotFound action:{action} pk:{pk} resource:{child} payload:{payload!r} not found in forward",
                        action=action,
                        pk=parent_pk,
                        resource=resource_name,
                        payload=payload,
                    )
                    return


dispatcher = CallbackDispatcher(registry)


class hook(RegisterDecorator):
    registry = registry
