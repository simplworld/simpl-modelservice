import djclick as click

from autobahn.asyncio.wamp import ApplicationRunner

from modelservice.crossbar.profiler.worker import WorkerComponent as _WorkerComponent


HELPS = {
    'url': "The url of the WAMP router to connect to. Defaults to 'ws://localhost:8080/ws'",
    'realm': "The WAMP realm to use. Defaults to 'realm1'",
    'module': "Dotted path to the Python module containing the profile tasks to run. Default to 'modelservice.profiles'",
    'workers': "How many workers to run. Defaults to 1",
    'groups': "How many times every tasks should be run. Defaults to 1",
    'name': "What the worker should be named. Defaults to 'worker'",
    'user-email': "Optional user to impersonate. Overrides `--name`. Defaults to `None`",
    'log_level': "Log level. Defaults to 'info'. Valid values are: 'debug', 'info', 'warn', 'error', 'critical'."
}


@click.command()
@click.option('--url', '-u', default='ws://localhost:8080/ws', help=HELPS['url'])
@click.option('--realm', '-r', default='realm1', help=HELPS['realm'])
@click.option('--module', '-m', default='modelservice.profiles', help=HELPS['module'])
@click.option('--workers', '-w', type=int, default=1, help=HELPS['workers'])
@click.option('--groups', '-g', type=int, default=1, help=HELPS['groups'])
@click.option('--name', '-n', envvar='WORKER_NAME', default=None, help=HELPS['name'])
@click.option('--user-email', 'email', default=None, help=HELPS['user-email'])
@click.option('--log-level', 'log_level', default='info', help=HELPS['log_level'],
              type=click.Choice(['debug', 'info', 'warn', 'error', 'critical']))
def command(url, realm, module, workers, groups, name, email, log_level):

    class WorkerComponent(_WorkerComponent):
        user_email = email
        worker_name = name or user_email or 'worker'
        workers_count = workers
        groups_count = groups
        profile_module = module

    runner = ApplicationRunner(url=url, realm=realm)
    runner.run(WorkerComponent, log_level=log_level)
