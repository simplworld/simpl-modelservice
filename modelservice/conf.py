import os
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

SCOPE_STORAGE = getattr(
    settings, "SCOPE_STORAGE", "modelservice.games.storages.SIMPLStorage"
)
SIMPL_GAMES_URL = getattr(settings, "SIMPL_GAMES_URL", "http://localhost:8100/apis")
SIMPL_GAMES_AUTH = getattr(settings, "SIMPL_GAMES_AUTH", None)

ROOT_TOPIC = settings.ROOT_TOPIC
CALLBACK_URL = getattr(settings, "CALLBACK_URL", "http://{hostname}:{port}/callback")

LOAD_ACTIVE_RUNS = getattr(settings, "LOAD_ACTIVE_RUNS", True)

PROFILING_ENABLED = getattr(settings, "PROFILING_ENABLED", False)
MONITORING_ENABLED = getattr(settings, "MONITORING_ENABLED", False)

MODEL_TICKET = getattr(settings, "MODEL_TICKET", None)
if MODEL_TICKET is None:
    raise ImproperlyConfigured(
        "MODEL_TICKET must be set to a secure password like string for guest model process"
    )


def get_callback_url():
    return CALLBACK_URL.format(
        hostname=os.environ.get("HOSTNAME", ""), port=os.environ.get("PORT", "")
    )
