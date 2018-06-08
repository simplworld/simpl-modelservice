import subprocess
import tempfile
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string


class Command(BaseCommand):
    hostname = os.environ.get('HOSTNAME', None)
    port = os.environ.get('PORT', None)
    bind_str = '{}:{}'.format(hostname, port)

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument('--bind',
            dest='bind',
            default=self.bind_str if (self.hostname and self.port) else 'localhost:8080',
            help='host:port to bind the WebSocket server to')

        parser.add_argument('--path',
            dest='path',
            default='ws',
            help='Path of the WebSocket endpoint')

        parser.add_argument('--realm',
            dest='realm',
            default='realm1',
            help='name of the Realm to start')

        parser.add_argument('--config',
            dest='config',
            default=None,
            help='Path to crossbar configuration')

        parser.add_argument('--print-config',
            dest='print_config',
            action="store_true",
            default=False,
            help='Print the auto-generated config')

        parser.add_argument('--loglevel',
            dest='loglevel',
            default='info',
            help='Set crossbar loglevel')

    def handle(self, *args, **options):
        config_path = options['config']
        loglevel = options['loglevel']

        if config_path is None:
            hostname, port = options['bind'].split(':')
            wsgi_module, wsgi_object = settings.WSGI_APPLICATION.rsplit('.', 1)
            ctx = {
                'wsgi_module': wsgi_module,
                'wsgi_object': wsgi_object,
                'hostname': hostname,
                'port': port,
                'realm': options['realm'],
                'ROOT_TOPIC': settings.ROOT_TOPIC,
                'DEBUG': settings.DEBUG,
            }
            config = render_to_string('modelservice/config.json.tpl', ctx)

            if options['print_config']:
                print(config)

            config_file = tempfile.NamedTemporaryFile(suffix='.json')
            config_file.write(bytes(config, 'UTF-8'))
            config_file.flush()
            config_path = config_file.name

        try:
            subprocess.check_call(['crossbar', 'start', '--config', config_path, '--loglevel', loglevel])
        except KeyboardInterrupt:
            print("Exiting.")
        finally:
            if options['config'] is None:
                config_file.close()
