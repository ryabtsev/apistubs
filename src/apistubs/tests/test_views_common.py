import os
import json
import yaml

from mock import ANY

from django.test import TestCase, override_settings
from django.urls import reverse

from apistubs import settings as su_settings
from apistubs.helpers import load_apistubs_yaml
from apistubs import urls

__all__ = (
    'StubViewTests',
    'StubForceViewTests',
    'SpecViewTests',
)

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..' ))
PROJECT = 'account'


class ViewTestsMixin(object):
    def stub_url(self, service):
        return reverse('stub', args=(service,))

    def stub_env_url(self, env, service):
        return reverse('stub_env', args=(env, service,))

    def stub_default_url(self):
        return reverse('stub_default')

    def sample_url(self, service):
        return reverse('sample', args=(service,))

    def spec_url(self):
        return reverse('spec', args=(PROJECT,))

    def spec_default_url(self):
        return reverse('spec_default')

    def index_url(self):
        return reverse('index', args=(PROJECT,))

    def index_default_url(self):
        return reverse('index_default')

    def oauth2_redirect_url(self):
        return reverse('oauth2_redirect', args=('test',))

    def patch_spec(self):
        return su_settings.override(
            APISTUBS_SPEC_FILES={
                PROJECT: os.path.join(APP_ROOT, 'demo', 'tests.api.json'),
            },
            APISTUBS_STUBS_CONFIG=[
                os.path.join(APP_ROOT, 'demo', 'tests.stubs.json'),
                os.path.join(APP_ROOT, 'demo', 'tests.stubs.yaml'),
            ],
            APISTUBS_PRINT_INFO=False
        )

    def stub_request(
        self, path, expected_status, expected_content,
        service=None, specs=None, stubs_conf=None,
        default_url=False,
        env_url=False,
        method='get',
        post=None,
        headers={},
        expected_headers={},
        use_cookies_prompt=False,
        expected_log=None,
        content_type=None
    ):
        if service is None:
            service = PROJECT

        if specs is None:
            specs = {
                service: os.path.join(APP_ROOT, 'demo', 'tests.api.json'),
            }

        if stubs_conf is None:
            stubs_conf = [
                os.path.join(APP_ROOT, 'demo', 'tests.stubs.json'),
                os.path.join(APP_ROOT, 'demo', 'tests.stubs.yaml'),
            ]

        if default_url:
            base_path = self.stub_default_url()[:-1]
        elif env_url:
            base_path = self.stub_env_url('test_env', service)[:-1]
        else:
            base_path = self.stub_url(service)[:-1]

        path = base_path + path

        with su_settings.override(
            APISTUBS_SPEC_FILES=specs,
            APISTUBS_STUBS_CONFIG=stubs_conf,
            APISTUBS_PRINT_INFO=False
        ):
            if method == 'post':
                if content_type:
                    response = self.client.post(path, data=post, content_type=content_type, **headers)
                else:
                    response = self.client.post(path, data=post, **headers)
            else:
                response = self.client.get(path)

        self.assertEqual(response.status_code, expected_status)
        content = response.content.decode()
        if content:
            content = json.loads(content)
        self.assertEqual(content, expected_content)
        self.assertTrue(expected_headers.items() <= response.headers.items())

        if expected_log:
            self.client.delete(reverse('log'))
            self.client.delete(reverse('log_env', args=('test_env',)))

        if not su_settings.DB_PRESET_ENABLED:
            return

        with su_settings.override(
            APISTUBS_PRINT_INFO=False
        ):
            data = {}
            for stubs_path in stubs_conf:
                stubs_data = load_apistubs_yaml(stubs_path)
                data.update(stubs_data)

            prompt = data.get('PROMPT')
            if prompt:
                if use_cookies_prompt:
                    headers['Cookie'] = 'STUBS_PROMPT: %s' % prompt
                    from http.cookies import SimpleCookie
                    self.client.cookies = SimpleCookie({'STUBS_PROMPT': prompt})
                else:
                    if env_url:
                        self.client.post(reverse('prompt_env', kwargs={'env': 'test_env'}), data=prompt, content_type='text/plain')
                    else:
                        self.client.post(reverse('prompt'), data=prompt, content_type='text/plain')

            data = json.dumps(data)
            if env_url:
                self.client.post(reverse('settings_env', kwargs={'env': 'test_env'}), data=data, content_type='application/json')
            else:
                self.client.post(reverse('settings'), data=data, content_type='application/json')

            with su_settings.override(
                APISTUBS_SPEC_FILES=specs,
                APISTUBS_PRINT_INFO=False
            ):
                if method == 'post':
                    if content_type:
                        response = self.client.post(
                            path, data=post, content_type=content_type, **headers
                        )
                    else:
                        response = self.client.post(path, data=post, **headers)
                else:
                    response = self.client.get(path, **headers)
            self.assertEqual(response.status_code, expected_status)
            content = response.content.decode()
            if content:
                content = json.loads(content)
            self.assertEqual(content, expected_content)
            if expected_log:
                if env_url:
                    log_url = reverse('log_env', args=('test_env',))
                else:
                    log_url = reverse('log')

                response = self.client.get(log_url + '?format=json')
                content = response.content.decode()
                content = json.loads(content)
                self.assertEqual(content, expected_log)

                if not env_url:
                    log_url = reverse('log_env', args=('test_env',))
                else:
                    log_url = reverse('log')

                response = self.client.get(log_url + '?format=json')
                self.assertEqual(json.loads(response.content.decode()), {'log': []})


@override_settings(ROOT_URLCONF=urls, PROJECT=PROJECT)
class StubViewTests(ViewTestsMixin, TestCase):
    maxDiff = None

    def test_without_methods(self):
        self.stub_request('/', 404, {'error': 'not_secified'}, default_url=True)

    def test_does_not_exist_in_spec(self):
        self.stub_request('/does_not_exist_in_spec/', 404, {'error': 'not_secified'}, default_url=True)

    def test_does_not_exist_in_spec_but_in_conf(self):
        self.stub_request('/does_not_exist_in_spec_but_in_conf/', 200, {'status': 'one'},
                          default_url=True)

    def test_does_not_exist_in_spec_but_in_conf_use_cookies_prompt(self):
        self.stub_request(
            '/does_not_exist_in_spec_but_in_conf/', 200, {'status': 'one'},
            default_url=True, use_cookies_prompt=True,
            expected_log={'log': [{
                'result': 'success',
                'service': 'account',
                'prompt': 'ok',
                'request': {
                    'method': 'get',
                    'path': '/does_not_exist_in_spec_but_in_conf/',
                    'headers': ANY,
                    'params': {},
                    'data': {},
                    'body': None,
                },
                'response': {
                    'status': 200,
                    'content': {'status': 'one'},
                    'headers': {},
                },
            }]}
        )

    def test_default(self):
        self.stub_request('/family/api/children/list/', 202, {}, method='post')

    def test_default_env(self):
        self.stub_request('/family/api/children/list/', 202, {}, method='post', env_url=True)

    def test_example_number_predifined(self):
        self.stub_request('/auth/sessions/333/list/', 200, {'account_id': 12345, 'sessions': []})

    def test_env_stub(self):
        self.stub_request(
            '/auth/sessions/333/list/', 200, {'account_id': 12345, 'sessions': []}, env_url=True,
            expected_log={"log": [
                {
                    "result": "success",
                    "service": 'account',
                    "pattern": "/auth/sessions/{accountId}/list/",
                    "prompt": 2,
                    "request": {
                        "method": "get",
                        "path": "/auth/sessions/333/list/",
                        "data": {},
                        "headers": {
                            "Cookie": ""
                        },
                        "params": {},
                        'body': None,
                    },
                    "response": {
                        "status": "200",
                        "content": {
                            "account_id": 12345,
                            "sessions": []
                        },
                        "headers": {}
                    }
                }
            ]
        })

    def test_example_number_predifined(self):
        self.stub_request('/auth/sessions/333/list/', 200, {'account_id': 12345, 'sessions': []})

    def test_default_example(self):
        self.stub_request('/auth/sessions/333/list/', 200, {
            'account_id': 12345,
            'sessions': [ANY, ANY],
        }, service='spa2')

    def test_custom_status(self):
        self.stub_request('/auth/sessions/333/list/', 500, {}, service='spa3')

    def test_custom_status_and_response(self):
        self.stub_request('/auth/sessions/333/list/', 500, '', service='spa4')

    def test_template_response(self):
        query = (
            'client_id=929991016477-0t10462r6ifugrcqoeieeqokfqklva3o.apps.googleusercontent.com&'
            'redirect_uri=https%3A%2F%2Fexample.net%2Fpersonal%2Fcredentials%2Fexternal%2Fbind%2Fprocess%2F&'
            'response_type=code&'
            'scope=profile+email+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuser.birthday.read&'
            'state=google%3A9565d1665544b2ed0a8d5a4a9a599191'
        )
        self.stub_request('/auth/sessions/333/list/?' + query, 301, {}, service='spa5', expected_headers={
            'Location': (
                'https://example.net/personal/credentials/external/bind/process/&state=google:9565d1665544b2ed0a8d5a4a9a599191&'
                'scope=profile%20email%20https%3A//www.googleapis.com/auth/user.birthday.read&'
                'authuser=1&'
                'prompt=none&'
                'code=111111'
            ),
        })

    def test_custom_third(self):
        self.stub_request('/custom/', 409, {}, service='third')

    def test_skipped(self):
        self.stub_request('/skipped/', 404, {'error': 'not_secified'}, service='third')

    def test_skipped_with_prompt(self):
        self.stub_request('/skipped2/', 404, {'error': 'not_secified'}, service='third')

    def test_skipped_with_prompt_env(self):
        self.stub_request('/skipped2/', 404, {'error': 'not_secified'}, service='third', env_url=True)

    def test_skipped_with_cookie_prompt(self):
        self.stub_request(
            '/skipped2/', 404, {'error': 'not_secified'}, service='third',
            use_cookies_prompt=True, method='post',
            post=json.dumps({'key_post': 'value_post'}),
            content_type='application/json',
            expected_log={'log': [{
                'result': 'not_specified',
                'service': 'third',
                'request': {
                    'method': 'post',
                    'path': '/skipped2/',
                    'headers': ANY,
                    'params': {},
                    'data': {},
                    'body': {'key_post': 'value_post'},
                },
            }]}
        )

    def test_custom_response(self):
        self.stub_request(
            '/realm/detect/', 409, {'realm': 'one'},
            expected_headers={'Etag': '32423412342'}
        )

    def test_request_view(self):
        self.stub_request('/personal/account/birthday/', 202, {}, method='post')

    def test_parametrize(self):
        self.stub_request('/parametrize/?key=value&key2=value2', 200, {'status': 'ok'}, method='get')

    def test_parametrize_data(self):
        self.stub_request(
            '/parametrize/?key=value', 200, {'status': 'ok'}, method='post',
            post={'key_post': 'value_post'},
            headers={'HTTP_X_TRACKING_ID': '500zxc'}
        )


@override_settings(ROOT_URLCONF=urls, PROJECT=PROJECT)
class StubForceViewTests(ViewTestsMixin, TestCase):
    def stub_url(self, service):
        return reverse('stub_force', args=(service,))

    def test_default(self):
        self.stub_request('/family/api/children/list/', 202, {}, method='post')

    def test_default_env(self):
        self.stub_request('/family/api/children/list/', 202, {}, method='post', env_url=True)

    def test_example_number_predifined(self):
        self.stub_request('/auth/sessions/333/list/', 200, {'account_id': 12345, 'sessions': []})

    def test_env_stub(self):
        self.stub_request(
            '/auth/sessions/333/list/', 200, {'account_id': 12345, 'sessions': []}, env_url=True,
            expected_log={"log": [
                {
                    "result": "success",
                    "service": 'account',
                    "pattern": "/auth/sessions/{accountId}/list/",
                    "prompt": 2,
                    "request": {
                        "method": "get",
                        "path": "/auth/sessions/333/list/",
                        "data": {},
                        "headers": {
                            "Cookie": ""
                        },
                        "params": {},
                        'body': None,
                    },
                    "response": {
                        "status": "200",
                        "content": {
                            "account_id": 12345,
                            "sessions": []
                        },
                        "headers": {}
                    }
                }
            ]
        })

    def test_example_number_predifined(self):
        self.stub_request('/auth/sessions/333/list/', 200, {'account_id': 12345, 'sessions': []})

    def test_default_example(self):
        self.stub_request('/auth/sessions/333/list/', 200, {
            'account_id': 12345,
            'sessions': [ANY, ANY],
        }, service='spa2')

    def test_custom_status(self):
        self.stub_request('/auth/sessions/333/list/', 500, {}, service='spa3')

    def test_custom_status_and_response(self):
        self.stub_request('/auth/sessions/333/list/', 500, '', service='spa4')

    def test_template_response(self):
        query = (
            'client_id=929991016477-0t10462r6ifugrcqoeieeqokfqklva3o.apps.googleusercontent.com&'
            'redirect_uri=https%3A%2F%2Fexample.net%2Fpersonal%2Fcredentials%2Fexternal%2Fbind%2Fprocess%2F&'
            'response_type=code&'
            'scope=profile+email+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuser.birthday.read&'
            'state=google%3A9565d1665544b2ed0a8d5a4a9a599191'
        )
        self.stub_request('/auth/sessions/333/list/?' + query, 301, {}, service='spa5', expected_headers={
            'Location': (
                'https://example.net/personal/credentials/external/bind/process/&state=google:9565d1665544b2ed0a8d5a4a9a599191&'
                'scope=profile%20email%20https%3A//www.googleapis.com/auth/user.birthday.read&'
                'authuser=1&'
                'prompt=none&'
                'code=111111'
            ),
        })

    def test_skipped_with_prompt(self):
        self.stub_request('/skipped2/', 404, {'error': 'not_secified'}, service='third')

    def test_skipped_with_prompt_env(self):
        self.stub_request('/skipped2/', 404, {'error': 'not_secified'}, service='third', env_url=True)

    def test_custom_response(self):
        self.stub_request(
            '/realm/detect/', 409, {'realm': 'one'},
            expected_headers={'Etag': '32423412342'}
        )

    def test_request_view(self):
        self.stub_request('/personal/account/birthday/?birthday=birthday', 202, {}, method='post')


@override_settings(ROOT_URLCONF=urls, PROJECT=PROJECT)
class SpecViewTests(ViewTestsMixin, TestCase):
    def test_index(self):
        response = self.client.get(self.oauth2_redirect_url())
        self.assertEqual(response.status_code, 200)

        with self.patch_spec():
            self.client.get(self.index_url())
            self.client.get(self.index_default_url())

    def test_spec(self):
        with self.patch_spec():
            for url in [
                self.spec_url(),
                self.spec_default_url()
            ]:
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                content = json.loads(response.content)
                self.assertEqual(content, {
                    'openapi': ANY,
                    'info': ANY,
                    'servers': ANY,
                    'paths': ANY,
                    'tags': ANY,
                    'components': ANY,
                })
