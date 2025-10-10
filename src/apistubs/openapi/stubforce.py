
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.http.response import HttpResponse

from apistubs.views.stub import BaseStubViewMixin
from apistubs.openapi.middleware import CheckOpenAPIMiddleware, OpenAPIValidationError

__all__ = (
    'StubForceView',
)


class StubForceView(BaseStubViewMixin, View):
    base_path = 'stubforce/'

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        middleware = CheckOpenAPIMiddleware(
            get_response=self.process,
            spec_from_path=True,
            explicit=True,
            base_path=self.base_path
        )
        try:
            return middleware(request, *args, **kwargs)
        except OpenAPIValidationError as e:
            return HttpResponse(e)
