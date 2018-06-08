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

    async def add_or_update_runuser(self, payload) -> None:
        # because RunUser parent is Run, moved from Game
        # TODO eliminate and treat RunUser like a Scope
        runuser_resource = Resource(self.games_client.runusers, **payload)
        try:
            runuser = self.game.get_scope('runuser', runuser_resource.pk)

            self.game.scopes['runuser'].remove(runuser)  # TODO still needed?
            runuser.json = runuser_resource.payload
            self.game.scopes['runuser'].add(runuser)  # TODO still needed?

            self.log.debug(
                'add_or_update_runuser: {name} pk: {pk} updated runuser {id} json: {json!r}',
                name=self.game.resource_name, pk=self.pk,
                id=runuser_resource.pk, json=runuser.json)

        except ScopeNotFound:
            runuser = \
                await self.game.runuser_class.create(
                    self.session, self.game, runuser_resource.payload)

            await self.game.add_scopes(runuser)

            self.log.debug(
                'add_or_update_runuser: {name} pk: {pk} added runuser {id}',
                name=self.game.resource_name, pk=self.pk,
                id=runuser_resource.pk)

            scenario_resources = \
                self.game.scopes['scenario'].filter(
                    runuser=runuser_resource.pk)

            ScenarioClass = self.game.scenario_class
            scenarios = []
            for scenario_resource in scenario_resources:
                scenario = await ScenarioClass.create(
                    self.game.session, self.game, scenario_resource.payload)
                scenarios.append(scenario)
            await self.game.add_scopes(*scenarios)

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

    @subscribe
    async def runuser_deleted(self, payload, **kwargs):
        """
        A `RunUser` has been deleted from `Simpl-Games-API`
        """
        # TODO eliminate and treat RunUser like a Scope
        self.log.debug(
            'Run.runuser_deleted: {name} pk: {pk} deleted runuser {id}',
            name=self.resource_name, pk=self.pk, id=payload['id'])

        runuser = self.game.get_scope('runuser', payload['id'])
        await self.game.remove_scopes(runuser)
        await self.on_runuser_deleted(payload)

    @subscribe
    async def runuser_changed(self, payload, **kwargs):
        """
        A `RunUser` has been changed from `Simpl-Games-API`
        """
        # TODO eliminate and treat RunUser like a Scope
        self.log.debug(
            'Run.runuser_changed: {name} pk: {pk} updated runuser {id}',
            name=self.resource_name, pk=self.pk, id=payload['id'])

        await self.add_or_update_runuser(payload)

    @subscribe
    async def runuser_created(self, payload, **kwargs):
        """
        A `RunUser` has been created from `Simpl-Games-API`
        """
        # TODO eliminate and treat RunUser like a Scope

        self.log.debug(
            'Run.runuser_created: {name} pk: {pk} created runuser {id}',
            name=self.resource_name, pk=self.pk, id=payload['id'])

        await self.add_or_update_runuser(payload)
        await self.on_runuser_created(payload['id'])

    def update_pubsub(self):
        """
        Propagate the run's update down to its worlds, so they can be notified
        when the Run closes.
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

    async def restore_endpoint(self, endpoint, scope_class):
        # return a manager for endpoint's scopes

        params = {'game_slug': self.slug}
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

    async def restore(self):
        # load all child scopes
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
                        await webhooks_subscribe(api_session, 'users')
                    self.log.info('webhook registered for prefix `{prefix}.*`',
                                  prefix='users')
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
            ('roles', cls.resource_classes['role']),
            ('phases', cls.resource_classes['phase']),
            ('runs', cls.resource_classes['run']),
            ('runusers', cls.resource_classes['runuser']),
            ('worlds', cls.resource_classes['world']),
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
    RunUser,
    World,
    Scenario,
    Period,
    Decision,
    Result,
)
