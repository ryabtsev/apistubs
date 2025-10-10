import json

from django.core.cache import cache

from apistubs import settings as su_settings
from apistubs.constants import METHODS
from apistubs.helpers import parse_preset_response, load_apistubs_yaml
from apistubs.spec import (
    oas_find_path,
    select_path,
    response_from_spec,
)

if su_settings.DB_PRESET_ENABLED:
    from apistubs.dbpreset.models import Mock

__all__ = (
    'StubResponse',
    'YamlSettings',
    'HeadersSettings',
    'DBSettings',
    'ComboSettings',
    'get_stub_response',
)


class Prompt:
    def __init__(self, value, env=False):
        self.value = value
        self.env = env

    def use_alias(self, status_aliases):
        selected_alias = None
        selected_alias_index = len(self.value)
        selected_alias_count = 0
        for status_alias in status_aliases:
            if isinstance(status_alias, str):
                alias = status_alias.split('-')[-1]
                if alias in self.value:
                    selected_alias_count += 1
                    index = self.value.index(alias)
                    if selected_alias_index > index:
                        selected_alias = status_alias
                        selected_alias_index = index

        if selected_alias_count > 1 and self.env is not None:
            self.value.pop(selected_alias_index)
            self.set_value(self.env, ' '.join(self.value))

        return selected_alias

    @classmethod
    def get_value(cls, env):
        return cache.get('PROMPT' + env)

    @classmethod
    def set_value(cls, env, value):
        return cache.set('PROMPT' + env, value, timeout=60 * 60 * 24 * 30)

    @classmethod
    def delete_value(cls, env):
        return cache.delete('PROMPT' + env)


class StubResponse:
    def __init__(
        self, status=200, content={}, headers=None, db_id=None, pattern=None, prompt=None
    ):
        self.status = status
        self.content = content
        if headers:
            self.headers = headers
        else:
            self.headers = {}
        self._db_id = db_id
        self.pattern = pattern
        self.prompt = prompt


class BaseSettingsSource:
    def __init__(self, spec_name, env='', path=None):
        self.spec_name = spec_name
        self.prompt = None
        self.env = env
        self.path = path
        self.values = self.load()

    def load(self):
        pass

    def set_prompt(self, value):
        if not value:
            return

        if isinstance(value, bytes):
            value = value.decode('utf-8')

        value = value.strip().replace('\n', ' ')
        value = [i.strip() for i in value.split(' ')]
        self.prompt = value

    @property
    def patterns(self):
        patterns = []

        for key in self.values:
            patterns.append(key.split('#')[-1])

        return patterns


class YamlSettings(BaseSettingsSource):
    def load(self):
        self.data_all = {}
        yaml_path = self.path
        if not yaml_path:
            return {}
        try:
            data = load_apistubs_yaml(yaml_path)
        except FileNotFoundError:
            return {}
        if not data:
            return {}
        self.set_prompt(data.get('PROMPT'))
        self.data_all = data
        return data.get(self.spec_name, {})


class HeadersSettings(BaseSettingsSource):
    def __init__(self, request):
        self.request = request
        self.values = self.load()

    @property
    def response(self):
        status = self.request.META.get('HTTP_STUB_RESPONSE_STATUS')
        content = self.request.META.get('HTTP_STUB_RESPONSE_CONTENT')
        headers = self.request.META.get('HTTP_STUB_RESPONSE_HEADERS')
        try:
            content = json.loads(content)
        except:
            return
        try:
            headers = json.loads(headers)
        except:
            return
        if status is None:
            return
        return StubResponse(status=int(status), content=content, headers=headers)


class DBSettings(BaseSettingsSource):
    def load(self):
        values = {}
        for response in Mock.objects.order_by('index').filter(spec_name=self.spec_name, env=self.env):
            values['#'.join([response.method, response.pattern])] = response.get_content()
        return values


class CookiesSettings(BaseSettingsSource):
    def __init__(self, request, env=''):
        self.request = request
        self.prompt = None
        self.env = env
        self.values = self.load()

    def load(self):
        paths = {}

        for cookie_name in self.request.COOKIES:
            for method in METHODS:
                if cookie_name.startswith('%s#' % method):
                    paths[cookie_name] = self.request.COOKIES[cookie_name]
                    paths.append(cookie_name.split('#')[-1])

        prompt = self.request.COOKIES.get('STUBS_PROMPT')
        if prompt:
            cache.set('PROMPT', prompt, 30)
        else:
            prompt = Prompt.get_value(self.env)
        self.set_prompt(prompt)
        return paths


class ComboSettings:
    def __init__(self, spec_name, request, env=''):
        self.request = request
        self.spec_name = spec_name
        self.use_db = su_settings.DB_PRESET_ENABLED
        self.prompt = None

        stubs_configs = su_settings.STUBS_CONFIG
        if not isinstance(stubs_configs, list):
            stubs_configs = [stubs_configs]
        self.yamls = [
            YamlSettings(spec_name, path=stubs_config)
            for stubs_config in stubs_configs
        ]
        for item in self.yamls:
            if item.prompt:
                self.prompt = Prompt(item.prompt)
                break

        self.headers = HeadersSettings(request)
        self.cookies = CookiesSettings(request, env=env)
        if self.cookies.prompt:
            self.prompt = Prompt(self.cookies.prompt, env=env)

        if self.use_db:
            self.db = DBSettings(spec_name, env=env)

    @property
    def patterns(self):
        pattens = []
        if self.use_db:
            pattens += self.db.patterns

        pattens += self.cookies.patterns
        for source in self.yamls:
            pattens += source.patterns

        return pattens

    def get_preset_response(self, pattern, path):
        sources = []
        if self.use_db:
            sources.append(self.db.values)
        sources.append(self.cookies.values)

        for source in self.yamls:
            sources.append(source.values)

        for source in sources:
            mp = '#'.join([self.request.method.lower(), path])
            if mp in source:
                return source[mp]
            mp = '#'.join([self.request.method.lower(), pattern])
            if mp in source:
                return source[mp]


def get_stub_response(spec_name, request, path, explicit=False, env=''):
    settings = ComboSettings(spec_name, request, env=env)

    response = settings.headers.response
    if response:
        return response

    pattern = oas_find_path(spec_name, path)
    if not pattern:
        pattern = select_path(settings.patterns, path, request=request)

    if not pattern:
        return

    preset_response = settings.get_preset_response(pattern, path)

    requested_status = None
    requested_example = None
    if preset_response:
        (
            requested_status,
            requested_example,
            requested_content,
            requested_headers,
        ) = parse_preset_response(preset_response, settings.prompt)
        if requested_status == 0:
            return
        if requested_status is not None and requested_content is not None:
            return StubResponse(
                status=requested_status,
                content=requested_content,
                headers=requested_headers,
                pattern=pattern,
                prompt=requested_example
            )

    if requested_status is None and explicit:
        return

    response = response_from_spec(
        request, spec_name, pattern,
        requested_status, requested_example
    )

    if response:
        status, content, headers = response
        return StubResponse(
            status=status,
            content=content,
            headers=headers,
            pattern=pattern,
            prompt=requested_example
        )

    if not requested_status:
        return

    return StubResponse(status=requested_status, pattern=pattern)
