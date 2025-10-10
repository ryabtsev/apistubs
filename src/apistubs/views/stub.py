import json
import sys

from django.views import View
from django.http import HttpResponse, HttpResponseNotFound
from django.conf import settings as app_settings
from django.views.decorators.csrf import csrf_exempt

from apistubs import VERSION
from apistubs.stubs import get_stub_response
from apistubs.helpers import render_params
from apistubs.logging import RequestLog

__all__ = (
    'StubView',
    'IndexStubView',
)


class BaseStubViewMixin:
    base_path = 'stub/'

    def process(self, request, *args, **kwargs):
        spec_name = kwargs.get('spec', app_settings.PROJECT)
        env = kwargs.get('env', '')
        if self.base_path:
            path = request.path[request.path.find(self.base_path) + len(self.base_path) - 1:]
        else:
            path = request.path

        stub_response = get_stub_response(spec_name, request, path, env=env)
        if not stub_response:
            RequestLog.add_not_specified(
                service=spec_name, method=request.method, path=path,
                data=request.POST.dict(), params=request.GET.dict(), headers=dict(request.headers),
                env=env, request=request
            )
            return HttpResponseNotFound(json.dumps({'error': 'not_secified'}, indent=4, ensure_ascii=False))

        status, payload, headers = stub_response.status, stub_response.content, stub_response.headers

        RequestLog.add_success(
            service=spec_name, method=request.method, path=path,
            pattern=stub_response.pattern, status=status,
            content=payload, prompt=stub_response.prompt,
            data=request.POST.dict(), params=request.GET.dict(), headers=dict(request.headers),
            response_headers=headers, env=env, request=request
        )

        if not isinstance(payload, str):
            payload = json.dumps(payload, indent=4, ensure_ascii=False)

        response = HttpResponse(payload, status=status, content_type='application/json')
        for key in headers:
            header = str(headers[key]).strip()
            header = render_params(header, request)
            response[key] = header

        response['X-Stub-Mocked'] = 'on'
        response['X-Stub-Version'] = VERSION

        if spec_name:
            response['X-Stub-Service'] = spec_name
        return response


class StubView(BaseStubViewMixin, View):
    base_path = 'stub/'

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return self.process(request, *args, **kwargs)


class IndexStubView(BaseStubViewMixin, View):
    base_path = None

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return self.process(request, *args, **kwargs)
