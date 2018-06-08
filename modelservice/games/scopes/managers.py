from collections import defaultdict, OrderedDict

from .constants import SCOPE_FILTER_ATTRIBUTES
from .exceptions import ScopeNotFound, MultipleScopesFound


class ScopeManager(object):
    # Stores scopes indexed by pk for quick retrieval

    ScopeNotFound = ScopeNotFound
    MultipleScopesFound = MultipleScopesFound

    payload_attr = 'json'
    pk_attr = 'id'

    def __init__(self, *args):
        self.scopes = OrderedDict()
        self.indexes = defaultdict(lambda: defaultdict(set))
        self.extends(*args)
        super(ScopeManager, self).__init__()

    def get_indexes(self, scope):
        # Returns attributes by which scope can be filtered
        return SCOPE_FILTER_ATTRIBUTES[scope.resource_name]

    def get_pk(self, scope):
        return getattr(scope, self.payload_attr)[self.pk_attr]

    def get_index_value(self, index, scope):
        return getattr(scope, self.payload_attr)[index]

    def add_to_index(self, index, scope):
        index_value = self.get_index_value(index, scope)
        self.indexes[index][index_value].add(scope)

    def remove_from_index(self, index, scope):
        index_value = self.get_index_value(index, scope)
        self.indexes[index][index_value].remove(scope)

    def reset(self):
        self.scopes = OrderedDict()
        self.indexes = defaultdict(lambda: defaultdict(set))

    def extends(self, *args):
        for arg in args:
            self.scopes[self.get_pk(arg)] = arg
            for index in self.get_indexes(arg):
                self.add_to_index(index, arg)

    def _lookup(self, scope, **kwargs):
        payload = getattr(scope, self.payload_attr)
        for key, value in kwargs.items():
            try:
                if payload[key] != value:
                    return False
            except KeyError:
                raise ValueError(
                    "Scope `{}` does not have attribute `{}`. Available attributes are: {!r}".format(
                        scope.resource_name, key, list(payload.keys())
                    )
                )
        return True

    def filter(self, **kwargs):
        if len(kwargs) == 1:
            k, v = list(kwargs.items())[0]
        else:
            k = None

        if k is not None and k in self.indexes:
            scopes = self.indexes[k][v]
            results = ScopeManager(*[
                scope for scope in scopes
            ])
        else:
            results = ScopeManager(*[
                scope for scope in self.scopes.values() if
                self._lookup(scope, **kwargs)
            ])
        return results

    def for_user(self, user):
        """
        Returns manager for this manager's scopes the user may access
        :param user: SimplUser
        :return: ScopeManager -- may be empty
        """
        return ScopeManager(*[
            scope for scope in self.scopes.values()
            if user.pk in scope.my.get_user_ids(leader=user.runuser.leader)
        ])

    def all(self):
        return self

    def get(self, **kwargs):
        if len(kwargs) == 1:
            k, v = list(kwargs.items())[0]
            if k == self.pk_attr:
                try:
                    return self.scopes[v]
                except KeyError:
                    raise self.ScopeNotFound(kwargs)

        found = self.filter(**kwargs)
        if len(found) == 0:
            raise self.ScopeNotFound(kwargs)
        if len(found) > 1:
            raise self.MultipleScopesFound(kwargs)
        return found[0]

    def append(self, *scopes):
        for scope in scopes:
            self.scopes[self.get_pk(scope)] = scope
            for index in self.get_indexes(scope):
                self.add_to_index(index, scope)

    def add(self, scope):
        self.append(scope)

    def remove(self, scope):
        for index in self.get_indexes(scope):
            self.remove_from_index(index, scope)
        self.scopes.pop(self.get_pk(scope))

    def exists(self):
        if len(self.scopes) > 1:
            raise MultipleScopesFound
        return len(self.scopes) == 1

    def last(self):
        try:
            return list(self.scopes.values())[-1]
        except IndexError:
            raise ScopeNotFound(self.scopes)

    def count(self):
        return len(self.scopes)

    def __repr__(self):
        return "<ScopeManager object containing {} scopes>".format(
            self.count(),
        )

    def __add__(self, other):
        self.extends(*other)
        return self

    def __radd__(self, other):
        if not isinstance(other, self.__class__):
            scopes = [scope for scope in self]
        else:
            scopes = self
        return other + scopes

    def __len__(self):
        return len(self.scopes)

    def __getitem__(self, key):
        return list(self.scopes.values())[key]

    def __iter__(self):
        return self.scopes.values().__iter__()

    def __next__(self):
        return self.scopes.values().__next__()

    def __contains__(self, item):
        return self.get_pk(item) in self.scopes

    def __eq__(self, other):
        return [scope for scope in self] == other

    def __ne__(self, other):
        return [scope for scope in self] != other
