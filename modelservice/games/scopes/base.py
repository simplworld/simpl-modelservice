import asyncio
import warnings

from django.conf import settings
from django.utils.module_loading import import_string

from modelservice import conf
from modelservice.utils.functional import classproperty

from .constants import SCOPE_PARENT_GRAPH
from .exceptions import ScopeNotFound, ParentScopeNotFound
from .traversing import Traversing
from .wamp import ScopeWamp

from ..decorators import register, subscribe

from ...simpl import games_client


class ScopeMixin(object):
    def __eq__(self, other):
        if hasattr(other, 'resource_name') and hasattr(other, 'pk'):
            return self.resource_name == other.resource_name and self.pk == other.pk
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        key = "{}:{}".format(self.resource_name, self.pk)
        return hash(key)


class SessionScope(object):
    def __init__(self, session):
        self.session = session
        self.log = self.session.log
        super(SessionScope, self).__init__()


class WampScope(ScopeMixin, SessionScope):
    resource_classes = {}
    child_scopes_resources = tuple()
    default_child_resource = None

    initial_json = {
        'data': {}  # ensure scopes always have non-null json data property
    }
    resource_name = 'undefined'
    resource_name_plural = None
    online_runusers = set()

    pk = None
    slug = None

    registered = []
    subscribed = []
    hooked = []

    def __init__(self, session):
        super(WampScope, self).__init__(session)
        self.games_client = games_client

        self.child_scopes_classes = [
            self.game.resource_classes[resource_name]
            for resource_name in self.child_scopes_resources
        ]

        if self.resource_name_plural is None:
            self.resource_name_plural = self.resource_name + 's'

        Storage = import_string(conf.SCOPE_STORAGE)
        self.json = self.initial_json
        self.storage = Storage(self)
        self.my = Traversing(self)
        self.wamp = ScopeWamp(self)

    def __repr__(self):
        return "<Scope {} pk: {}>".format(self.resource_name, self.pk)

    def __del__(self):
        pass

    @classmethod
    async def create(cls, session):
        self = cls(session)
        self.pk = await self.get_pk()
        return self

    async def get_pk(self):
        if 'id' not in self.json:
            await self.save()
        return self.json.get('id')

    async def start(self):
        await self.wamp.join()
        self.onStart()

    async def stop(self):
        if hasattr(self, 'wamp'):
            await self.wamp.leave()
            self.onStop()

    def onStart(self):
        pass

    def onStop(self):
        pass

    async def add_child_scope(self, scope):
        """
        Push a scope instance into `child_scopes`.
        Also, notifies any associated World or Runusers.
        """
        self.log.debug(
            'add_child_scope: parent {name} pk: {pk}, child {child} pk: {child_pk}',
            name=self.resource_name,
            pk=self.pk,
            child=scope.resource_name,
            child_pk=scope.pk,
        )

        await self.game.add_scopes(scope)

        if scope.my.world is not None:
            scope.my.world.publish('add_child',
                                   scope.pk,
                                   scope.resource_name,
                                   scope.json)

        if scope.my.runusers is not None:
            for runuser in scope.my.runusers:
                runuser.publish('add_child',
                                scope.pk,
                                scope.resource_name,
                                scope.json)

        return scope

    async def remove(self, payload=None):
        """
        Remove scope and notify any associated World and Runusers.
        Subclasses that override this method can pass the payload argument to
        an on_deleted hook.
        """
        self.log.debug('remove: {name} pk: {pk}',
                       name=self.resource_name, pk=self.pk)
        try:
            if self.my.world is not None:
                self.my.world.publish('remove_child', self.pk,
                                      self.resource_name,
                                      self.json)
        except ParentScopeNotFound as ex:
            self.log.debug('{e!s}', e=ex)
            pass

        try:
            for runuser in self.my.runusers:
                runuser.publish('remove_child', self.pk,
                                self.resource_name,
                                self.json)
        except ParentScopeNotFound as ex:
            self.log.debug('{e!s}', e=ex)
            pass

        await self.my.game.remove_scopes(self)

    def update_pubsub(self):
        """
        Publishes the scope update to the browsers
        by notifying any associated World or Runusers.
        """
        self.log.debug('update_pubsub: {name} pk: {pk}',
                       name=self.resource_name, pk=self.pk, )

        if self.my.world is not None:
            self.my.world.publish('update_child', self.pk, self.resource_name,
                                  self.json)

        if self.my.runusers is not None:
            for runuser in self.my.runusers:
                runuser.publish('update_child', self.pk, self.resource_name,
                                self.json)

    async def remove_child(self, scope, payload=None):
        self.log.debug(
            'remove_child: parent {name} pk: {pk}, child {child} pk: {child_pk}',
            name=self.resource_name, pk=self.pk,
            child=scope.resource_name, child_pk=scope.pk
        )

        await scope.remove(payload)

    async def add_child_webhook(self, resource_name, payload, *args, **kwargs):
        try:
            # test whether scope has been loaded
            self.game.get_scope(resource_name, payload['id'])

            self.log.debug(
                "add_child_webhook: parent {resource_name} payload: '{payload!r}'",
                resource_name=resource_name, payload=payload)
        except ScopeNotFound:
            await self.add_new_child_scope(
                resource_name=resource_name,
                json=payload)  # also adds to game.scopes

            self.log.debug(
                "add_child_webhook: scope not found, creating. parent {resource_name} payload: '{payload!r}'",
                resource_name=resource_name, payload=payload)

    async def remove_child_webhook(self, resource_name, payload, **kwargs):
        self.log.debug(
            "remove_child_webhook: parent {name} payload: '{payload!r}",
            name=resource_name, payload=payload)

        scope = self.game.get_scope(resource_name, payload['id'])
        await self.remove_child(scope)

    def update_webhook(self, resource_name, payload, **kwargs):
        self.json = payload
        self.update_pubsub()

    async def add_new_child_scope(self, resource_name, json=None):
        """
        Adds a new instance of `self.ChildScope` to `child_scopes`.

        It will also publish a notification on this scope's World or Runuser.
        """
        self.log.debug(
            'add_new_child_scope: parent {parent} pk: {pk}, child {child}',
            parent=self.resource_name,
            pk=self.pk,
            child=resource_name
        )

        json[self.resource_name] = self.pk

        # instantiate game resource_classes to pickup game-specific endpoints
        ChildScope = self.game.resource_classes[resource_name]
        scope = \
            await ChildScope.create(
                session=self.session, game=self.my.game, json=json)
        await self.add_child_scope(scope)
        return scope

    def get_routing(self, name):
        route = settings.ROOT_TOPIC + '.model.{}'.format(self.resource_name)
        if self.pk is not None:
            route += '.{}'.format(self.pk)
        route += '.{}'.format(name)
        return route

    @classproperty
    def resource_name_plural(cls):
        return cls.resource_name + 's'

    @classproperty
    def parent_resource_names(cls):
        return SCOPE_PARENT_GRAPH[cls.resource_name]

    @property
    def child_scopes(self):
        return self.my.child_scopes

    def publish(self, topic, *args, **kwargs):
        model_topic = self.get_routing(topic)

        self.log.debug("publishing to `{}`".format(model_topic))

        self.session.publish(
            model_topic,
            resource_name=self.resource_name, pk=self.pk,
            *args, **kwargs
        )

    async def call(self, procedure, *args, **kwargs):
        """
        Calls the the specified WAMP RPC, and return its result.

        Example::
            myscope.call('remote.procedure', 'argument1', keyword1='keyword')

        Note that the procedure name will be passed as it is, and
        `Scope.get_routing` will not get called on it.
        """
        self.log.debug("calling procedure `{name}`", name=procedure)

        result = await self.session.call(procedure, *args, **kwargs)
        return result

    @register
    def get_scope(self, *args, **kwargs):
        """
        Returns this scope serialized.
        """
        return self.pubsub_export()

    def _scope_tree(self, exclude=None, *args, **kwargs):
        """
        Returns this scope and its children serialized.
        """
        user = kwargs['user']
        payload = self.pubsub_export()
        payload['children'] = []
        scope_groups = self.child_scopes
        for resource_name, scope_group in scope_groups.items():
            self.log.debug(
                '_scope_tree: resource_name: {name}, user: {user!s}, exclude: {exclude!s}',
                name=resource_name, user=user, exclude=exclude)

            if exclude is not None and resource_name in exclude:
                self.log.debug(
                    '_scope_tree: exclude {name} children', name=resource_name)
            else:
                children = scope_group.for_user(user)

                self.log.debug('_scope_tree: children: {children!s}',
                               children=children)

                payload['children'] += \
                    [child._scope_tree(exclude, *args, **kwargs)
                     for child in children]
        return payload

    @register
    def get_scope_tree(self, exclude=None, *args, **kwargs):
        self.log.debug('get_scope_tree: {name} pk: {pk} exclude: {exclude!s}',
                       name=self.resource_name, pk=self.pk, exclude=exclude)

        return self._scope_tree(exclude, *args, **kwargs)

    async def _unload_scope_tree(self):
        """
        Removes this scope and all its children from game's scopes.
        """
        self.log.debug('_unload_scope_tree: resource_name: {name} pk: {pk}',
                       name=self.resource_name, pk=self.pk)

        scope_groups = self.child_scopes
        for resource_name, scope_group in scope_groups.items():
            for scope in scope_group:
                await scope._unload_scope_tree()

        await self.my.game.remove_scopes(self)

    def pubsub_export(self):
        """
        Serializes the scope so it can be transmitted over pubsub and used by
        the frontend.
        """
        payload = {
            'pk': self.pk,
            'data': self.json,
            'resource_name': self.resource_name,
        }
        return payload

    @subscribe
    def connected(self, *args, **kwargs):
        user = kwargs['user']

        self.log.debug(
            "User {email} (runuser.pk={pk}) Connected",
            email=user.email, pk=user.runuser.pk)

        self.online_runusers.add(user.runuser.pk)

        payload = user.runuser.payload
        payload['online'] = True
        self.publish('update_child', user.runuser.pk, 'runuser', payload)
        return self.onConnected(*args, **kwargs)

    @subscribe
    def disconnected(self, *args, **kwargs):
        user = kwargs['user']

        self.log.debug("User {email}  (runuser.pk={pk}) Disconnected",
                       email=user.email, pk=user.runuser.pk)

        try:
            self.online_runusers.remove(user.runuser.pk)
        except KeyError:
            pass

        payload = user.runuser.payload
        payload['online'] = False
        if self.my.world:
            self.my.world.publish('update_child', user.runuser.pk, 'runuser',
                                  payload)
        if self.my.run:
            self.my.run.publish('update_child', user.runuser.pk, 'runuser',
                                payload)
        return self.onDisconnected(*args, **kwargs)

    def onConnected(self, *args, **kwargs):
        """
        This method will be called when a client connects to this scope,
        most likely because a React component has just been mounted / updated.
        """
        pass

    def onDisconnected(self, *args, **kwargs):
        """
        This method will be called when a client disconnects from this scope,
        most likely because a React component has just been unmounted / updated,
        or they closed the browser window
        """
        pass

    async def save(self):
        self.json = await self.storage.save(self.json)
        return self.json

    @register
    def get_active_runusers(self, *args, **kwargs):
        runusers = []
        user = kwargs['user']
        for ru in self.my.get_runusers(user.runuser.leader):
            payload = {}
            payload['data'] = ru.json
            payload['data']['online'] = ru.pk in self.online_runusers
            payload['pk'] = ru.pk
            payload['resource_name'] = 'runuser'
            runusers.append(payload)
        return runusers

    def get_initial_json(self):
        return self.initial_json

    @register
    def get_current_run_and_phase(self, *args, **kwargs):
        """ Get the current Run for this scope """

        phase = self.run.current_phase

        if phase is None:
            phase_export = None
        else:
            phase_export = {
                'pk': phase.pk,
                'data': phase.json,
                'resource_name': 'phase',
            }

        return {
            'run': self.run.pubsub_export(),
            'phase': phase_export,
        }


class Scope(WampScope):
    def __init__(self, session, game, json=None):
        self.game = game
        super(Scope, self).__init__(session)
        if json is not None:
            self.json = json

    @classmethod
    async def create(cls, session, game, json=None):
        self = cls(session, game, json)
        self.pk = await self.get_pk()
        return self
