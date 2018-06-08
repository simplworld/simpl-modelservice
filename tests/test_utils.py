from unittest import mock

from modelservice.games.scopes import concrete


async def make_game(slug=None):
    session = mock.Mock()

    if slug is None:
        slug = 'game'

    GameClass = concrete.Game
    GameClass.resource_classes = {
        'phase': concrete.Phase,
        'role': concrete.Role,
        'run': concrete.Run,
        'runuser': concrete.RunUser,
        'world': concrete.World,
        'scenario': concrete.Scenario,
        'period': concrete.Period,
        'decision': concrete.Decision,
        'result': concrete.Result,
    }
    game = await GameClass.create(session, 'game')
    game.pk = 1
    return game, session
