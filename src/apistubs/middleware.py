import json
import sys

from django.conf import settings as app_settings
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse, JsonResponse

from apistubs import VERSION
from apistubs import settings as su_settings
from apistubs.stubs import get_stub_response
from apistubs.logging import RequestLog

__all__ = (
    'APIStubsMiddleware',
)


class APIStubsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not su_settings.ENABLED:
            return

        if not su_settings.MIDDLEWARE_STUB_ENABLED:
            return

        if request.headers.get('X-Stubs-Mode') == 'skip':
            return

        env = ''
        marker = su_settings.MIDDLEWARE_STUB_COOKIE_MARKER
        if marker is True:
            marker = su_settings.MIDDLEWARE_STUB_COOKIE_MARKER_DEFAULT
        if marker:
            if marker not in request.COOKIES:
                return
            else:
                env = request.COOKIES[marker]
                env = env.strip()
                if env == 'root':
                    env = ''

        specs = [app_settings.PROJECT]
        if su_settings.MIDDLEWARE_SPECS:
            specs = su_settings.MIDDLEWARE_SPECS

        for spec in specs:
            stub_response = get_stub_response(spec, request, request.path, explicit=True, env=env)
            if not stub_response:
                continue

            status, payload, headers = stub_response.status, stub_response.content, stub_response.headers

            RequestLog.add_success(
                service=spec, method=request.method, path=request.path,
                pattern=stub_response.pattern, status=status,
                content=payload, prompt=stub_response.prompt,
                data=request.POST.dict(), params=request.GET.dict(), headers=dict(request.headers),
                response_headers=headers, request=request
            )

            if not isinstance(payload, str):
                payload = json.dumps(payload, indent=4, ensure_ascii=False)

            response = HttpResponse(payload, status=status, content_type='application/json')
            for header in headers:
                response[header] = headers[header]

            request.has_staff_ip = False
            response['X-Stub-Mocked'] = 'on'
            response['X-Stub-Version'] = VERSION

            return response
