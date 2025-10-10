import yaml

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apistubs.logging import RequestLog

__all__ = (
    'LogView',
)


class LogView(View):
    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(LogView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        env = kwargs.get('env', '')
        response_format = request.GET.get('format')
        if response_format == 'json':
            return JsonResponse({
                'log': RequestLog.get(env),
            })
        return HttpResponse(yaml.safe_dump(RequestLog.get(env)), content_type='text/plain')

    @csrf_exempt
    def delete(self, request, *args, **kwargs):
        env = kwargs.get('env', '')
        RequestLog.clear(env)
        return JsonResponse({})
