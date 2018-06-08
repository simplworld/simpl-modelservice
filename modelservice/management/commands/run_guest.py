import os

from django.core.management.base import BaseCommand

from modelservice.crossbar.guest import ModelComponent
from modelservice.crossbar.runner import ApplicationRunner


class Command(BaseCommand):
    hostname = os.environ.get('HOSTNAME', 'localhost')
    port = os.environ.get('PORT', '8080')
    bind_str = '{}:{}'.format(hostname, port)

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--bind',
            dest='bind',
            default=self.bind_str if (self.hostname and self.port) else 'localhost:8080',
            help='host:port to bind the WebSocket server to')

        parser.add_argument(
            '--path',
            dest='path',
            default='ws',
            help='Path of the WebSocket endpoint')

        parser.add_argument(
            '--realm',
            dest='realm',
            default='realm1',
            help='name of the Realm to start')

        parser.add_argument(
            '--log-level',
            dest='loglevel',
            default='info',
            help='Log verbosity.')

        parser.add_argument(
            '--ping-interval',
            dest='ping-interval',
            default=10.,
            help="Ping interval in float seconds")

        parser.add_argument(
            '--ping-timeout',
            dest='ping-timeout',
            default=300.,
            help="Ping timeout in float seconds")

    def handle(self, *args, **options):
        url = "ws://{}/{}".format(options['bind'], options['path'])
        runner = ApplicationRunner(url=url, realm=options['realm'])
        print("Guest Options: {!r}".format(options))
        runner.run(
            ModelComponent,
            log_level=options['loglevel'],
            ping_interval=options['ping-interval'],
            ping_timeout=options['ping-timeout'],
        )
