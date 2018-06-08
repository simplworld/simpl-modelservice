# coding=utf-8
"""
WAMP component that runs profiling tasks.

Multiple instances of this component will be started. Once they are all connected, a leader will be
elected and that instance will take care of orchestrating the tasks.

Each task gets as many times as ``WorkerComponent.groups_count``, with an increasing number or workers performing the
task simultaneously (see func:`~modelservice.crossbar.profiler.worker.WorkerComponent.build_roster`).
"""
import asyncio
import inspect
import random

from collections import defaultdict
from functools import partial

import djclick as click

from autobahn.asyncio.wamp import ApplicationSession
from autobahn.wamp.types import PublishOptions
from modelservice.utils.instruments import StatAggregator, Timer

from .discovery import discover_tasks, pull_tasks, task_method


def start(name):
    return name + '.start'


def done(name):
    return name + '.done'


def error(name):
    return name + '.error'


PRINCIPAL_TICKET = '===secret!!!==='


class WorkerComponent(ApplicationSession):
    worker_name = 'worker1'
    user_email = None
    workers_count = 1
    groups_count = 1
    all_groups = defaultdict(set)
    worker_groups = []
    leader = None

    done_tasks = defaultdict(lambda: defaultdict(list))
    error_tasks = defaultdict(lambda: defaultdict(list))

    done_task_count = 0
    stats = defaultdict(lambda: defaultdict(dict))

    subscriptions = []
    sessions = set()

    profile_module = 'modelservice.profiles'
    publish_all = PublishOptions(exclude_me=False)

    def __init__(self, *args, **kwargs):
        suite = discover_tasks(self.profile_module)
        self.tasks = pull_tasks(suite)
        super().__init__(*args, **kwargs)

    @property
    def is_leader(self):
        return self.leader == self.details.session

    async def onConnect(self):
        self.join(self.config.realm, ['ticket'], 'worker')

    async def onChallenge(self, challenge):
        if challenge.method == "ticket":
            return PRINCIPAL_TICKET
        else:
            raise Exception("Invalid authmethod {}".format(challenge.method))

    async def _fetch_sessions(self):
        sessions_list = await self.call('wamp.session.list')
        workers = [
            await self.call("wamp.session.get", session)
            for session in sessions_list
            if session not in self.sessions
        ]
        return [worker['session'] for worker in workers if worker['authrole'] == 'profiler']

    async def update_sessions(self):
        self.sessions.update((await self._fetch_sessions()))

    async def elect_leader(self, session):
        if self.leader is None:
            self.leader = session

            if self.leader == self.details.session:
                click.echo(click.style("Worker '{}' elected as leader".format(self.worker_name), fg='green'))

                self.subscriptions.append(
                    await self.subscribe(self.receive_stat, 'leader.add_stat')
                )

                await self.build_roster()
                await self.start_workers()

    async def build_roster(self):
        """
        Assign workers to groups, so that tasks can be run multiple times over
        a different amount of workers.

        Groups 1–(N) will have increasing amount of workers.
        Group 0 will always have 1 and only 1 worker.
        """
        group_names = list(range(self.groups_count))

        await self.update_sessions()
        sessions = list(self.sessions)

        single_runner = sessions[0]
        self.publish(
            'worker.{}.join_groups'.format(single_runner), group_names,
            options=self.publish_all
        )
        for group in group_names:
            self.all_groups[group].add(single_runner)

        if self.groups_count == 1:
            for idx, session in enumerate(sessions[1:]):
                topic = 'worker.{}.join_groups'.format(session)
                self.publish(topic, group_names, options=self.publish_all)
                for group in group_names:
                    self.all_groups[group].add(session)
            return

        for idx, session in enumerate(sessions[1:]):
            step = idx % (self.groups_count - 1)
            session_groups = group_names[step + 1:]
            topic = 'worker.{}.join_groups'.format(session)
            self.publish(topic, session_groups, options=self.publish_all)
            for group in session_groups:
                self.all_groups[group].add(session)

    async def start_group(self, name, group, sessions):
        self.publish(start(name), {'group': group, 'workers': len(sessions)}, options=self.publish_all)
        while len(self.done_tasks[name][group]) < len(sessions):
            await asyncio.sleep(0.1)

    async def start_workers(self):
        all_groups = self.all_groups.copy()

        timer = Timer()
        timer.start()
        for name, _ in self.tasks:
            for group, sessions in all_groups.items():
                click.echo(click.style(
                    "→ Running task '{}' on group '{}' ({} workers).".format(
                        name, group, len(sessions),
                    )
                ))
                await self.start_group(name, group, sessions)
                if len(self.error_tasks[name]):
                    click.echo(click.style(
                        "✗ Task `{}` on Group '{}' failed.".format(name, group),
                        fg='red',
                    ))
                else:
                    self.summary(name, group)
                    click.echo(click.style(
                        "✓ Task `{}` on Group '{}' done.".format(name, group),
                        fg='green',
                    ))

            click.echo(click.style("Task '{}' done.".format(name), fg='green'))
            self.done_task_count += 1
            if self.done_task_count == len(self.tasks):
                timer.stop()
                click.echo(
                    click.style("All tasks done in {:.3f}s. Clients leaving.".format(
                        timer.elapsed,
                        self.worker_name,
                    ), fg='red')
                )
                self.publish('worker.leave', options=self.publish_all)

    def join_groups(self, groups):
        self.worker_groups = groups

    async def start_task(self, task_name, task, message):
        group = message.get('group', None)
        if group not in self.worker_groups:
            return
        worker_count = message['workers']
        task.wamp = self
        task.workers_count = worker_count
        task.group_name = group
        task.publish_stat = partial(
            self.publish_stat,
            task=task_name, group=group,
        )

        method = task_method(task)
        try:
            if inspect.iscoroutinefunction(method):
                await method()
            else:
                method()
        except:
            self.publish(error(task_name), {
                'task': task_name,
                'session': self.details.session,
                'group': group,
            }, options=self.publish_all)
            raise
        finally:
            await asyncio.sleep(0.01)
            self.publish(done(task_name), {
                'task': task_name,
                'session': self.details.session,
                'group': group,
            }, options=self.publish_all)

    async def worker_done(self, message):
        task = message['task']
        session = message['session']
        group = message['group']

        self.done_tasks[task][group].append(session)

    async def worker_error(self, message):
        task = message['task']
        session = message['session']
        group = message['group']

        self.error_tasks[task][group].append(session)

    def publish_stat(self, stat_id, value, *, fmt=None, attribute=None, task, group):
        return self.publish('leader.add_stat', stat_id, value, fmt, attribute, task, group, options=self.publish_all)

    def receive_stat(self, stat_id, value, fmt, attribute, task, group):
        stat = self.stats[task][group].setdefault(stat_id, StatAggregator(fmt=fmt, attribute=attribute))
        stat.push(value)

    def summary(self, task, group):
        stats = self.stats[task][group]
        for stat in stats.values():
            click.echo(click.style('ℹ {!s}'.format(stat), fg='blue'))

    async def onJoin(self, details):
        # 1. collect the tasks
        # 2. subscribe to topics
        # 3. every time a tasks topic is published:
        #   run the task
        #   publish to a `done` topic
        self.details = details

        self.subscriptions.append(
            await self.subscribe(self.join_groups, "worker.{}.join_groups".format(details.session))
        )

        self.subscriptions.append(
            await self.subscribe(self.elect_leader, "worker.elect_leader")
        )

        self.subscriptions.append(
            await self.subscribe(self.leave, "worker.leave")
        )

        for name, task in self.tasks:
            task_handler = partial(self.start_task, name, task)
            self.subscriptions.append(
                await self.subscribe(task_handler, start(name))
            )
            self.subscriptions.append(
                await self.subscribe(self.worker_done, done(name))
            )
            self.subscriptions.append(
                await self.subscribe(self.worker_error, error(name))
            )
        # Nominate a leader.
        await self.update_sessions()
        while len(self.sessions) < self.workers_count:
            await asyncio.sleep(0.1)
            await self.update_sessions()

        random.seed(1234)  # Any value would do, as long as it's the same across workers
        random_leader = random.choice(list(self.sessions))
        if random_leader == self.details.session:
            self.publish('worker.elect_leader', random_leader, options=self.publish_all)

    def onDisconnect(self):
        super().onDisconnect()
        loop = asyncio.get_event_loop()
        loop.stop()
