from asynctest import TestCase, patch

from modelservice.games.scopes import concrete

from .test_utils import make_game


class TestScopes(TestCase):
    use_default_loop = True

    @patch('modelservice.games.storages.SIMPLStorage.load')
    async def test_run(self, SIMPLStorage):
        game, session = await make_game()

        json = {
            'id': 1,
            'game': game.pk
        }

        run = await concrete.Run.create(session, game, json)

        self.assertEqual(run.game, game)
        self.assertEqual(run.my.parent, game)
        self.assertEqual(run.run, run)
        self.assertEqual(run.world, None)

    @patch('modelservice.games.storages.SIMPLStorage.load')
    async def test_world_scenario(self, SIMPLStorage):
        game, session = await make_game()

        run = await concrete.Run.create(session, game, {
            'id': 1,
            'game': game.pk
        })
        await game.add_scopes(run)

        world = await concrete.World.create(session, game, {
            'id': 1,
            'run': run.pk,
        })
        await game.add_scopes(world)

        json = {
            'id': 1,
            'runuser': None,
            'world': world.pk,
        }

        scenario = await concrete.Scenario.create(session, game, json)
        await game.add_scopes(scenario)

        self.assertEqual(scenario.game, game)
        self.assertEqual(scenario.my.parent, world)
        self.assertEqual(scenario.my.run, run)
        self.assertEqual(scenario.my.run, world.run)
        scenario_runusers = scenario.my.runusers
        self.assertEqual(scenario_runusers, [])

    @patch('modelservice.games.storages.SIMPLStorage.load')
    async def test_runuser_scenario(self, SIMPLStorage):
        game, session = await make_game()

        run = await concrete.Run.create(session, game, {
            'id': 1,
            'game': game.pk
        })
        await game.add_scopes(run)

        runuser = await concrete.RunUser.create(session, game, {
            'id': 1,
            'run': run.pk,
            'user': 1,
            'world': None,
        })
        await game.add_scopes(runuser)

        leader = await concrete.RunUser.create(session, game, {
            'id': 2,
            'run': run.pk,
            'user': 2,
            'leader': True,
            'world': None,
        })
        await game.add_scopes(leader)

        json = {
            'id': 1,
            'runuser': runuser.pk,
            'world': None,
        }

        scenario = await concrete.Scenario.create(session, game, json)

        self.assertEqual(scenario.game, game)
        self.assertEqual(scenario.my.parent, runuser)
        self.assertEqual(scenario.my.run, run)
        self.assertEqual(scenario.my.run, runuser.run)
        self.assertEqual(scenario.my.world, None)
        self.assertEqual(scenario.my.runusers, [runuser])


