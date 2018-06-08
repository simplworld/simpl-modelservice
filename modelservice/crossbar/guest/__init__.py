import traceback

from autobahn.asyncio.wamp import ApplicationSession
from autobahn.wamp.types import RegisterOptions


from modelservice import conf

from modelservice.games.scopes.exceptions import FormError
from modelservice.callees import registry as callee_registry
from modelservice.games import registry as game_registry
from modelservice.pubsub import registry as subscriber_registry
from modelservice.utils.instruments import Timer
from modelservice.utils.strings import no_format


class ModelComponent(ApplicationSession):
    games = []

    def onUserError(self, fail, msg):
        # publish exceptions to the websocket, so they can be shown on the UI
        user_id = None
        if hasattr(fail.value, 'user') and fail.value.user is not None:
            user_id = fail.value.user.id

        if user_id is not None:
            topic = "{}.error.{}".format(conf.ROOT_TOPIC, user_id)
        else:
            topic = "{}.error".format(conf.ROOT_TOPIC)

        if hasattr(fail.value, 'error'):
            kwargs = fail.value.kwargs
            kwargs['error'] = fail.value.error
            self.publish(topic, *fail.value.args, **kwargs)
        else:
            self.publish(topic, *fail.value.args,
                         error=fail.value.__class__.__name__)
        super(ModelComponent, self).onUserError(fail, msg)

    async def onJoin(self, details):
        self.log.info("session joined")
        # can do subscribes, registers here e.g.:
        # await self.subscribe(...)
        # await self.register(...)

        self.define(FormError)

        for game_name, GameClass in game_registry._registry.items():
            try:
                with Timer() as timer:
                    game = GameClass(self, game_name)
                    await game.start()
                    await game.restore()
                    self.games.append(game)
                    await game.subscribe_webhook()
                    self.log.info("game `{game_name}` installed",
                                  game_name=game_name)
                self.log.info("Game `{game_name}` installed in {time:.03f}s.",
                              game_name=game_name,
                              time=timer.elapsed)
                await self.register(game.ready,
                                    '{}.ready'.format(conf.ROOT_TOPIC),
                                    RegisterOptions(match='exact'))
            except Exception as e:
                self.log.error(
                    "could not install game `{game_name}`: {error!r}",
                    game_name=game_name, error=e)
                self.log.error(no_format(traceback.format_exc()))

        for uri, registration in callee_registry._registry.items():
            try:
                await self.register(registration['func'], uri,
                                    options=registration['options'])
                self.log.info("procedure `{uri}` registered", uri=uri)
            except Exception as e:
                self.log.error("could not register procedure: {error!r}",
                               error=e)
                self.log.error(no_format(traceback.format_exc()))

        for topic, registration in subscriber_registry._registry.items():
            try:
                await self.subscribe(registration['func'], topic,
                                     options=registration['options'])
                self.log.info("subscriber `{topic}` registered", topic=topic)
            except Exception as e:
                self.log.error("could not register subscriber: {error!r}",
                               error=e)
                self.log.error(no_format(traceback.format_exc()))
