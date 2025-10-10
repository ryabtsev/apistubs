import yaml
import json
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apistubs import urls
from apistubs.helpers import parse_preset_response
from apistubs.stubs import Prompt

__all__ = (
    'ParsePresetResponseTests',
    'PromptTests',
)


PROJECT = 'account'
APISTUBS = """
apistubs: 1.0.0

account:
  get#/service/accounts/{id}/accounts/:
    200-accounts_do_not_exist:
      accounts: []
    200-accounts_ok:
      accounts:
        - account_id: 500297762
          game: wows
          state: 3
          registered: True
    409-accounts_timeout:
      error: timeout
    500-accounts_error:
      error: server_error
"""


class ParsePresetResponseTests(SimpleTestCase):
    def test_ok(self):
        self.assertEqual(parse_preset_response('200'), (200, None, None, None,))
        self.assertEqual(parse_preset_response(200), (200, None, None, None,))
        self.assertEqual(parse_preset_response('200-key'), (200, 'key', None, None,))
        self.assertEqual(parse_preset_response(
            {200: {'status': 'ok'}}),
            (200, None, {'status': 'ok'}, None,)
        )
        self.assertEqual(parse_preset_response(
            {'200-full': {'status': 'ok'}}),
            (200, 'full', {'status': 'ok'}, None,)
        )
        self.assertEqual(parse_preset_response(
            {
                '200-full': {'status': 'ok'},
                '200-empty': {'status': 'ok'},
                '200-none': {'status': 'ok'},
            }, prompt=Prompt('empty')),
            (200, 'empty', {'status': 'ok'}, None,)
        )


@override_settings(ROOT_URLCONF=urls, PROJECT=PROJECT)
class PromptTests(TestCase):
    def test_ok(self):
        env = 'takeout'
        value = ['a2', 'a1', 'a3', 'b1', 'c1', 'c2', 'c4']
        prompt = Prompt(value, env=env)
        Prompt.set_value(env, value)

        alias = prompt.use_alias(['200-b0', '200-b1', '409-b2'])
        self.assertEqual(alias, '200-b1')

        alias = prompt.use_alias(['200-a0', '200-a1', '409-a2', '409-a3', '409-a4'])
        self.assertEqual(alias, '409-a2')
        self.assertEqual(Prompt.get_value(env), ' '.join(['a1', 'a3', 'b1', 'c1', 'c2', 'c4']))

        alias = prompt.use_alias(['200-a0', '200-a1', '409-a2', '409-a3', '409-a4'])
        self.assertEqual(alias, '200-a1')
        self.assertEqual(Prompt.get_value(env), ' '.join(['a3', 'b1', 'c1', 'c2', 'c4']))

        for x in range(4):
            alias = prompt.use_alias(['200-a0', '200-a1', '409-a2', '409-a3', '409-a4'])
            self.assertEqual(alias, '409-a3')
            self.assertEqual(Prompt.get_value(env), ' '.join(['a3', 'b1', 'c1', 'c2', 'c4']))

        value = ['b1', 'c1', 'c2', 'c4']
        prompt = Prompt(value, env=env)
        Prompt.set_value(env, ' '.join(value))
        alias = prompt.use_alias(['200-a0', '200-a1', '409-a2', '409-a3', '409-a4'])
        self.assertEqual(Prompt.get_value(env), ' '.join(['b1', 'c1', 'c2', 'c4']))
        self.assertEqual(alias, None)

        alias = prompt.use_alias(['200-c0', '409-c4', '200-c1', '409-c2', '409-c3'])
        self.assertEqual(alias, '200-c1')
        self.assertEqual(Prompt.get_value(env), ' '.join(['b1', 'c2', 'c4']))

        alias = prompt.use_alias(['200-c0', '409-c4', '200-c1', '409-c2', '409-c3'])
        self.assertEqual(alias, '409-c2')
        self.assertEqual(Prompt.get_value(env), ' '.join(['b1', 'c4']))

        for x in range(4):
            alias = prompt.use_alias(['200-c0', '409-c4', '200-c1', '409-c2', '409-c3'])
            self.assertEqual(alias, '409-c4')
            self.assertEqual(Prompt.get_value(env), ' '.join(['b1', 'c4']))

    def setup_stubs(self, env_url=False):
        data = yaml.safe_load(APISTUBS)
        if env_url:
            self.client.post(reverse('settings_env', kwargs={'env': 'test_env'}), data=data, content_type='application/json')
        else:
            self.client.post(reverse('settings'), data=data, content_type='application/json')

    def setup_prompt(self, prompt, env_url=False):
        if prompt is None:
            if env_url:
                self.client.delete(reverse('prompt_env', kwargs={'env': 'test_env'}))
            else:
                self.client.delete(reverse('prompt'))
        else:
            if env_url:
                self.client.post(reverse('prompt_env', kwargs={'env': 'test_env'}), data=prompt, content_type='text/plain')
            else:
                self.client.post(reverse('prompt'), data=prompt, content_type='text/plain')

    def get_prompt(self, env_url=False):
        if env_url:
            self.client.get(reverse('prompt_env', kwargs={'env': 'test_env'}))
        else:
            self.client.get(reverse('prompt'))

    def stub_request(self, env_url=False):
        url = reverse('stub', args=('account',))[:-1] + '/service/accounts/1/accounts/'
        if env_url:
            url = '/test_env' + url
        response = self.client.get(url)
        return json.loads(response.content)

    def _test_full_flow(self, env_url=False):
        self.setup_stubs(env_url=env_url)
        self.assertEqual(self.stub_request(env_url=env_url), {'accounts': []})

        self.setup_prompt('accounts_ok', env_url=env_url)
        self.assertEqual(self.stub_request(env_url=env_url), {
            'accounts': [{'account_id': 500297762,  'game': 'wows', 'registered': True,'state': 3}],
        })

        self.setup_prompt('accounts_error  accounts_timeout  accounts_ok', env_url=env_url)
        self.assertEqual(self.stub_request(env_url=env_url), {'error': 'server_error'})
        self.assertEqual(self.stub_request(env_url=env_url), {'error': 'timeout'})
        self.assertEqual(self.stub_request(env_url=env_url), {
            'accounts': [{'account_id': 500297762,  'game': 'wows', 'registered': True,'state': 3}],
        })

        self.setup_prompt(None, env_url=env_url)
        self.assertEqual(self.stub_request(env_url=env_url), {
            'accounts': [],
        })

    def test_full_flow(self):
        self._test_full_flow()

    def test_full_flow_env(self):
        self._test_full_flow(env_url=True)
