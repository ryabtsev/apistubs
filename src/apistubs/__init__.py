import os

from contextlib import contextmanager

from django.conf import settings as app_settings
from django.test.utils import override_settings

__all__ = (
    'settings',
    'default_app_config',
)


VERSION = '0.2.x'

default_settings = {
    'ENABLED': False,
    'MIDDLEWARE_STUB_ENABLED': False,
    'MIDDLEWARE_STUB_COOKIE_MARKER': None,
    'MIDDLEWARE_STUB_COOKIE_MARKER_DEFAULT': 'middleware_stubs_env',
    'SPEC_FILES': {},
    'AUTHORIZATION_URL': None,
    'TOKEN_URL': None,
    'EXTERNAL_DOCS': None,
    'MIDDLEWARE_SPECS': None,
    'STUBS_CONFIG': None,
    'STUB_FORCE_ENABLED': False,
    'DB_PRESET_ENABLED': False,
    'PRINT_INFO': True,
}


class Settings(object):
    app_name = __name__
    app_config = '%s.apps.APIStubsConfig' % __name__

    defaults = default_settings

    prefix = 'APISTUBS_'

    def __init__(self):
        self.reload()

    def reload(self):
        for k, v in self.get_settings().items():
            if hasattr(app_settings, self.prefix + k):
                value = getattr(app_settings, self.prefix + k, None)
            else:
                value = v
            setattr(self, k, value)

        self.SPEC_FILES.update({
            'ministubs': os.path.abspath(os.path.join(
                os.path.dirname(__file__), 'data', 'specs', 'ministubs.openapi.yaml'
            )),
        })

    @contextmanager
    def override(self, **kwargs):
        try:
            with override_settings(**kwargs):
                self.reload()
                yield
        finally:
            self.reload()

    def get_settings(self):
        data = self.defaults.copy()
        data.update({
            'STUBS_CONFIG': os.path.join(app_settings.BASE_DIR, '.stubs.yaml'),
            'DB_PRESET_ENABLED': self.get_setting('STUB_FORCE_ENABLED'),
        })
        return data

    def get_setting(self, key):
        return getattr(app_settings, self.prefix + key, self.defaults[key])

    def ready(self):
        pass



settings = Settings()
default_app_config = settings.app_config
