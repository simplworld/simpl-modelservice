DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
}
SECRET_KEY = 'fake-key'
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',

    "modelservice",
    "tests",
]

ROOT_URLCONF = 'modelservice.urls'

SIMPL_GAMES_URL = 'http://localhost:9000'
SIMPL_GAMES_AUTH = ('test', 'test')
ROOT_TOPIC = 'com.example'
