import os
from http import HTTPStatus
from typing import Callable
from urllib.parse import urlparse, urlsplit, urlunsplit

from django.conf import settings
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.utils.http import urlencode
from openapi_core import OpenAPI, Spec
from openapi_core.contrib.django import \
    DjangoOpenAPIRequest as BaseDjangoOpenAPIRequest
from openapi_core.contrib.django.handlers import (
    DjangoOpenAPIErrorsHandler, DjangoOpenAPIValidRequestHandler)
from openapi_core.contrib.django.integrations import DjangoIntegration
from openapi_core.datatypes import RequestParameters
from openapi_core.deserializing.media_types.util import data_form_loads
from openapi_core.templating.paths.exceptions import (OperationNotFound,
                                                      PathNotFound,
                                                      ServerNotFound)
from openapi_core.templating.paths.finders import APICallPathFinder
from teamcity.messages import TeamcityServiceMessages
from werkzeug.datastructures import Headers, ImmutableMultiDict

SPEC_FILES = {}
CHECK_OPENAPI_SPEC = getattr(
    settings, 'CHECK_OPENAPI_SPEC',
    os.path.join(settings.PROJECT_ROOT, 'docs', 'oas', 'api.json'),
)
CHECK_OPENAPI_PATHS = getattr(settings, 'CHECK_OPENAPI_PATHS', None)
EXCLUDE_OPENAPI_PATHS = getattr(settings, 'EXCLUDE_OPENAPI_PATHS', None)
SKIP_REQUEST = getattr(
    settings, 'CHECK_OPENAPI_SKIP_VALIDATE_REQUEST_STATUSES', [
        HTTPStatus.FORBIDDEN,
        HTTPStatus.BAD_REQUEST,
    ]
)
SKIP_RESPONSE = getattr(
    settings, 'CHECK_OPENAPI_SKIP_VALIDATE_RESPONSE_STATUSES', [
        HTTPStatus.FORBIDDEN,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.NOT_FOUND,
        HTTPStatus.GONE,
        HTTPStatus.NOT_IMPLEMENTED,
        HTTPStatus.METHOD_NOT_ALLOWED,
    ]
)
BASE_HEADERS = {
    'User-Agent': 'Chrome/51.0.2704.103 Safari/537.36',
    'Referer': 'https://django.test/',
    'Authorization': 'Authorization',
    'X-CSRFToken': 'X-CSRFToken',
    'Accept-Language': 'en',
    'Cookie': '; '.join('='.join(i) for i in {
    }.items()),
}

__openapi_cache = {}

def get_finder(path):
    if path not in __openapi_cache:
        spec = Spec.from_file_path(path)
        finder = APICallPathFinder(
            spec, base_url=spec['servers'][0]['url']
        )
        openapi = OpenAPI(finder.spec)
        __openapi_cache[path] = finder, openapi
    return __openapi_cache[path]


messages = TeamcityServiceMessages()


class OpenAPIValidationError(Exception):
    pass


class DjangoOpenAPIRequest(BaseDjangoOpenAPIRequest):
    def __init__(self, request):
        self.request = request
        self.parameters = RequestParameters(
            path=self.request.openapi_path.path_result.variables,
            query=ImmutableMultiDict(self.request.GET),
            header=Headers(self.get_headers(request)),
            cookie=ImmutableMultiDict(dict(self.request.COOKIES)),
        )

        content = self.request.openapi_path.operation.get('requestBody', {}).get('content', {})
        self.request_pattern = urlparse(request.base_url).path + request.openapi_pattern
        self.request_mimetype = list(content.keys())[0] if content else None
        self.request_body = request._openapi_request_body
        self.base_url = request.base_url

    def get_headers(self, request):
        headers = {}
        headers.update(BASE_HEADERS)
        headers.update(dict(request.headers.items()))
        if headers.get('Content-Type', '').startswith('multipart/form-data'):
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        headers.pop('Content-Length', None)
        return headers

    @property
    def path_pattern(self) -> str:
        return self.request_pattern

    @property
    def host_url(self) -> str:
        return self.base_url

    @property
    def body(self):
        return self.request_body

    @property
    def content_type(self) -> str:
        if self.request_mimetype:
            return self.request_mimetype
        if self.request.content_type:
            return self.request.content_type.split(';')[0]
        return ''


class CheckOpenAPIMiddleware(DjangoIntegration):
    request_cls = DjangoOpenAPIRequest
    valid_request_handler_cls = DjangoOpenAPIValidRequestHandler
    errors_handler = DjangoOpenAPIErrorsHandler()

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse], spec_from_path=False, explicit=False, base_path=''):
        self.get_response = get_response
        self.spec_from_path = spec_from_path
        self.explicit = explicit
        self.base_path = base_path
        if spec_from_path:
            openapi_finder = None
            openapi = None
        else:
            openapi_finder, openapi = get_finder(CHECK_OPENAPI_SPEC)
        self.openapi_finder = openapi_finder
        super().__init__(openapi)

    def __call__(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if self.spec_from_path:
            spec_name = kwargs['spec']
            spec = SPEC_FILES.get(spec_name)
            if not spec:
                return HttpResponse('{}',  status=522)
            self.openapi_finder, self.openapi = get_finder(spec)

        try:
            path, *parts = urlsplit(request.path)[2:]
            path = path[path.index(self.base_path) + len(self.base_path):]
            url = urlunsplit(urlsplit(self.openapi_finder.base_url)[:2] + (path, ) + tuple(parts))
            openapi_path = self.openapi_finder.find(request.method.lower(), url)
        except (
            PathNotFound,
            OperationNotFound,
            ServerNotFound,  # TODO: investigate
        ):
            if self.explicit:
                return HttpResponse('{}',  status=522)
            return self.get_response(request, *args, **kwargs)
        else:
            request.base_url = self.openapi_finder.base_url
            request.openapi_path = openapi_path
            request.openapi_pattern = str(request.openapi_path.operation).split('#')[1]

            if CHECK_OPENAPI_PATHS is not None and request.openapi_pattern not in CHECK_OPENAPI_PATHS:
                return self.get_response(request, *args, **kwargs)

            if EXCLUDE_OPENAPI_PATHS is not None and request.openapi_pattern in EXCLUDE_OPENAPI_PATHS:
                return self.get_response(request, *args, **kwargs)

            content_type = request.META.get('CONTENT_TYPE')
            if content_type and content_type.startswith('multipart/form-data'):
                openapi_request_body = data_form_loads(request.body, boundary='BoUnDaRyStRiNg')
                openapi_request_body = urlencode(openapi_request_body).encode()
            else:
                openapi_request_body = request.body.decode('utf-8').encode()

            request._openapi_request_body = openapi_request_body

        response = self.get_response(request, *args, **kwargs)

        errors = []

        if response.status_code not in SKIP_REQUEST:
            request_unmarshal_result = self.unmarshal_request(request)
            if request_unmarshal_result.errors:
                errors.extend(request_unmarshal_result.errors)

        if (
            response.status_code not in SKIP_REQUEST and
            response.status_code not in SKIP_RESPONSE and
            response.status_code < 500
        ):
            response_unmarshal_result = self.unmarshal_response(request, response)
            if response_unmarshal_result.errors:
                errors.extend(response_unmarshal_result.errors)

        if errors:
            details = self.report(request, errors)
            if os.environ.get('TEAMCITY_VERSION'):
                self.report_teamcity(request, details)
            raise OpenAPIValidationError(details)

        return response

    def report(self,request, errors):
        errors = self.format_errors(errors)
        data = []
        data.append('[%s] %s' % (request.method, request.openapi_pattern,))

        for error in errors:
            data.append(error['title'])

        details = '\n'.join(data)
        return details

    def report_teamcity(self, request, details):
        messages.testStarted(request.openapi_pattern)
        messages.testFailed(request.openapi_pattern, '', details)
        messages.testFinished(request.openapi_pattern)

    def format_errors(self, errors):
        def format_openapi_error(error):
            if error.__cause__ is not None:
                error = error.__cause__
            return {
                'title': str(error),
                'type': str(type(error)),
            }
        data_errors = [format_openapi_error(err) for err in errors]
        return data_errors
