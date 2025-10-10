import json
import yaml

from django.test import TestCase, override_settings
from django.urls import reverse

from apistubs import settings as su_settings
from apistubs import urls

__all__ = (
    'SettingsViewTests',
)


PROJECT = 'account'
STUB_SETTINGS = {
    'account': {
        'get#/requests': 200,
        'get#/requests': '200-ok',
        'get#/requests': {
            '300': {
                'status': 'ok',
            }
        },
    }
}


@override_settings(ROOT_URLCONF=urls, PROJECT=PROJECT)
class SettingsViewTests(TestCase):
    def get_url(self, env=False):
        if env:
            return reverse('settings_env', kwargs={'env': 'test'})
        return reverse('settings')

    def post(self, data, is_yaml=False, env=False):
        if is_yaml:
            data = yaml.dump(data)
            return self.client.patch(self.get_url(env=env), data=data, content_type='application/json')

        data = json.dumps(data)
        return self.client.post(self.get_url(env=env), data=data, content_type='application/json')

    def get(self, response_format='yaml', env=False):
        return self.client.get('%s?format=%s' %(self.get_url(env=env), response_format,))

    def delete(self):
        return self.client.delete(self.get_url())

    def test_ok(self):
        if not su_settings.DB_PRESET_ENABLED:
            return

        response = self.post(STUB_SETTINGS)
        response = self.post(STUB_SETTINGS, env=True)
        response = self.get()
        self.assertEqual(yaml.safe_load(response.content), STUB_SETTINGS)
        response = self.get(env=True)
        self.assertEqual(yaml.safe_load(response.content), STUB_SETTINGS)
        response = self.get(response_format='json')
        self.assertJSONEqual(response.content, STUB_SETTINGS)
        response = self.delete()
        response = self.get()
        self.assertJSONEqual(response.content, {})

    def test_ok_yaml(self):
        if not su_settings.DB_PRESET_ENABLED:
            return

        response = self.post(STUB_SETTINGS, is_yaml=True)
        response = self.post(STUB_SETTINGS, is_yaml=True, env=True)
        response = self.get()
        self.assertEqual(yaml.safe_load(response.content), STUB_SETTINGS)
        response = self.get( env=True)
        self.assertEqual(yaml.safe_load(response.content), STUB_SETTINGS)
