from typing import Dict

from django.utils.functional import cached_property

from .exceptions import ScopeNotFound, ParentScopeNotFound
from .managers import ScopeManager


class Traversing(object):
    def __init__(self, scope):
        self.scope = scope
        self.game = self.scope.game
        self.resource_name = scope.resource_name
        self.log = scope.log  # Not used in this file, but useful for debugging in the future
        super(Traversing, self).__init__()

    @cached_property
    def parent(self):
        if self.resource_name == 'game':
            return None

        parent_resources = self.scope.parent_resource_names
        # Use the first non-null parent
        for parent_resource in parent_resources:
            parent_pk = self.scope.json[parent_resource]
            if parent_pk is not None:
                break

        if parent_resource == 'game' and parent_pk == self.game.pk:
            return self.game
        try:
            return self.game.get_scope(parent_resource, parent_pk)
        except ScopeNotFound:
            raise ParentScopeNotFound("Can't find scope {} {}, parent of {} {}".format(
                parent_resource, parent_pk,
                self.resource_name,
                self.scope.pk,
            ))

    @property
    def child_scopes(self) -> Dict[str, ScopeManager]:
        child_resources = self.scope.child_scopes_resources  # names of child scopes
        children = {}
        for child_resource in child_resources:
            children[child_resource] = self.game.scopes[child_resource].filter(
                **{self.resource_name: self.scope.pk}
            )
        return children

    @property
    def run(self):
        if self.resource_name in ('game', 'phase', 'role'):
            return None

        scope = self.scope

        if scope.resource_name == 'scenario' and scope.world is None:
            return scope.runuser.run

        while scope.my.parent is not None and scope.resource_name != 'run':
            scope = scope.my.parent

        return scope

    @property
    def runusers(self):
        if self.resource_name == 'game':
            return self.game.scopes['runuser']

        if self.resource_name == 'run':
            return self.game.scopes['runuser'].filter(run=self.scope.pk)

        if self.resource_name == 'runuser' or self.resource_name == 'world':
            return self.game.scopes['runuser'].filter(run=self.run.pk)

        # Scenarios and deeper into the tree of relationships may not be
        # associated to a World.  In that case, only send them to the
        # corresponding runuser on the Scenario
        if self.resource_name == 'scenario':
            if self.scope.world is None:
                return [self.scope.runuser]
            else:
                return self.scope.world.runusers

        if self.resource_name == 'period':
            if self.scope.my.parent.world is None:
                return [self.scope.my.parent.runuser]
            else:
                return self.scope.my.parent.world.runusers

        if self.resource_name == 'decision':
            if self.scope.my.parent.scenario.world is None:
                return [self.scope.my.parent.scenario.runuser]
            else:
                return self.scope.my.parent.scenario.world.runusers

        if self.resource_name == 'result':
            if self.scope.my.parent.scenario.world is None:
                return [self.scope.my.parent.scenario.runuser]
            else:
                return self.scope.my.parent.scenario.world.runusers

        return None  # scope is a Phase or Role

    @property
    def world(self):
        if self.resource_name in ('game', 'run', 'phase', 'role'):
            return None

        if self.resource_name == 'runuser':
            return self.scope.world

        if self.resource_name == 'scenario':
            return self.scope.world

        scope = self.scope  # scope is a World, Period, Decision, or Result

        while scope.my.parent is not None and scope.resource_name != 'world':
            scope = scope.my.parent

        if scope.resource_name != 'world':
            return None  # Period, Decision, or Result unassociated with a world
        else:
            return scope

    def get_runusers(self, leader=False):
        """
        This is a Swiss Army knife of a function that
        returns a manager for any `RunUser`s that have access to the scope.

        If `leader` is True and the scope is a `World`, returns all
        `RunUser`s for the `World`'s `Run`. Otherwise, returns only `RunUser`s that
        are explicitly assigned to that `World` (ie: runuser.world is not None).
        """
        if self.resource_name == 'game':
            return self.game.scopes['runuser']
        elif self.resource_name == 'run':
            return self.game.scopes['runuser'].filter(run=self.scope.pk)
        elif self.resource_name == 'world':
            if leader is False:
                self.log.debug(
                    "get_runusers: resource_name: {name} returning world run_users",
                    name=self.resource_name)

                return self.game.scopes['runuser'].filter(world=self.scope.pk)
            else:
                self.log.debug(
                    "get_runusers: resource_name: {name} returning run run_users",
                    name=self.resource_name)

                return self.game.scopes['runuser'].filter(run=self.parent.pk)
        elif self.resource_name == 'runuser':
            return ScopeManager(self.scope)
        else:
            if self.world is not None:
                self.log.debug(
                    "get_runusers: resource_name: {name} returning world run_users",
                    name=self.resource_name)

                return self.world.my.get_runusers(leader=leader)
            elif self.run is not None:
                self.log.debug(
                    "get_runusers: resource_name: {name} returning run run_users",
                    name=self.resource_name)

                return self.run.my.get_runusers(leader=leader)
        raise ValueError(
            "Can't figure out runusers for {} {}.".format(self.resource_name,
                                                          self.scope.pk))

    def get_user_ids(self, leader=False):
        """
        Returns a list of user ids from `RunUser`s that have access to the scope.

        Note that these will be `SimplUser` ids, not `RunUser` ids.

        If `leader` is True and the scope is a world, returns ids of all
        users for the World's Run. Otherwise if the scope is a world, returns
        ids of only users that are explicitly assigned to that World.
        """
        runusers = self.get_runusers(leader=leader)

        self.log.debug("get_user_ids: runusers={runusers!s}",
                       runusers=runusers)

        user_ids = [runuser.json['user'] for runuser in runusers]
        return user_ids
