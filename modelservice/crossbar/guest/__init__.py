import aiohttp
import asyncio
import json
import random
import traceback
import urllib

from autobahn.asyncio.wamp import ApplicationSession
from autobahn.wamp import auth
from autobahn.wamp.types import RegisterOptions

from genericclient_base.exceptions import HTTPError

from modelservice import conf

from modelservice.auth import validate_external_auth
from modelservice.games.scopes.exceptions import FormError, ScopeNotFound
from modelservice.callees import registry as callee_registry
from modelservice.games import registry as game_registry
from modelservice.pubsub import registry as subscriber_registry
from modelservice.simpl import games_client
from modelservice.utils.instruments import Timer
from modelservice.utils.strings import no_format

# Avoid building a few common things repeatedly
BASIC_AUTH = aiohttp.BasicAuth(
    login=conf.SIMPL_GAMES_AUTH[0], password=conf.SIMPL_GAMES_AUTH[1], encoding="utf-8"
)

CHAT_FOR_USER_URL = urllib.parse.urljoin(conf.SIMPL_GAMES_URL, "/apis/rooms/for_user/")
CHAT_CHECK_USER_URL = urllib.parse.urljoin(
    conf.SIMPL_GAMES_URL, "/apis/rooms/check_user/"
)
CHAT_ADD_USER_URL = urllib.parse.urljoin(conf.SIMPL_GAMES_URL, "/apis/rooms/add_user/")
CHAT_REMOVE_USER_URL = urllib.parse.urljoin(
    conf.SIMPL_GAMES_URL, "/apis/rooms/remove_user/"
)
CHAT_POST_MESSAGE_URL = urllib.parse.urljoin(
    conf.SIMPL_GAMES_URL, "/apis/messages/post_message/"
)
CHAT_LOAD_MESSAGES_URL = urllib.parse.urljoin(conf.SIMPL_GAMES_URL, "/apis/messages/")


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

        # Determine if we need to use external auth or if we should authenticate
        # this user directly against the simpl-games-api
        password = details["ticket"]
        if password.startswith("::simpl-external-auth::"):
            authenticated = validate_external_auth(authid, password)

            if authenticated:
                self.log.info(f"EXTERNAL AUTH SUCCESSFUL realm={realm} authid={authid}")
                return {"secret": password, "role": "browser"}
            else:
                self.log.info(
                    f"EXTERNAL AUTH FAILED realm={realm} authid={authid} auth-url={url}"
                )
                return {
                    "secret": f"{random.random()}{details['ticket']}{random.random()}"
                }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, data={"email": authid, "password": password}
            ) as response:
                if response.status == 200:
                    self.log.info(f"AUTH SUCCESSFUL realm={realm} authid={authid}")
                    return {"secret": password, "role": "browser"}
                else:
                    self.log.info(
                        f"AUTH FAILED realm={realm} authid={authid} auth-url={url}"
                    )
                    return {"secret": f"{random.random()}{password}{random.random()}"}

    def _is_authid_leader(self, authid):
        for game_run in self.games[0].runs:
            try:
                me = game_run.runusers.get(email=authid)
                if me.json["leader"] is True:
                    return True
            except ScopeNotFound:
                continue

        return False

    async def authorize(self, session, uri, action, options):
        """ Authorize a particular user/action """
        authid = session["authid"]
        role = session["authrole"]
        game = self.games[0]

        self.log.info(f"AUTHORIZE CALL uri={uri} action={action}")

        ################################################
        # Handle users getting their initial scopes
        ################################################
        if uri.startswith(f"{conf.ROOT_TOPIC}.init_user_scopes"):
            return {"allow": True, "cache": True, "disclose": True}

        ################################################
        # Handle user's own error scope
        ################################################
        if uri.startswith(f"{conf.ROOT_TOPIC}.error.{authid}"):
            return {"allow": True, "cache": True, "disclose": True}

        ################################################
        # Handle chat related operations authorization
        ################################################
        if uri.startswith(f"{conf.ROOT_TOPIC}.chat."):
            base = uri.replace(f"{conf.ROOT_TOPIC}.chat.", "")

            is_leader = self._is_authid_leader(authid)
            if (
                base == "create_room"
                or base == "add_user"
                or base == "remove_user"
                or "check_user"
            ):

                if not is_leader:
                    self.log.info(f"Non-leader attempting to modify chat rooms")
                    return {"allow": False, "cache": True, "disclose": True}

                return {"allow": True, "cache": True, "disclose": True}

            if base == "rooms_for_user":
                return {"allow": True, "cache": True, "disclose": True}

            # We check authorization for the user in the room inside this method
            if base == "load_messages":
                return {"allow": True, "cache": True, "disclose": True}

            # Allow users in a chat room to subscribe to the pubsub channel, but
            # they SHOULD NOT be allowed to publish on it.
            if action == "subscribe" and base.startswith("rooms."):
                parts = base.split(".")
                room_slug = parts[1]

                result = await self.chat_check_user(room_slug=room_slug, authid=authid)

                if result is True:
                    return {"allow": True, "cache": True, "disclose": True}
                else:
                    return {"allow": False, "cache": True, "disclose": True}

            # Disallow chat operations that are not specifically allowed
            return {"allow": False, "cache": True, "disclose": True}

        ################################################
        # Handle the non-chat related Simpl scopes
        ################################################

        # Determine resource and pk of URI
        base = uri.replace(f"{conf.ROOT_TOPIC}.model.", "")
        parts = base.split(".")
        resource_name = parts[0]

        if resource_name == "game":
            if parts[1] == "get_phases" or parts[1] == "get_roles":
                return {"allow": True, "cache": True, "disclose": True}
            elif action == "call":
            # TODO Disallow game level call actions unless user is staff
            # For now, allow anyone to access Game level RPCs
                return {"allow": True, "cache": True, "disclose": True}

        try:
            pk = int(parts[1])
        except ValueError:
            pk = None

        # Disallow register actions across the board
        if action == "register":
            self.log.info(
                f"AUTHORIZATION DENY authid={authid} uri={uri} action={action}"
            )
            return {"allow": False, "cache": True, "disclose": True}

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

    async def init_user_scopes(self, details):
        """ Retrieve the user's scopes for this game """
        is_leader = False
        runs = set()
        worlds = set()
        runusers = set()
        rooms = set()

        for game_run in self.games[0].runs:
            try:
                runuser = game_run.runusers.get(email=details.caller_authid)
                runuser_id = runuser.json["id"]

                if runuser.json["leader"] is True:
                    is_leader = True

                if is_leader:
                    runs.add(game_run.pk)
                else:
                    runusers.add(runuser_id)
                    if runuser.json["world"]:
                        worlds.add(runuser.json["world"])
            except ScopeNotFound:
                continue

        # Build topics
        topics = []

        if is_leader:
            topics.extend([f"model:model.run.{x}" for x in runs])
        else:
            topics.extend([f"model:model.runuser.{x}" for x in runusers])
            topics.extend([f"model:model.world.{x}" for x in worlds])

        self.log.info(
            f"TOPICS for authid={details.caller_authid} is_leader={is_leader} topics={topics}"
        )
        return (topics, is_leader)

    async def chat_create_room(self, room_data):
        """ Create a room """
        payload = {
            "game": self.games[0].pk,
            "slug": room_data["slug"],
            "name": room_data["name"],
            "data": room_data["data"],
        }

        async with games_client as api_session:

            try:
                room = await api_session.rooms.create(payload)
                slug = room_data["slug"]
                self.log.info(f"Chat room '{slug}' created.")
                return room.payload
            except HTTPError as e:
                if e.response.status == 400:
                    self.log.error(f"Unable to create room {e.response.json()}")

    async def chat_rooms_for_user(self, runuser_id):
        """ Retrieve list of rooms for a given runuser """
        async with aiohttp.ClientSession(auth=BASIC_AUTH) as session:
            async with session.post(
                CHAT_FOR_USER_URL, data={"runuser": runuser_id}
            ) as response:
                if response.status == 200:
                    rooms = await response.json()
                    return rooms
                else:
                    self.log.info(
                        f"CHAT USER ROOMS FAILED content={rooms} runuser_id={runuser_id}"
                    )
                    return {"error": True}

    async def chat_check_user(self, room_slug, authid):
        """ Check if a user is allowed to subscribe to a room """
        async with aiohttp.ClientSession(auth=BASIC_AUTH) as session:
            async with session.post(
                CHAT_CHECK_USER_URL, data={"email": authid, "room": room_slug}
            ) as response:
                if response.status == 200:
                    self.log.info(
                        f"CHAT USER CHECK SUCCESSFUL room={room_slug} authid={authid}"
                    )
                    return {"allowed": True}
                else:
                    self.log.info(
                        f"CHAT USER CHECK FAILED room={room_slug} authid={authid}"
                    )
                    return {"allowed": False}

    async def chat_add_user(self, room_slug, runuser_id):
        """ Add a user to a room """
        async with aiohttp.ClientSession(auth=BASIC_AUTH) as session:
            async with session.post(
                CHAT_CHECK_USER_URL, data={"runuser": runuser_id, "room": room_slug}
            ) as response:
                if response.status == 200:
                    self.log.info(
                        f"CHAT ADD USER SUCCESSFUL room={room_slug} runuser_id={runuser_id}"
                    )
                    return {"allowed": True}
                else:
                    self.log.info(
                        f"CHAT ADD USER FAILED room={room_slug} runuser_id={runuser_id}"
                    )
                    return {"allowed": False}

    async def chat_remove_user(self, room_slug, runuser_id):
        """ Remove a user from a room """
        async with aiohttp.ClientSession(auth=BASIC_AUTH) as session:
            async with session.post(
                CHAT_REMOVE_USER_URL, data={"runuser": runuser_id, "room": room_slug}
            ) as response:
                if response.status == 200:
                    self.log.info(
                        f"CHAT REMOVE USER SUCCESSFUL room={room_slug} runuser_id={runuser_id}"
                    )
                    return {"allowed": True}
                else:
                    self.log.info(
                        f"CHAT REMOVE USER FAILED room={room_slug} runuser_id={runuser_id}"
                    )
                    return {"allowed": False}

    async def chat_post_message(self, room_slug, authid, data):
        """ Post a message to a room """
        async with aiohttp.ClientSession(auth=BASIC_AUTH) as session:
            async with session.post(
                CHAT_POST_MESSAGE_URL,
                data={"sender": authid, "room": room_slug, "data": json.dumps(data)},
            ) as response:
                if response.status == 200:
                    content = await response.json()
                    self.publish(f"{conf.ROOT_TOPIC}.chat.room.{room_slug}", content)
                    return content
                else:
                    content = await response.text()
                    self.log.info(f"CHAT POST ERROR {content}")
                    return {"posted": False}

    async def chat_load_messages(self, room_slug, authid):
        """ Post a message to a room """
        # See if user is allowed to load messages
        result = await self.chat_check_user(room_slug, authid)

        # If they are allowed to get these messages, grab them and return them
        if result["allowed"]:
            async with aiohttp.ClientSession(auth=BASIC_AUTH) as session:
                url = f"{CHAT_LOAD_MESSAGES_URL}?room_slug={room_slug}"
                self.log.info(f"CHAT LOAD URL {url}")
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.json()
                        return content
                    else:
                        content = await response.text()
                        self.log.info(f"CHAT LOAD MESSAGES ERROR {content}")
                        return {}
        else:
            self.log.info(f"CHAT LOAD MESSAGES FOR INCORRECT ROOM {authid} {room_slug}")

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

        # User scopes
        await self.register(
            self.init_user_scopes,
            f"{conf.ROOT_TOPIC}.init_user_scopes",
            RegisterOptions(details_arg="details"),
        )

        ###########################################################
        # Setup chat RPC methods
        ###########################################################
        self.log.info(f"Register {conf.ROOT_TOPIC}.chat.create_room")
        await self.register(
            self.chat_create_room, f"{conf.ROOT_TOPIC}.chat.create_room"
        )
        self.log.info(f"Register {conf.ROOT_TOPIC}.chat.rooms_for_user")
        await self.register(
            self.chat_rooms_for_user, f"{conf.ROOT_TOPIC}.chat.rooms_for_user"
        )
        self.log.info(f"Register {conf.ROOT_TOPIC}.chat.check_user")
        await self.register(self.chat_check_user, f"{conf.ROOT_TOPIC}.chat.check_user")
        self.log.info(f"Register {conf.ROOT_TOPIC}.chat.add_user")
        await self.register(self.chat_add_user, f"{conf.ROOT_TOPIC}.chat.add_user")
        self.log.info(f"Register {conf.ROOT_TOPIC}.chat.remove_user")
        await self.register(
            self.chat_remove_user, f"{conf.ROOT_TOPIC}.chat.remove_user"
        )
        self.log.info(f"Register {conf.ROOT_TOPIC}.chat.post_message")
        await self.register(
            self.chat_post_message, f"{conf.ROOT_TOPIC}.chat.post_message"
        )
        self.log.info(f"Register {conf.ROOT_TOPIC}.chat.load_messages")
        await self.register(
            self.chat_load_messages, f"{conf.ROOT_TOPIC}.chat.load_messages"
        )
        self.log.info("Chat RPC methods registered")

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
