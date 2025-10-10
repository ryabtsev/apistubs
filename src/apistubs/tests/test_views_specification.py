import json
import yaml
import os

from django.test import TestCase, override_settings
from django.urls import reverse

from apistubs import settings as su_settings
from apistubs import urls
from apistubs.helpers import load_apistubs_yaml

__all__ = (
    'SpecificationViewTests',
)


PROJECT = 'account'


@override_settings(ROOT_URLCONF=urls, PROJECT=PROJECT)
class SpecificationViewTests(TestCase):
    def get_url(self, spec):
        return reverse('index', kwargs={'spec': spec})

    def get_spec_url(self, spec):
        return reverse('spec', kwargs={'spec': spec})

    def post(self, spec, data, cdn=False):
        data = json.dumps(data)
        if cdn:
            return self.client.post(self.get_spec_url_cdn(spec), data=data, content_type='application/json')
        return self.client.post(self.get_url(spec), data=data, content_type='application/json')

    def get(self, spec, cdn=False):
        if cdn:
            return self.client.get(self.get_spec_url_cdn(spec))
        return self.client.get(self.get_spec_url(spec))

    def delete(self, spec, cdn=False):
        if cdn:
            return self.client.delete(self.get_spec_url_cdn(spec))
        return self.client.delete(self.get_url(spec))

    def test_ok(self):
        if not su_settings.DB_PRESET_ENABLED:
            return

        data = load_apistubs_yaml(su_settings.SPEC_FILES['ministubs'])
        self.post('vpnwn', data)
        response = self.get('vpnwn')

        self.assertEqual(data['paths'], json.loads(response.content)['paths'])
        response = self.delete('vpnwn')
        response = self.get('vpnwn')
        self.assertEqual(response.status_code, 404)
