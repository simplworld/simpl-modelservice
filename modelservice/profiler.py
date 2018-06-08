import unittest

from .simpl import games_client


class ProfileCase(unittest.TestCase):
    """
    A class for grouping profile tasks.

    Inherits from ``unittest.TestCase`` so that we can reuse unittest's discovery.

    Unlike ``unittest.TestCase``, it does not support ``.setUp()`` or ``.tearDown()`` methods.

    A ProfileCase contains multiple ``profile_*`` tasks.

    Each task performs some operations and publishes measurements via the ``publish_stat(stat_id, value, fmt)`` method::

        from modelservice.profiles import ProfileCase
        from modelservice.utils.instruments import Counter


        class MyProfileCase(ProfileCase):
            def profile_thing(self):
                counter = Counter(duration=5)
                while counter.on:
                    do_something()

                self.publish_stat(
                    'mything',
                    counter.rate,
                    fmt='Task \'profile_thing\' averaged {stats.mean:.3f} c/s.'
                )

    Each task may run one or more times, and the measurements are collected into instances of
    :class:`~modelservice.utils.instruments.StatAggregator` 'buckets', identified by the ``stat_id``
    argument.

    After a task has finished its runs, the format string specified in the ``fmt`` parameter gets
    ``.format()`` 'ed with the ``StatAggregator`` instance passed as ``stats``.
    """

    games_client = games_client
    user_email = None

    @property
    def worker_name(self):
        return self.wamp.worker_name

    @property
    def user_email(self):
        return self.wamp.user_email

    def worker_is_named(self, name: str) -> bool:
        """
        Convenience method to check if the task is running on a particular worker.

        Useful if you want some logic to only be executed once per group.

        Equivalent to ``self.worker_name == name``::

            if self.worker_is_named('1'):
                run_only_on_1()

        :param name: the name of the worker
        :return: True is the worker is named ``name``, False otherwise.
        """
        return self.worker_name == name

    def setUp(self):
        raise NotImplemented

    def tearDown(self):
        raise NotImplemented

    def run(self, *args, **kwargs):
        raise NotImplemented

    async def call(self,uri: str, *args, **kwargs):
        """
        Calls an RPC procedure on the modelservice as a specific user.

        Example::

            self.call('world.simpl.sims.simpl-calc.model.game.hello_world')

        :param uri: the WAMP URI of the RPC
        :param args: arguments for the RPC
        :param kwargs: keyword arguments for the RPC
        :return: the result of the RPC
        """
        if self.user_email is not None:
            kwargs['user_email'] = self.user_email
        return await self.wamp.call(uri, *args, **kwargs)

    async def call_as(self, user_email: str, uri: str, *args, **kwargs):
        """
        Calls an RPC procedure on the modelservice as a specific user.

        Example::

            self.call_as('s1@calc.edu', 'world.simpl.sims.simpl-calc.model.game.hello_world')

        :param user_email: the email identifying the user
        :param uri: the WAMP URI of the RPC
        :param args: arguments for the RPC
        :param kwargs: keyword arguments for the RPC
        :return: the result of the RPC
        """
        kwargs['user_email'] = user_email
        return await self.wamp.call(uri, *args, **kwargs)

    def publish(self, topic: str, *args, **kwargs):
        """
        Publishes to a topic on the modelservice.

        If the ``user_email`` property is set on the ``ProfileCase``, the publishing is done as that user.

        Example::

            self.publish('world.simpl.sims.simpl-calc.model.game.hello_world')

        :param topic: the WAMP topic to publish to
        :param args: arguments to be published
        :param kwargs: keyword arguments to be published
        :return: the result of the publishing (typically: ``None``)
        """
        if self.user_email is not None:
            kwargs['user_email'] = self.user_email
        return self.wamp.publish(topic, *args, **kwargs)

    def publish_as(self, user_email: str, topic: str, *args, **kwargs):
        """
        Publishes to a topic on the modelservice as a specific user.

        Example::

            self.publish_as('s1@calc.edu', 'world.simpl.sims.simpl-calc.model.game.hello_world')

        :param user_email: the email identifying the user
        :param topic: the WAMP topic to publish to
        :param args: arguments to be published
        :param kwargs: keyword arguments to be published
        :return: the result of the publishing (typically: ``None``)
        """
        kwargs['user_email'] = user_email
        return self.wamp.publish(topic, *args, **kwargs)
