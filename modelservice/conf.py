import os
from django.conf import settings

SCOPE_STORAGE = getattr(settings, 'SCOPE_STORAGE',
                        'modelservice.games.storages.SIMPLStorage')
SIMPL_GAMES_URL = getattr(settings, 'SIMPL_GAMES_URL',
                          'http://localhost:8100/apis')
SIMPL_GAMES_AUTH = getattr(settings, 'SIMPL_GAMES_AUTH', None)

ROOT_TOPIC = settings.ROOT_TOPIC
CALLBACK_URL = getattr(settings, 'CALLBACK_URL',
                       'http://{hostname}:{port}/callback')

LOAD_ACTIVE_RUNS = getattr(settings, 'LOAD_ACTIVE_RUNS', True)

def get_callback_url():
    return CALLBACK_URL.format(hostname=os.environ.get('HOSTNAME', ''),
                               port=os.environ.get('PORT', ''))
