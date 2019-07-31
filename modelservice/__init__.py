from django.utils.module_loading import autodiscover_modules

from .callees import registry as callee_registry
from .games.registry import registry as games_registry
from .pubsub import registry as pubsub_registry
from .webhooks import registry as hook_registry


_version = "0.7.15"
__version__ = VERSION = tuple(map(int, _version.split('.')))

default_app_config = 'modelservice.apps.ModelserviceConfig'


def autodiscover():
    autodiscover_modules('webhooks', register_to=hook_registry)
    autodiscover_modules('callees', register_to=callee_registry)
    autodiscover_modules('pubsub', register_to=pubsub_registry)
    autodiscover_modules('games', register_to=games_registry)
