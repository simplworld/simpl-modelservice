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

        # TODO figure out why we're not receiving user notifications and correct
        # if resource_name == 'user':
        #     if action == 'changed':
        #         runusers = \
        #             await games_client.runusers.filter(user=payload['id'],
        #                                                game_slug=game.slug)
        #         for runuser in runusers:
        #             # update runuser scope user info: email, first_name, last_name
        #             self.log.info('TODO use user payload: {user}'.format(user=payload))
        #             self.log.info('to update runuser scope of resource: {runuser}'.format(runuser=runuser))

        if resource_name == 'game':
            # Send a very loud message advising not to delete games and
            # stating the modelservice needs to be restarted
            game.log.error(
                "Deleting games is not recommended. Please restart the modelservice for game `{game_slug}`",
                game_slug=game.slug)
            return

        # Scopes -- each scope instance has a single designated parent
        parent_resources = SCOPE_PARENT_GRAPH[resource_name]
        for parent_resource in parent_resources:
            parent_pk = payload[parent_resource]
            if parent_pk is None:
                continue

            pk = payload['id']

            # Make sure the parent had the time to be instantiated
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
                    await scope.remove(payload)
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
