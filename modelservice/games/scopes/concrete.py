from collections import defaultdict, OrderedDict
from functools import reduce

import asyncio
import json

from django.conf import settings

import aiorwlock
from genericclient_base import BaseResource as Resource

from .base import WampScope, Scope
from .exceptions import ChangePhaseException, ScopeNotFound, ScopesNotLoaded
from .managers import ScopeManager
from .webhooks import SubscriptionAlreadyExists
from .webhooks import subscribe as webhooks_subscribe

from ..decorators import register, subscribe
from ..registry import registry

from ...webhooks import dispatcher

from ...conf import LOAD_ACTIVE_RUNS


class Result(Scope):
    resource_name = 'result'

    @property
    def role(self):
        if self.json['role'] is None:
            return None
        return self.game.get_scope('role', self.json['role'])

    @property
    def period(self):
        return self.my.parent


class Decision(Scope):
    resource_name = 'decision'

    @property
    def role(self):
        if self.json['role'] is None:
            return None
        return self.game.get_scope('role', self.json['role'])

    @property
    def period(self):
        return self.my.parent


class Period(Scope):
    resource_name = 'period'
    child_scopes_resources = ('decision', 'result',)
    default_child_scope = Decision

    @property
    def scenario(self):
        return self.my.parent

    @property
    def decisions(self):
        return self.game.scopes['decision'].filter(period=self.pk)

    @property
    def results(self):
        return self.game.scopes['result'].filter(period=self.pk)


class Scenario(Scope):
    resource_name = 'scenario'
    child_scopes_resources = ('period',)

    @property
    def world(self):
        if self.json['world'] is None:
            return None
        return self.game.get_scope('world', self.json['world'])

    @property
    def runuser(self):
        if self.json['runuser'] is None:
            return None
        return self.game.get_scope('runuser', self.json['runuser'])

    @property
    def periods(self):
        return self.game.scopes['period'].filter(scenario=self.pk)


class World(Scope):
    resource_name = 'world'
    child_scopes_resources = ('scenario',)

    @property
    def run(self):
        return self.my.parent

    @property
    def world(self):
        return self

    @property
    def scenarios(self):
        return self.game.scopes['scenario'].filter(world=self.pk)

    @property
    def runusers(self):
        return self.game.scopes['runuser'].filter(world=self.pk)


class RunUser(Scope):
    resource_name = 'runuser'
    child_scopes_resources = ('scenario',)

    @property
    def run(self):
        return self.my.parent

    @property
    def world(self):
        if self.json['world'] is None:
            return None
        return self.game.get_scope('world', self.json['world'])

    @property
    def scenarios(self):
        return self.game.scopes['scenario'].filter(runuser=self.pk)

    @register
    def get_scenarios(self, *args, **kwargs):
        return [
            scope._scope_tree(*args, **kwargs)
            for scope in self.scenarios
        ]

    @property
    def leader(self):
        return self.json['leader']

    @property
    def role(self):
        if self.json['role'] is None:
            return None
        return self.game.get_scope('role', self.json['role'])

    async def remove(self, payload):
        """
        Call parent Run on_runuser_deleted, notify parent Run subscribers,
        and remove scope.
        """
        self.log.debug('remove: {name} pk: {pk}',
                       name=self.resource_name, pk=self.pk)

        if self.run is not None:
            await self.run.on_runuser_deleted(payload)
            self.run.publish('remove_child', self.pk, self.resource_name,
                             self.json)

        await super(RunUser, self).remove(payload)

    def update_webhook(self, resource_name, payload, **kwargs):
        self.log.debug('update_webhook: {name} pk: {pk}',
                       name=self.resource_name, pk=self.pk)
        # updating a RunUser may require updating its manager's 'world' index
        world_changed = payload['world'] != self.json['world']
        if world_changed:
            self.game.scopes['runuser'].remove(self)
        self.json = payload
        if world_changed:
            self.game.scopes['runuser'].add(self)
        self.update_pubsub()

    def update_pubsub(self):
        """
        Notify parent Run subscribers.
        """
        self.log.debug('update_pubsub: {name} pk: {pk}',
                       name=self.resource_name, pk=self.pk, )

        super(RunUser, self).update_pubsub()
        self.run.publish(
            'update_child', self.pk, self.resource_name, self.json)


class Run(Scope):
    resource_name = 'run'
    child_scopes_resources = ('runuser', 'world',)
    default_child_scope = World
    world = None

    ChangePhaseException = ChangePhaseException

    def __init__(self, *args, **kwargs):
        super(Run, self).__init__(*args, **kwargs)

    @property
    def parent(self):
        return self.game

    @property
    def run(self):
        return self

    @property
    def world(self):
        return None

    @property
    def worlds(self):
        return self.game.scopes['world'].filter(run=self.pk)

    @property
    def runusers(self):
        return self.game.scopes['runuser'].filter(run=self.pk)

    @property
    def current_phase(self):
        try:
            return [phase for phase in self.game.phases if
                    phase.pk == self.json['phase']][0]
        except IndexError:
            return None

    async def on_runuser_deleted(self, payload):
        """
        Override this hook to provide custom behavior after deleting
        a runuser from a run
        """
        pass

    async def on_runuser_created(self, runuser_id):
        """
        Override this hook to provide custom behavior after adding
        a runuser to a run
        """
        pass

    async def add_child_scope(self, scope):
        """
        Push a scope instance into `child_scopes`.
        If child is a runuser, call on_runuser_created.
        Also, publish to Run topic subscribers.
        """
        self.log.debug(
            'add_child_scope: parent {name} pk: {pk}, child {child} pk: {child_pk}',
            name=self.resource_name,
            pk=self.pk,
            child=scope.resource_name,
            child_pk=scope.pk,
        )

        await self.game.add_scopes(scope)
        if scope.resource_name == 'runuser':
            await self.on_runuser_created(scope.pk)

        self.publish('add_child',
                     scope.pk,
                     scope.resource_name,
                     scope.json)

    def update_pubsub(self):
        """
        Propagate update down to child worlds and runusers, so they
        are notified their parent Run has changed. This ensures players are
        notified of phase changes, etc.
        TODO How does publishing update_child when parent changes accomplish this?
        """
        super(Run, self).update_pubsub()
        for world in self.worlds:
            world.publish(
                'update_child', self.pk, self.resource_name, self.json)

    def get_phase(self, order):
        phase = self.current_phase
        if phase is None:
            raise ValueError("Run {} doesn't have any phase.".format(self.pk))

        return [phase for phase in self.game.phases if
                phase.json['order'] == order][0]

    def get_next_phase(self):
        phase = self.current_phase
        order = phase.json['order'] + 1
        try:
            return self.get_phase(order)
        except IndexError:
            raise ValueError(
                "Run {}: There isn't any phase available after '{}'".format(
                    self.pk, phase.json['name'],
                ))

    async def get_previous_phase(self):
        phase = self.current_phase
        order = phase.json['order'] - 1
        try:
            return self.get_phase(order)
        except IndexError:
            raise ValueError(
                "Run {}: There isn't any phase available before '{}'".format(
                    self.pk, phase.json['name'],
                ))

    async def on_advance_phase(self, next_phase):
        """
        Override this hook to provide custom behavior after advancing the run
        to the next phase.
        """
        pass

    async def on_rollback_phase(self, previous_phase):
        """
        Override this hook to provide custom behavior after reverting the run
        to the previous phase.
        """
        pass

    @register
    async def advance_phase(self, *args, **kwargs):
        next_phase = self.get_next_phase()
        self.json['phase'] = next_phase.pk
        await self.save()
        await self.on_advance_phase(next_phase)

    @register
    async def rollback_phase(self, *args, **kwargs):
        previous_phase = self.get_previous_phase()
        self.json['phase'] = previous_phase.pk
        await self.save()
        await self.on_rollback_phase(previous_phase)


class Phase(Scope):
    resource_name = 'phase'
    resource_name_plural = 'phases'


class Role(Scope):
    resource_name = 'role'
    resource_name_plural = 'roles'


class Game(WampScope):
    resource_name = 'game'

    child_scopes_resources = ('run', 'phase', 'role')
    default_child_resource = 'run'

    scopes = defaultdict(ScopeManager)

    run = None
    world = None

    game_subscription = None
    users_subscription = None

    locks = defaultdict(aiorwlock.RWLock)

    def __init__(self, session, slug):
        self.slug = slug
        super(Game, self).__init__(session)

    @classmethod
    async def create(cls, session, slug):
        self = cls(session, slug)
        self.pk = await self.get_pk()
        return self

    @property
    def game(self):
        return self

    @property
    def runuser_class(self):
        return self.resource_classes['runuser']

    @property
    def scenario_class(self):
        return self.resource_classes['scenario']

    @property
    def parent(self):
        return None

    @property
    def run(self):
        return None

    @property
    def world(self):
        return None

    @property
    def phases(self):
        return self.scopes['phase']

    @property
    def roles(self):
        return self.scopes['role']

    @property
    def runs(self):
        return self.scopes['run']

    async def load(self):
        self.json = await self.storage.load(slug=self.slug)
        return self.json

    async def start(self):
        await self.load()
        self.pk = await self.get_pk()
        await super(Game, self).start()

    async def _filter(self, endpoint, params):
        # return consolidated query results
        results = []
        while True:
            resources = await endpoint.filter(**params)
            results += resources
            link = resources.response.links.get('next')
            if link is not None:
                params = {}
                endpoint.url = link['url']
                # self.log.info('next url: {url}', url=endpoint.url)
            else:
                break
        return results

    async def restore_endpoint(self, endpoint, scope_class, params={},
                               parent_name=None, parent_ids=[]):
        # return a manager for endpoint's scopes
        params['game_slug'] = self.slug
        self.log.debug("params: {params!s}", params=params)
        results = await self._filter(endpoint, params)

        scopes = []
        for result in results:
            scope = await scope_class.create(self.session,
                                             game=self,
                                             json=result.payload)
            scopes.append(scope)

        manager = ScopeManager(*scopes)
        self.log.debug(
            'restore_endpoint: loaded {result_count} results managed as {mgr_count} {scope_class} scopes',
            result_count=len(results),
            mgr_count=manager.count(),
            scope_class=scope_class)

        if len(results) != manager.count():
            raise ScopesNotLoaded(
                'Restored only {mgr_count} of {result_count} {scope_class}.',
                mgr_count=manager.count(),
                result_count=len(results),
                scope_class=scope_class)
        return manager

    async def restore_run(self, run_pk):
        # load newly activated run and all its child scopes
        run_scopes = []
        for endpoint_name, scope_class in self.endpoint_to_classes.items():
            endpoint = getattr(self.games_client, endpoint_name)

            if endpoint_name == 'phases' or endpoint_name == 'roles':
                continue
            elif endpoint_name == 'runs':
                result = await endpoint.get(id=run_pk)
                scope = await scope_class.create(self.session,
                                                 game=self,
                                                 json=result.payload)
                self.scopes[scope_class.resource_name].append(scope)
                run_scopes.append(scope)
                self.log.debug('loaded activated run {pk}', pk=run_pk)
            else:
                manager = \
                    await self.restore_endpoint(endpoint,
                                                scope_class,
                                                params={'run': run_pk})
                scope_class_manager = self.scopes[scope_class.resource_name]
                for scope in manager:
                    scope_class_manager.append(scope)
                    run_scopes.append(scope)
                self.log.debug('loaded all {len} {children} of activated run',
                               len=len(manager), children=endpoint_name)

        for scope in run_scopes:
            await scope.start()

        self.log.info('Started {total} scopes of activated run',
                      total=len(run_scopes))

    async def restore(self):
        # load all child scopes
        if LOAD_ACTIVE_RUNS:
            for endpoint_name, scope_class in self.endpoint_to_classes.items():
                endpoint = getattr(self.games_client, endpoint_name)

                if endpoint_name == 'phases' or endpoint_name == 'roles':
                    manager = await self.restore_endpoint(endpoint,
                                                          scope_class)
                    self.scopes[scope_class.resource_name] = manager
                elif endpoint_name == 'runs':
                    manager = \
                        await self.restore_endpoint(endpoint,
                                                    scope_class,
                                                    params={'active': True})
                    self.scopes[scope_class.resource_name] = manager
                    self.log.debug('loaded all active runs')
                else:
                    manager = \
                        await self.restore_endpoint(endpoint,
                                                    scope_class,
                                                    params={
                                                        'run_active': True})
                    self.scopes[scope_class.resource_name] = manager
                    self.log.debug('loaded all {children} of active runs',
                                   children=endpoint_name)
        else:
            for endpoint_name, scope_class in self.endpoint_to_classes.items():
                endpoint = getattr(self.games_client, endpoint_name)
                manager = await self.restore_endpoint(endpoint, scope_class)
                self.scopes[scope_class.resource_name] = manager

        # start scopes
        scopes = []
        for manager in self.scopes.values():
            scopes += [scope for scope in manager]

        total = len(scopes)
        int_progress = 0
        self.log.info('Starting scopes {progress!r}%...',
                      progress=int_progress)
        for i, scope in enumerate(scopes):
            progress = (i / total) * 100
            if int(progress) != int_progress:
                int_progress = int(progress)
                if int_progress % 5 == 0:
                    self.log.info('Starting scopes {progress!r}%...',
                                  progress=int_progress)
            await scope.start()

    async def unload_inactive_run_scope_tree(self, run):
        """
        Unloads the run and its children without publishing delete notifications
        """
        self.log.info('unload_inactive_run_scope_tree: pk: {pk}', pk=run.pk)
        await run._unload_scope_tree()

    async def get_pk(self):
        json = await self.storage.load(slug=self.slug)
        return json.get('id')

    def get_routing(self, name):
        route = settings.ROOT_TOPIC + '.model.{}.{}'.format(self.resource_name,
                                                            name)
        return route

    def get_scope(self, resource_name, pk):
        try:
            return self.scopes[resource_name].get(id=pk)
        except KeyError:
            raise ScopeNotFound(
                "Scope {} {} not found".format(resource_name, pk))

    async def add_scopes(self, *scopes):
        for scope in scopes:
            self.scopes[scope.resource_name].add(scope)
            await scope.start()

    async def remove_scopes(self, *scopes):
        for scope in scopes:
            await scope.stop()
            self.scopes[scope.resource_name].remove(scope)

    async def subscribe_webhook(self):
        # Subscribe to game-specific webhooks from `Simpl-Games-API`
        async with self.games_client as api_session:
            if self.game_subscription is None:
                try:
                    self.game_subscription = \
                        await webhooks_subscribe(api_session, self.slug)
                    self.log.info('webhook registered for prefix `{prefix}.*`',
                                  prefix=self.slug)
                except SubscriptionAlreadyExists as exc:
                    pass

            # Subscribe to users-related webhooks from `Simpl-Games-API`
            if self.users_subscription is None:
                try:
                    self.users_subscription = \
                        await webhooks_subscribe(api_session, 'user')
                    self.log.info('webhook registered for prefix `{prefix}.*`',
                                  prefix='user')
                except SubscriptionAlreadyExists as exc:
                    pass

    @register
    def get_phases(self, *args, **kwargs):
        return [phase.json for phase in self.phases]

    @register
    async def get_roles(self, *args, **kwargs):
        return [role.json for role in self.roles]

    @register
    def list_scopes(self, *args, **kwargs):
        scopes = {}
        for k, scope_group in self.scopes.items():  # TODO fix items()
            if k not in scopes:
                scopes[k] = {}

            for scope in scope_group:
                scopes[k][scope.pk] = scope.json
        return scopes

    @subscribe
    def hello_game(self, *args, **kwargs):
        """
        Identifies the user and the game that it's currently running.
        Mostly for debugging and profiling purposes.
        """
        self.log.info('hello user `{email}`! Welcome to {slug}.',
                      email=kwargs['user'].email, slug=self.slug)

    @subscribe
    async def webhook_forward(self, payload, *args, **kwargs):
        self.log.debug("Received callback.")
        self.log.debug("{body!r}", body=payload['body'])

        body = json.loads(payload['body'])
        dispatcher.dispatch(body)
        await dispatcher.forward(self, body)

    def ready(self, *args, **kwargs):
        return True

    @classmethod
    def register(cls, slug, resource_classes):
        """
        from modelservice.games import Run, Game

        class CalcRun(Run):
            pass


        Game.register('simpl-calc', [
            CalcRun,
        ])
        """
        resource_classes_map = {c.resource_name: c for c in
                                default_resource_classes}
        for scope_class in resource_classes:
            resource_classes_map[scope_class.resource_name] = scope_class

        cls.resource_classes = resource_classes_map

        cls.endpoint_to_classes = OrderedDict([
            ('phases', cls.resource_classes['phase']),
            ('roles', cls.resource_classes['role']),
            ('runs', cls.resource_classes['run']),
            ('worlds', cls.resource_classes['world']),
            ('runusers', cls.resource_classes['runuser']),
            ('scenarios', cls.resource_classes['scenario']),
            ('periods', cls.resource_classes['period']),
            ('decisions', cls.resource_classes['decision']),
            ('results', cls.resource_classes['result']),
        ])

        registry.register(cls, slug)

    def __repr__(self):
        return "<Scope {} slug: {} pk: {}>".format(self.resource_name,
                                                   self.slug, self.pk)


default_resource_classes = (
    Phase,
    Role,
    Run,
    World,
    RunUser,
    Scenario,
    Period,
    Decision,
    Result,
)
