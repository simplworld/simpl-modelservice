from collections import defaultdict

from autobahn.wamp import types
from twisted.logger import Logger

from .simpl import games_client

from .base import Registry, RegisterDecorator

from .games.scopes.constants import SCOPE_PARENT_GRAPH
from .games.scopes.exceptions import ScopeNotFound

from .conf import LOAD_ACTIVE_RUNS

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

        game.log.debug(
            "Forward Event: {event} ref: {ref} payload: {payload!r}",
            event=event,
            ref=ref,
            payload=payload,
        )

        if event.startswith('user'):
            resource_name, action = event.rsplit('.', 2)
        else:
            _, resource_name, action = event.rsplit('.', 2)

        if resource_name == 'user':
            if action == 'changed':
                id = payload['id']
                runusers = \
                    await games_client.runusers.filter(user=id,
                                                       game_slug=game.slug)
                for runuser in runusers:
                    # await self.forward_runuser(game, event, runuser.payload)
                    # update runuser scope user info: email, first_name, last_name
                    game.log.debug('publish update runuser scope with pk: {pk}',
                                   pk=runuser.pk)
                    scope = game.get_scope('runuser', runuser.pk)
                    # update monkey patched user properties
                    scope.json['email'] = runuser.email
                    scope.json['first_name'] = runuser.first_name
                    scope.json['last_name'] = runuser.last_name
                    scope.update_pubsub()
            return
        elif resource_name == 'game':
            if action == 'deleted':
                game.log.error(
                    "Deleting games is not recommended. Please stop the modelservice for game `{game_slug}`",
                    game_slug=game.slug)
                return
            elif action == 'changed':
                # update Game Scope. but skip publish
                game.json = payload
                return

        # Scopes -- each scope instance has a single designated parent
        parent_resources = SCOPE_PARENT_GRAPH[resource_name]
        for parent_resource in parent_resources:
            parent_pk = payload[parent_resource]
            if parent_pk is None:
                continue

            if LOAD_ACTIVE_RUNS and parent_resource != 'game' \
                    and payload['run_active'] is False:
                return

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
                    game.log.debug(
                        "ScopeNotFound action: {action} parent: {parent} pk: {pk} of child: {child} not found in forward",
                        action=action,
                        parent=parent_resource,
                        pk=parent_pk,
                        child=resource_name
                    )
                    return

            elif action == 'deleted':
                try:
                    scope = game.get_scope(resource_name, pk)
                    await scope.remove(payload)
                except ScopeNotFound:
                    game.log.debug(
                        "ScopeNotFound action: {action} pk: {pk} resource: {resource} not found in forward",
                        action=action,
                        pk=pk,
                        resource=resource_name,
                    )
                    return

            elif action == 'changed':
                try:
                    scope = game.get_scope(resource_name, pk)
                    if LOAD_ACTIVE_RUNS and resource_name == 'run' \
                            and payload['active'] is False:
                        # remove run and its children from game's scopes
                        await game.unload_inactive_run_scope_tree(scope)
                    else:
                        scope.update_webhook(resource_name, payload)
                except ScopeNotFound:
                    if LOAD_ACTIVE_RUNS and resource_name == 'run' \
                            and payload['active'] is True:
                        # run has been reactivated and needs to be loaded
                        await game.restore_run(pk)
                    else:
                        game.log.debug(
                            "ScopeNotFound action: {action} pk: {pk} resource: {resource} not found in forward",
                            action=action,
                            pk=pk,
                            resource=resource_name,
                        )
                    return


dispatcher = CallbackDispatcher(registry)


class hook(RegisterDecorator):
    registry = registry
