# vim: ft=python:sw=4:ts=4


from django.core.management.base import BaseCommand
from ...utils import aws_profiler_management as aws_profiler


class Command(BaseCommand):

    _args = "start|stop|status".split('|')

    help = '''
    Valid arguments: start, stop, status

    '''

    def add_arguments(self, parser):
        for option in self._args:
            parser.add_argument(f'--{option}', action='store_true',)

    def handle(self, *args, **kwargs):

        if kwargs['status']:
            self.stdout.write('\n'.join(aws_profiler.status()))
        elif kwargs['start']:
            self.stdout.write('\n'.join(aws_profiler.start()))
        elif kwargs['stop']:
            self.stdout.write('\n'.join(aws_profiler.stop()))
