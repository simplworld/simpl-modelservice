from modelservice.profiler import ProfileCase
from modelservice.utils.instruments import Counter


class ProfileHttpTestCase(ProfileCase):
    """
    Profile HTTP calls from the modelservice to simpl-games-api.
    """

    async def profile_get_phases(self):
        counter = Counter(duration=5, name='{}-{}-get_phases'.format(self.worker_name, self.group_name))
        while counter.on:
            await self.wamp.call(
                'world.simpl.sims.simpl-calc.model.game.get_phases',
            )
        self.publish_stat(
            'profile_get_phases_avg_rate',
            counter.rate,
            fmt='Task \'profile_get_phases\' averaged {stats.mean:.3f} c/s.'
        )

    async def profile_create_run(self):
        game = self.games_client.games.get(slug='simpl-calc')
        counter = Counter(duration=5)
        runs = []
        while counter.on:
            run = await self.games_client.runs.create({
                'name': 'test_run',
                'game': game.pk,
            })
            runs.append(run)

        [await run.delete() for run in runs]

        self.publish_stat(
            'profile_create_run_rate',
            counter.rate,
            fmt='Task \'profile_create_run\' averaged {stats.mean:.3f} c/s.'
        )
