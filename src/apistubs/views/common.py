import json
import re
from urllib.parse import (
    urlsplit,
    urlunsplit,
)
from django.http import (
    HttpResponse,
    Http404,
)
from django.utils import timezone
from django import forms
from django.views import View
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, Http404
from django.conf import settings as app_settings

from apistubs import settings as su_settings
from apistubs.helpers import get_path
from apistubs.spec import spec_point

__all__ = (
    'IndexView',
    'BrowserView',
    'OAuth2RedirectView',
    'SpecView',
)


if su_settings.DB_PRESET_ENABLED:
    from apistubs.dbpreset.models import Mock

class IndexView(TemplateView):
    template_name = 'apistubs/index.html'

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(IndexView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super(TemplateView, self).get_context_data(**kwargs)
        service = kwargs.get('spec', 'ministubs')
        data['service'] = service
        data['spec_url'] = None
        data['STATIC_URL'] = app_settings.STATIC_URL
        return data

    MOCK_MODEL_ENV_PREFIX = 'storage:'
    MOCK_MODEL_METHOD = 'spec'

    def get_env(self, name):
        return self.MOCK_MODEL_ENV_PREFIX + name

    def get_spec(self, name):
        value = Mock.objects.filter(env=self.get_env(name))
        if not value:
            return None, None
        item = value[0]
        return item.content, item

    def save_spec(self, name, value):
        if not value:
            return Mock.objects.filter(env=self.get_env(name)).delete()
        _, item = self.get_spec(name)
        if item:
            item.content = value
            return item.save()
        Mock.objects.create(
            index=-1,
            headers={},
            status=0,
            env=self.get_env(name),
            method=self.MOCK_MODEL_METHOD,
            content=value,
            created_at=timezone.now()
        )

    def post(self, request, *args, **kwargs):
        if not su_settings.DB_PRESET_ENABLED or 'spec' not in kwargs:
            raise Http404
        data = json.loads(request.body)
        self.save_spec(kwargs['spec'], request.body.decode())
        return HttpResponse()

    def delete(self, request, *args, **kwargs):
        if not su_settings.DB_PRESET_ENABLED or 'spec' not in kwargs:
            raise Http404
        self.save_spec(kwargs['spec'], None)
        return HttpResponse()


class BrowserView(TemplateView):
    template_name = 'apistubs/index.html'

    class URLForm(forms.Form):
        url = forms.URLField(required=False)

    def get_context_data(self, **kwargs):
        form = self.URLForm(data=self.request.GET)
        if not form.is_valid():
            raise Http404

        url = form.cleaned_data['url']

        data = super(TemplateView, self).get_context_data(**kwargs)
        data['browser_mode'] = True
        data['STATIC_URL'] = app_settings.STATIC_URL
        data['url'] = url
        return data


class OAuth2RedirectView(TemplateView):
    template_name = 'apistubs/oauth2-redirect.html'


class SpecView(View):
    def get(self, request, *args, **kwargs):
        spec_name = kwargs.get('spec', 'ministubs')
        data, item = self.get_spec(spec_name)
        if not data:
            if spec_name not in su_settings.SPEC_FILES:
                raise Http404
            spec_file = spec_point.get_spec_file(spec_name)
            data = spec_point.get_data(spec_file)

        self.process_data(data, spec_name, *args, **kwargs)
        data = json.dumps(data, indent=4, ensure_ascii=False)

        # TODO: fix images paths
        data = re.sub(re.compile('<figure>.*?</figure>'), '', data)

        response = HttpResponse(data, content_type='application/json')
        response['Access-Control-Allow-Origin'] = '*'
        return response

    MOCK_MODEL_ENV_PREFIX = 'storage:'

    def get_env(self, name):
        return self.MOCK_MODEL_ENV_PREFIX + name

    def get_spec(self, name):
        if not su_settings.DB_PRESET_ENABLED:
            return None, None
        value = Mock.objects.filter(env=self.get_env(name))
        if not value:
            return None, None
        item = value[0]
        data = item.content
        if isinstance(data, str):
            data = json.loads(data)
        return data, item

    def process_data(self, data, spec_name, *args, **kwargs):
        spec_name = kwargs.get('spec', 'ministubs')

        if (
            data['servers'] and
            isinstance(data['servers'], list) and
            isinstance(data['servers'][0], dict) and
            'url' in data['servers'][0] and
            isinstance(data['servers'][0]['url'], str)
        ):
            server_url_parsed = list(urlsplit(data['servers'][0]['url']))
            server_url_parsed[1] = self.request.get_host()
            data['servers'][0] = {
                'url': urlunsplit(server_url_parsed),
            }

        if su_settings.AUTHORIZATION_URL or su_settings.TOKEN_URL:
            oauth_flows = get_path(data, 'components', 'securitySchemes', 'oauth_2_0', 'flows')
            if oauth_flows:
                implicit = get_path(oauth_flows, 'implicit')
                if implicit and su_settings.AUTHORIZATION_URL:
                    implicit['authorizationUrl'] = su_settings.AUTHORIZATION_URL
                authorization_code = get_path(oauth_flows, 'authorizationCode')
                if authorization_code and su_settings.TOKEN_URL:
                    authorization_code['authorizationUrl'] = su_settings.AUTHORIZATION_URL
                    authorization_code['tokenUrl'] = su_settings.TOKEN_URL

        if spec_name == 'ministubs':
            specs = []
            if su_settings.DB_PRESET_ENABLED:
                items = Mock.objects.filter(env__startswith=self.MOCK_MODEL_ENV_PREFIX)
                specs += [item.env[len(self.MOCK_MODEL_ENV_PREFIX):] for item in items]
            specs += su_settings.SPEC_FILES.keys()
            specs.sort()
            data['paths']['/{service}/']['get']['parameters'][0]['description'] = '<b>Specifications:</b><ol>%s</ol>' % (
                ''.join([
                    '<li><a target="_blank" href="%s/">%s</a></li>' % (key, key,)
                    for key in specs
                ])
            )
