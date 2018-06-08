import unittest
from unittest import mock

from modelservice.games.scopes.managers import ScopeManager


class TestScopeManager(unittest.TestCase):

    def setUp(self):
        super(TestScopeManager, self).setUp()

    def test_all(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        self.assertEqual(manager.all(), scopes)

    def test_count(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        self.assertEqual(manager.count(), 5)

    def test_last(self):
        scopes = [
            mock.Mock(
                idx=i,
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        self.assertEqual(manager.last(), scopes[-1])
        self.assertEqual(manager.last().idx, 4)

    def test_reset(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        self.assertEqual(manager.count(), 5)
        manager.reset()
        self.assertEqual(manager.count(), 0)

    def test_append(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        self.assertEqual(manager.count(), 5)

        manager.append(mock.Mock(
            resource_name='period',
            json={'id': 6, 'scenario': 1}
        ))
        self.assertEqual(manager.count(), 6)

    def test_remove(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        self.assertEqual(manager.count(), 5)

        scope = scopes[1]
        manager.remove(scope)
        self.assertEqual(manager.count(), 4)
        self.assertFalse(scope in manager)

    def test_len(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        self.assertEqual(len(manager), 5)

    def test_in(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        scope = scopes[1]
        self.assertTrue(scope in manager)

    def test_index(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        scope = scopes[1]
        self.assertTrue(manager[1], scope)

    def test_iter(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        lst = [scope for scope in manager]
        self.assertEqual(len(lst), 5)

    def test_add(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(2)
        ]
        scopes2 = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(3, 6)
        ]
        manager = ScopeManager(*scopes)
        manager2 = ScopeManager(*scopes2)

        total = manager + manager2
        self.assertEqual(total.count(), 5)

    def test_equal(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(5)
        ]
        manager = ScopeManager(*scopes)
        self.assertEqual(manager, scopes)
        self.assertEqual(scopes, manager)

    def test_add_list(self):
        scopes = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(2)
        ]
        scopes2 = [
            mock.Mock(
                resource_name='period',
                json={'id': i, 'scenario': 1}
            ) for i in range(3, 6)
        ]
        manager2 = ScopeManager(*scopes2)

        total = scopes + manager2
        self.assertTrue(isinstance(total, list))
        self.assertEqual(len(total), 5)

        total = manager2 + scopes
        self.assertTrue(isinstance(total, ScopeManager))
        self.assertEqual(total.count(), 5)

    def test_indexed_filter(self):
        worlds = [
            mock.Mock(resource_name='runuser', json={'id': 1, 'run': 1, 'world': 1}),
            mock.Mock(resource_name='runuser', json={'id': 2, 'run': 2, 'world': 2}),
            mock.Mock(resource_name='runuser', json={'id': 3, 'run': 2, 'world': 2}),
        ]
        manager = ScopeManager(*worlds)

        self.assertEqual(manager.filter(run=1).count(), 1)
        self.assertEqual(manager.filter(run=2).count(), 2)
        self.assertEqual(manager.filter(run=3).count(), 0)
        self.assertFalse(worlds[0] in manager.filter(run=2))

    def test_nonindexed_filter(self):
        runusers = [
            mock.Mock(resource_name='runuser', json={'id': 1, 'run': 1, 'world': 1, 'role': 1}),
            mock.Mock(resource_name='runuser', json={'id': 2, 'run': 2, 'world': 2, 'role': 2}),
            mock.Mock(resource_name='runuser', json={'id': 3, 'run': 2, 'world': 2, 'role': 2}),
        ]
        manager = ScopeManager(*runusers)

        self.assertEqual(manager.filter(role=1).count(), 1)
        self.assertEqual(manager.filter(role=2).count(), 2)
        self.assertEqual(manager.filter(role=3).count(), 0)
        self.assertFalse(runusers[0] in manager.filter(role=2))
        
    def test_get(self):
        worlds = [
            mock.Mock(resource_name='runuser', json={'id': 1, 'run': 1, 'world': 1}),
            mock.Mock(resource_name='runuser', json={'id': 2, 'run': 2, 'world': 2}),
            mock.Mock(resource_name='runuser', json={'id': 3, 'run': 2, 'world': 2}),
        ]
        manager = ScopeManager(*worlds)

        self.assertEqual(manager.get(run=1), worlds[0])
        self.assertRaises(manager.MultipleScopesFound, manager.get, run=2)
        self.assertRaises(manager.ScopeNotFound, manager.get, run=3)

    def test_for_user(self):
        user1 = mock.Mock(json={'id': 1, 'world': 1}, pk=1, runuser=mock.Mock(leader=False))
        user2 = mock.Mock(json={'id': 2, 'world': 1}, pk=2, runuser=mock.Mock(leader=False))
        user3 = mock.Mock(json={'id': 3, 'world': 2}, pk=3, runuser=mock.Mock(leader=False))
        user4 = mock.Mock(json={'id': 4, 'world': 2}, pk=4, runuser=mock.Mock(leader=False))

        get_user_ids_12 = mock.Mock(return_value=[1, 2])
        my_12 = mock.Mock(get_user_ids=get_user_ids_12)

        get_user_ids_23 = mock.Mock(return_value=[2, 3])
        my_23 = mock.Mock(get_user_ids=get_user_ids_23)

        worlds = [
            mock.Mock(my=my_12, json={'id': 1, 'run': 1}, pk=1, resource_name='world'),
            mock.Mock(my=my_23, json={'id': 2, 'run': 1}, pk=2, resource_name='world'),
        ]
        manager = ScopeManager(*worlds)

        self.assertEqual(manager.for_user(user1), [worlds[0]])
        self.assertEqual(manager.for_user(user1).count(), 1)
        self.assertEqual(manager.for_user(user2), worlds)
        self.assertEqual(manager.for_user(user2).count(), 2)
        self.assertEqual(manager.for_user(user3), [worlds[1]])
        self.assertEqual(manager.for_user(user3).count(), 1)
        self.assertEqual(manager.for_user(user4), [])
        self.assertEqual(manager.for_user(user4).count(), 0)
