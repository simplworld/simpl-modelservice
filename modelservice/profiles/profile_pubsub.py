from modelservice.profiler import ProfileCase


class ProfilePubSubTestCase(ProfileCase):
    """
    Profile pubsub calls to the modelservice.
    """

    def profile_hello_world(self):
        self.publish('world.simpl.sims.simpl-calc.model.game.hello_game')
