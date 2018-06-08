from typing import List, Union

from django.core.cache import cache, caches, InvalidCacheBackendError

from genericclient_aiohttp import Resource

from .scopes.managers import ScopeManager
from ..simpl import games_client
from ..utils.strings import encode_dict

try:
    user_cache = caches['users']
except InvalidCacheBackendError:
    user_cache = cache


class BaseStorage(object):
    def __init__(self, scope):
        self.scope = scope
        super(BaseStorage, self).__init__()

    @property
    def resource_name(self):
        return self.scope.resource_name

    @property
    def resource_name_plural(self):
        return self.scope.resource_name_plural


class SIMPLStorage(BaseStorage):
    def __init__(self, scope):
        self.games_client = games_client
        super(SIMPLStorage, self).__init__(scope)

    def json_to_scope(self, resource_name_plural, json_list):
        scope_class = self.scope.game.endpoint_to_classes[resource_name_plural]
        return ScopeManager(*[
            scope_class(session=self.scope.game.session, game=self.scope.game,
                        json=item)
            for item in json_list
        ])

    def _get_cache_key(self, method: str, endpoint: str, lookup: dict) -> str:
        return "{}.{}:{}".format(
            endpoint, method, encode_dict(lookup)
        )

    async def get(self, endpoint_name: str, timeout=1, **lookup) -> dict:
        cache_key = self._get_cache_key('get', endpoint_name, lookup)
        # To avoid cache misses, we want to lock while the value is fetched and written to cache.
        # To achieve this, we use a RWLock.

        # A RWLock maintains a pair of associated locks, one for read-only operations and one for
        # writing. The read lock may be held simultaneously by multiple reader tasks, so long as
        # there are no writers. The write lock is exclusive.

        # TODO: [Profile] Is it better to lock and have fewer HTTP requests, or
        # to 'eventually cache' and have a few more HTTP reqs but not lock at
        # all?
        async with self.scope.game.locks[cache_key].reader:
            payload = cache.get(cache_key)

        if payload is None:
            self.scope.log.debug('cache miss `{key}`', key=cache_key)

            async with self.scope.game.locks[cache_key].writer:
                endpoint = getattr(self.games_client, endpoint_name)
                resource = await endpoint.get(**lookup)
                payload = resource.payload
                cache.set(cache_key, payload, timeout)

                self.scope.log.debug('cache set `{key}`', key=cache_key)
        else:
            self.scope.log.debug('cache hit `{key}`', key=cache_key)

        return payload

    async def filter(self, endpoint_name: str, timeout=1, **lookup) -> List[
        dict]:
        cache_key = self._get_cache_key('filter', endpoint_name, lookup)
        # To avoid cache misses, we want to lock while the value is fetched and written to cache.
        # To achieve this, we use a RWLock.

        # A RWLock maintains a pair of associated locks, one for read-only operations and one for
        # writing. The read lock may be held simultaneously by multiple reader tasks, so long as
        # there are no writers. The write lock is exclusive.

        # TODO: [Profile] Is it better to lock and have fewer HTTP requests, or
        # to 'eventually cache' and have a few more HTTP reqs but not lock at
        # all?
        async with self.scope.game.locks[cache_key].reader:
            payloads = cache.get(cache_key)
        if payloads is None:
            async with self.scope.game.locks[cache_key].writer:
                endpoint = getattr(self.games_client, endpoint_name)
                resources = await endpoint.filter(**lookup)
                payloads = [resource.payload for resource in resources]
                cache.set(cache_key, payloads, timeout)
        return payloads

    async def save(self, json=None):
        if json is None:
            json = {}
        update_json = {
            self.scope.my.parent.resource_name: self.scope.my.parent.pk,
        }
        update_json.update(self.scope.json)
        update_json.update(json)
        endpoint = getattr(self.games_client, self.resource_name_plural)
        resource = (await endpoint.create_or_update(update_json)).payload
        return resource

    async def load(self, **kwargs):
        """
        Get scope resource from database
        :param kwargs:
        :return: retrieved resource
        """
        return await self.get(self.resource_name_plural, **kwargs)

    async def get_user(self, **lookup) -> Resource:
        """
        Fetches a user on simpl-games-api according to the passed keyword arguments,
        and monkeypatches it with the appropriate runuser::

            user = await self.get_user(id=123)
            # or
            user = await self.get_user(email='s1@mysim.edu')

        :param lookup: Keyword arguments for the lookup on simpl-games-api
        :return: The user monkeypatched with the appropriate runuser for this storage's scope.
        """
        self.scope.log.debug('get_user: {name} pk: {pk} lookup: {lookup}',
                             name=self.resource_name, pk=self.scope.pk,
                             lookup=lookup)

        user_json = await self.get('users', **lookup)
        user = Resource(self.games_client.users, **user_json)

        if self.scope.my.run is not None:
            if self.resource_name == 'runuser':
                runuser = Resource(self.games_client.runusers,
                                   **self.scope.json)
            else:
                try:
                    runuser_json = self.scope.game.scopes['runuser'].get(
                        user=user.pk,
                        run=self.scope.my.run.pk
                    ).json
                except ScopeManager.ScopeNotFound:
                    self.scope.log.info(
                        'get_user: get missing runuser scope user: {user} run: {run}',
                        user=user.pk,
                        run=self.scope.my.run.pk)
                    runuser_json = await self.get('runusers', user=user.pk,
                                                  run=self.scope.my.run.pk)
                runuser = Resource(self.games_client.runusers, **runuser_json)

            user.payload.update({'runuser': runuser})

        return user
