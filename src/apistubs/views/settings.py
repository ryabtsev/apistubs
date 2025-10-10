import json
import yaml
import re

from django.conf import settings as app_settings
from django.http import (
    HttpResponse,
    JsonResponse,
    HttpResponseRedirect,
)
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apistubs.dbpreset.models import Mock
from apistubs.helpers import clear_comments

__all__ = (
    'SettingsView',
    'SpecSettingsView',
)


class SettingsView(View):
    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        operation = request.POST.get('operation')
        if operation:
            env = request.POST.get('env', '')
            if not re.fullmatch(r'[-.\w]+', env):
                return HttpResponse('Invalid env')

            if operation == 'patch':
                data = request.POST.get('data')
                try:
                    preset = yaml.safe_load(data)
                except:
                    return HttpResponse('Invalid yaml')
                clear_comments(preset)

                self.operation_patch(preset, env)
                response = HttpResponseRedirect(request.path.replace('/settings/', f'/{env}/settings/'))
                response.set_cookie('stubs_env', env)
                return response
            elif operation == 'settings':
                return HttpResponseRedirect(request.path.replace('/settings/', f'/{env}/settings/'))
            elif operation == 'prompt':
                return HttpResponseRedirect(request.path.replace('/settings/', f'/{env}/prompt/'))

        return super(SettingsView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        env = kwargs.get('env', '')
        response_format = request.GET.get('format')
        responses = {}
        for response in Mock.objects.order_by('index').filter(env=env).all():
            responses.setdefault(response.spec_name, {})
            responses[response.spec_name][
                '#'.join([response.method, response.pattern])
            ] = response.get_content()

        if response_format == 'json':
            return HttpResponse(json.dumps(responses), content_type='text/json')

        return HttpResponse(yaml.safe_dump(responses, sort_keys=False), content_type='text/plain')

    def post(self, request, *args, **kwargs):
        env = kwargs.get('env', '')
        try:
            preset = json.loads(request.body)
        except json.JSONDecodeError:
            preset = yaml.safe_load(request.body)

        if not preset:
            preset = {}

        preset.pop('apistubs', None)
        clear_comments(preset)

        mocks = []
        index = 0
        for service in preset:
            if service.lower() != service:
                continue

            for pt in preset[service]:
                method, pattern = pt.split('#')
                preset_value = preset[service][pt]

                mocks.append(Mock(
                    index=index,
                    spec_name=service,
                    method=method,
                    pattern=pattern,
                    status=0,
                    content=Mock.prep_content(preset_value),
                    headers={},
                    env=env
                ))
                index += 1

        Mock.objects.filter(env=env).delete()
        Mock.objects.bulk_create(mocks)
        return HttpResponse()
        return JsonResponse(preset)

    def patch(self, request, *args, **kwargs):
        env = kwargs.get('env', '')
        try:
            preset = json.loads(request.body)
        except json.JSONDecodeError:
            preset = yaml.safe_load(request.body)

        clear_comments(preset)
        self.operation_patch(preset, env)
        return HttpResponse()
        return JsonResponse(preset)

    def operation_patch(self, preset, env):
        mocks = []
        index = 0
        for service in preset:
            for pt in preset[service]:
                method, pattern = pt.split('#')
                method = method.lower()
                preset_value = preset[service][pt]

                mocks.append(Mock(
                    index=index,
                    spec_name=service,
                    method=method,
                    pattern=pattern,
                    status=0,
                    content=preset_value,
                    headers={},
                    env=env
                ))
                index += 1

                Mock.objects.filter(
                    spec_name=service,
                    pattern=pattern,
                    method=method,
                    env=env
                ).delete()

        Mock.objects.bulk_create(mocks)
        return JsonResponse(preset)

    def delete(self, request, *args, **kwargs):
        env = kwargs.get('env', '')
        Mock.objects.filter(env=env).delete()
        return HttpResponse()


class SpecSettingsView(View):
    """
    Deprecated
    """
    @csrf_exempt
    def get(self, request, *args, **kwargs):
        spec_name = kwargs.get('spec', app_settings.PROJECT)

        responses = []
        for response in Mock.objects.order_by('id').filter(spec_name=spec_name).all():
            responses.append({
                'method': response.method,
                'pattern': response.pattern,
                'status': response.status,
                'headers': response.headers,
                'content': response.content,
            })
        return JsonResponse({
            'responses': responses,
        })

    @csrf_exempt
    def post(self, request, *args, **kwargs):
        # TODO: validation + documentation
        spec_name = kwargs.get('spec', app_settings.PROJECT)
        responses = json.loads(request.body)['responses']
        mocks = []
        for index, item in enumerate(responses):
            mocks.append(Mock(
                index=index,
                spec_name=spec_name,
                method=item['method'].lower(),
                pattern=item['pattern'],
                status=item['status'],
                content=item.get('content', {}),
                headers=item.get('headers', {}),
            ))

        Mock.objects.filter(spec_name=spec_name).delete()
        Mock.objects.bulk_create(mocks)
        return JsonResponse({
            'responses': responses,
        })

    @csrf_exempt
    def delete(self, request, *args, **kwargs):
        spec_name = kwargs.get('spec', app_settings.PROJECT)
        Mock.objects.filter(spec_name=spec_name).delete()
        return HttpResponse()
