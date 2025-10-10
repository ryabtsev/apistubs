import json
import yaml

from django.test import TestCase, override_settings
from django.urls import reverse

from apistubs import settings as su_settings
from apistubs import urls

__all__ = (
    'PromptViewTests',
)


PROJECT = 'account'

TEST_PROMPT = 'a1wefg2345234 asdfswdfg345'
TEST_PROMPT_ENV = 'asfgsd sfgsdg sdfhg'

@override_settings(ROOT_URLCONF=urls, PROJECT=PROJECT)
class PromptViewTests(TestCase):
    def get_url(self, env=False, prompt=None):
        if env:
            url = reverse('prompt_env', kwargs={'env': 'test'})
        else:
            url = reverse('prompt')
        return url

    def get_index_url(self, env=False, prompt=None):
        if env:
            url = reverse('prompt_env_index', kwargs={'env': 'test'})
        else:
            url = reverse('prompt_index')
        if prompt:
            url = url + '?q=' + prompt
        return url

    def test_api_ok(self):
        response = self.client.get(self.get_url(env=False))
        self.assertEqual(response.content.decode(), '')

        response = self.client.post(self.get_url(env=False), TEST_PROMPT, content_type='text/plain')
        response = self.client.post(self.get_url(env=True), TEST_PROMPT_ENV, content_type='text/plain')

        response = self.client.get(self.get_url(env=False))
        self.assertEqual(response.content.decode(), TEST_PROMPT)

        response = self.client.get(self.get_url(env=True))
        self.assertEqual(response.content.decode(), TEST_PROMPT_ENV)

        response = self.client.delete(self.get_url(env=False))
        response = self.client.delete(self.get_url(env=True))

        response = self.client.get(self.get_url(env=False))
        self.assertEqual(response.content.decode(), '')

        response = self.client.get(self.get_url(env=True))
        self.assertEqual(response.content.decode(), '')

    def test_ok(self):
        response = self.client.get(self.get_index_url(env=False, prompt=TEST_PROMPT))
        self.assertContains(response, TEST_PROMPT.replace(' ', '\n'))

        response = self.client.get(self.get_index_url(env=True, prompt=TEST_PROMPT_ENV))
        self.assertContains(response, TEST_PROMPT_ENV.replace(' ', '\n'))

        response = self.client.get(self.get_index_url(env=True))
        self.assertContains(response, TEST_PROMPT_ENV.replace(' ', '\n'))

        response = self.client.get(self.get_index_url(env=False))
        self.assertContains(response, TEST_PROMPT.replace(' ', '\n'))
