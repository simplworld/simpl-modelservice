from django.apps import AppConfig


class ModelserviceConfig(AppConfig):
    name = 'modelservice'

    def ready(self):
        super(ModelserviceConfig, self).ready()
        self.module.autodiscover()
