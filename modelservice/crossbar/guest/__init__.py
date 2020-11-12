import aiohttp
import asyncio
import random
import traceback
import urllib

from autobahn.asyncio.wamp import ApplicationSession
from autobahn.wamp import auth
from autobahn.wamp.types import RegisterOptions


from modelservice import conf

from modelservice.games.scopes.exceptions import FormError, ScopeNotFound
from modelservice.callees import registry as callee_registry
from modelservice.games import registry as game_registry
from modelservice.pubsub import registry as subscriber_registry
from modelservice.utils.instruments import Timer
from modelservice.utils.strings import no_format


class ModelComponent(ApplicationSession):
    games = []

    async def onConnect(self):
        print("Guest process connecting...")
        self.join(self.config.realm, ["wampcra"], "model")

    async def onChallenge(self, challenge):
        signature = auth.compute_wcs(
            conf.MODEL_TICKET.encode("utf8"),
            challenge.extra["challenge"].encode("utf8"),
        )
        return signature

    def onUserError(self, fail, msg):
        # publish exceptions to the websocket, so they can be shown on the UI
        user_id = None
        if hasattr(fail.value, "user") and fail.value.user is not None:
            user_id = fail.value.user.id

        if user_id is not None:
            topic = "{}.error.{}".format(conf.ROOT_TOPIC, user_id)
        else:
            topic = "{}.error".format(conf.ROOT_TOPIC)

        if hasattr(fail.value, "error"):
            kwargs = fail.value.kwargs
            kwargs["error"] = fail.value.error
            self.publish(topic, *fail.value.args, **kwargs)
        else:
            self.publish(topic, *fail.value.args, error=fail.value.__class__.__name__)
        super(ModelComponent, self).onUserError(fail, msg)

    async def authenticate(self, realm, authid, details):
        """ Authenticator a user against the Simpl Games API """
        url = urllib.parse.urljoin(conf.SIMPL_GAMES_URL, "/apis/authcheck/")

        self.log.info(f"AUTH URL='{url}'")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, data={"email": authid, "password": details["ticket"]}
            ) as response:
                if response.status == 200:
                    self.log.info(f"AUTH SUCCESSFUL realm={realm} authid={authid}")
                    return {"secret": details["ticket"], "role": "browser"}
                else:
                    self.log.info(f"AUTH FAILED realm={realm} authid={authid}")
                    return {
                        "secret": f"{random.random()}{details['ticket']}{random.random()}"
                    }

    def authorize(self, session, uri, action, options):
        """ Authorize a particular user/action """
        authid = session["authid"]
        role = session["authrole"]
        game = self.games[0]

        # Determine resource and pk of URI
        base = uri.replace(f"{conf.ROOT_TOPIC}.model.", "")
        parts = base.split(".")
        resource_name = parts[0]
        pk = int(parts[1])

        # Disallow register actions
        if action == "register":
            self.log.info(
                f"AUTHORIZATION DENY authid={authid} uri={uri} action={action}"
            )
            return {"allow": True, "cache": True, "disclose": True}

        if resource_name == "game":
            if parts[1] == "get_phases" or parts[1] == "get_roles":
                return {"allow": True, "cache": True, "disclose": True}

        # Allow phases and roles always
        if resource_name in ["phase", "role"]:
            return {"allow": True, "cache": True, "disclose": True}

        # Grab of the RunUser scopes for this user
        runusers = []
        runs = []
        is_leader = False

        for game_run in game.runs:
            try:
                me = game_run.runusers.get(email=authid)
                if me.json["leader"] is True:
                    is_leader = True
                runusers.append(me)
                runs.append(game_run)
            except ScopeNotFound:
                continue

        # Only leaders should be allowed to subscribe to runs
        if resource_name == "run":
            for ru in runusers:
                if ru.json["run"] == pk:
                    is_leader = ru.json["leader"]
                    if is_leader:
                        self.log.info(
                            f"AUTHORIZE authid={authid} role={role} uri={uri} action={action} leader={is_leader}"
                        )
                        return {"allow": True, "cache": True, "disclose": True}
                    else:
                        self.log.info(f"AUTHORIZATION DENY authid={authid} uri={uri}")
                        return {"allow": False, "cache": True, "disclose": True}

        # Ensure we can only subscribe to RunUsers that are us
        if resource_name == "runuser":
            for ru in runusers:
                if ru.json["email"] == authid:
                    self.log.info(
                        f"AUTHORIZE authid={authid} role={role} uri={uri} action={action}"
                    )
                    return {"allow": True, "cache": True, "disclose": True}

            # Disallow others
            self.log.info(f"AUTHORIZATION DENY authid={authid} uri={uri}")
            return {"allow": False, "cache": True, "disclose": True}

        # Enforce world subscriptions
        if resource_name == "world":
            for ru in runusers:
                if ru.json["world"] == pk:
                    self.log.info(
                        f"AUTHORIZE authid={authid} role={role} uri={uri} action={action}"
                    )
                    return {"allow": True, "cache": True, "disclose": True}

            # Handle leaders
            if is_leader:
                for run in runs:
                    for world in game_run.worlds.all():
                        if world.json["id"] == pk:
                            self.log.info(
                                f"AUTHORIZE authid={authid} role={role} uri={uri} action={action}"
                            )
                            return {"allow": True, "cache": True, "disclose": True}

        self.log.info(f"AUTHORIZATION DENY authid={authid} uri={uri}")
        return {"allow": False, "cache": False, "disclose": True}

    async def onJoin(self, details):
        self.log.info("session joined")
        # can do subscribes, registers here e.g.:
        # await self.subscribe(...)
        # await self.register(...)

        # Register authentication
        await self.register(self.authenticate, "world.simpl.authenticate")
        self.log.info("Register authentication as 'world.simpl.authenticate'")

        # Register authorization
        await self.register(self.authorize, "world.simpl.authorize")
        self.log.info("Register authorization as 'world.simpl.authorize'")

        self.define(FormError)

        for game_name, GameClass in game_registry._registry.items():
            try:
                with Timer() as timer:
                    game = GameClass(self, game_name)
                    await game.start()
                    await game.restore()
                    self.games.append(game)
                    await game.subscribe_webhook()
                    self.log.info("game `{game_name}` installed", game_name=game_name)
                self.log.info(
                    "Game `{game_name}` installed in {time:.03f}s.",
                    game_name=game_name,
                    time=timer.elapsed,
                )
                await self.register(
                    game.ready,
                    "{}.ready".format(conf.ROOT_TOPIC),
                    RegisterOptions(match="exact"),
                )
            except Exception as e:
                self.log.error(
                    "could not install game `{game_name}`: {error!r}",
                    game_name=game_name,
                    error=e,
                )
                self.log.error(no_format(traceback.format_exc()))

        for uri, registration in callee_registry._registry.items():
            try:
                await self.register(
                    registration["func"], uri, options=registration["options"]
                )
                self.log.info("procedure `{uri}` registered", uri=uri)
            except Exception as e:
                self.log.error("could not register procedure: {error!r}", error=e)
                self.log.error(no_format(traceback.format_exc()))

        for topic, registration in subscriber_registry._registry.items():
            try:
                await self.subscribe(
                    registration["func"], topic, options=registration["options"]
                )
                self.log.info("subscriber `{topic}` registered", topic=topic)
            except Exception as e:
                self.log.error("could not register subscriber: {error!r}", error=e)
                self.log.error(no_format(traceback.format_exc()))
