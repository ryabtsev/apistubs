import sys
import json

from django.core.cache import cache

from apistubs import settings as su_settings

__all__ = (
    'RequestLog',
)


BRIGHT_YELLOW = '\033[93m'
BRIGHT_RED = '\033[91m'
RESET = '\033[0m'


def _get_request_body(request):
    try:
        # TODO: set-up proper Exceptions
        body = json.loads(request.body)
    except:
        return None
    return body


class RequestLog:
    MAX = 20
    CACHE_KEY = 'LOG'

    @classmethod
    def get(cls, env):
        value = cache.get(cls.CACHE_KEY + env)
        if not value:
            value = []
        return value

    @classmethod
    def add_success(
        cls, service='default', method='get', path='/',
        pattern=None, status=200, content={}, prompt=None, data={}, headers={},
        response_headers={}, params={}, env='', request=None
    ):
        msg = {
            'result': 'success',
            'service': service,
        }
        if pattern and path != pattern:
            msg['pattern'] = pattern
        if prompt:
            msg['prompt'] = prompt
        msg['request'] = {
            'method': method.lower(),
            'path': path,
            'data': data,
            'headers': headers,
            'params': params,
            'body': _get_request_body(request),
        }
        msg['response'] = {
            'status': status,
            'content': content,
            'headers': response_headers,
        }
        cls.add(msg, env)

        if su_settings.PRINT_INFO:
            sys.stdout.write(
                BRIGHT_YELLOW +
                '[STUB] {}: {}#{}\n'.format(service, method.lower(), pattern) +
                RESET
            )

    @classmethod
    def add_not_specified(
        cls, service='default', method='get', path='/', data={},
        headers={}, params={}, env='', request=None
    ):
        msg = {
            'result': 'not_specified',
            'service': service,
            'request': {
                'method': method.lower(),
                'path': path,
                'data': data,
                'headers': headers,
                'params': params,
                'body': _get_request_body(request),
            }
        }
        cls.add(msg, env)

        if su_settings.PRINT_INFO:
            sys.stdout.write((
                BRIGHT_RED +
                '[STUB][NOT_FOUND] {s}: {m}#{p}' +
                BRIGHT_YELLOW +
                '\n[StubSampler to fill-up Stubs.YAML] ' +
                '$ ministubs sample --snapshots [ANY] --service {s} --path {p}' +
                RESET + '\n'
            ).format(s=service, m=method.lower(), p=path))

    @classmethod
    def add(cls, item, env):
        value = cls.get(env)
        value.insert(0, item)
        value = value[:cls.MAX]
        cache.set(cls.CACHE_KEY + env, value, timeout=60 * 60 * 24 * 30)

    @classmethod
    def clear(cls, env):
        cache.delete(cls.CACHE_KEY + env)
