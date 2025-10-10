from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from django import forms

from django.utils.html import escape
from django.core.cache import cache
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import FormView
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
)
from django.utils.safestring import SafeText

from apistubs import settings as su_settings
from apistubs.logging import RequestLog
from apistubs.stubs import YamlSettings, Prompt

if su_settings.DB_PRESET_ENABLED:
    from apistubs.dbpreset.models import Mock

__all__ = (
    'clean_prompt',
    'db_settings',
    'PromptView',
    'PromptAPIView',
)


def clean_prompt(prompt: bytes | str | None) -> List[str]:
    if not prompt:
        return []

    if isinstance(prompt, bytes):
        prompt = prompt.decode('utf-8')

    val = [p.strip() for p in prompt.replace(',', '').replace('\n', ' ').split(' ')]
    val = [p for p in val if p]
    return val


def db_settings(env: str) -> Dict[str, Dict[str, Any]]:
    settings: Dict[str, Dict[str, Any]] = {}
    if not su_settings.DB_PRESET_ENABLED:
        return settings

    for response in Mock.objects.order_by('index').filter(env=env):
        settings.setdefault(response.spec_name, {})
        settings[response.spec_name][
            '#'.join([response.method, response.pattern])
        ] = response.get_content()
    return settings


class PromptForm(forms.Form):
    default_key = 'default'
    special_fields = ['version']

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._initialize_properties(kwargs)
        self.base_fields: Dict[str, forms.Field] = {}
        self._create_prompt_field()
        self._create_choice_fields()
        super(PromptForm, self).__init__(*args, **kwargs)

    def _initialize_properties(self, kwargs: Dict[str, Any]) -> None:
        self.settings = kwargs.pop('settings')
        self.initial_prompt = kwargs.pop('prompt')
        self.prompt_query = kwargs.pop('prompt_query')
        self.default_data: Dict[str, Any] = {}
        self.anchors: List[str] = []

    def _create_prompt_field(self) -> None:
        self.base_fields[self.prompt_query] = forms.CharField(
            label='', widget=forms.Textarea, required=False, initial='\n'.join(self.initial_prompt)
        )

    def _create_choice_fields(self) -> None:
        prompt_index = 0
        for service, endpoints in self.settings.items():
            if service != service.lower() or service in self.special_fields:
                continue

            for index, path in enumerate(endpoints):
                if not isinstance(endpoints[path], dict):
                    continue

                prompts = self._get_prompts(endpoints[path])
                if len(prompts) < 2:
                    continue

                prompt_index += 1
                self._create_choice_field(service, path, index, prompt_index, prompts)

    def _get_prompts(self, endpoint_prompts: Dict[str, Any]) -> List[Tuple[str, str, str]]:
        prompts = []
        for prompt, payload in endpoint_prompts.items():
            parts = '{0}-{1}'.format(prompt, self.default_key).split('-', 2)
            prompts.append((
                parts[1],
                parts[0],
                json.dumps(payload, indent=2),
            ))
        return prompts

    def _create_choice_field(self, service: str, path: str, index: int, prompt_index: int, prompts: List[Tuple[str, str, str]]) -> None:
        field_name = f'{service}_{index}'
        initial = [p[0] for p in prompts if p[0] in self.initial_prompt]
        anchor = f'{service}-{path.replace("#", "")}'
        self.anchors.append(anchor)

        self.base_fields[field_name] = forms.ChoiceField(
            label=SafeText(
                f'<a href="#{anchor}" name="{anchor}">'
                f'{prompt_index}. [{service}] {path}</a>'
            ),
            label_suffix='',
            choices=[
                (p, SafeText(f'<span title=\"[{status}]\n{escape(payload)}\">{p}</span>'))
                for p, status, payload in prompts
            ],
            initial=initial[0] if initial else prompts[0][0],
            widget=forms.RadioSelect
        )
        self.default_data[field_name] = prompts[0][0]

    def clean_q(self) -> List[str]:
        return clean_prompt(self.cleaned_data[self.prompt_query])


class PromptView(FormView):
    template_name = 'apistubs/prompt.html'
    form_class = PromptForm
    cookie_name = 'STUBS_PROMPT'
    prompt_query = 'q'

    @csrf_exempt
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        env = kwargs.get('env', '')
        self.db_settings = db_settings(env)
        return super(PromptView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        env = kwargs.get('env', '')
        response = super().get(request, *args, **kwargs)
        prompt = self.request.GET.get(self.prompt_query)
        if prompt is not None:
            response.set_cookie(self.cookie_name + env, prompt)
            if self.db_settings:
                cache.set('PROMPT' + env, prompt, timeout=60 * 60 * 24 * 30)
            else:
                cache.delete('PROMPT' + env)
        return response

    def form_valid(self, form):
        prompt = form.cleaned_data[self.prompt_query]
        if prompt == form.initial_prompt:
            prompt = [
                str(form.cleaned_data[key]) for key in form.cleaned_data
                if key != self.prompt_query and form.cleaned_data[key] != form.default_data[key]
            ]
        return HttpResponseRedirect('?%s=%s' % (self.prompt_query, '+'.join(prompt), ))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        env = self.kwargs.get('env', '')
        kwargs['prompt'] = self._get_prompt(env)
        kwargs['prompt_query'] = self.prompt_query
        kwargs['settings'] = self._get_settings(env)
        return kwargs

    def _get_prompt(self, env):
        prompt = self.request.GET.get(self.prompt_query)
        if prompt is None:
            prompt = self.request.COOKIES.get(self.cookie_name + env, '')
            if self.db_settings:
                prompt = cache.get('PROMPT' + env, prompt)
        return clean_prompt(prompt)

    def _get_settings(self, env):
        if self.db_settings:
            return self.db_settings

        stubs_configs = su_settings.STUBS_CONFIG
        if not isinstance(stubs_configs, list):
            stubs_configs = [stubs_configs]
        stubs_configs = stubs_configs.copy()
        stubs_configs.reverse()
        settings = {}
        for stubs_config in stubs_configs:
            data_all = YamlSettings(None, path=stubs_config).data_all
            if not isinstance(data_all, dict):
                continue
            for service in data_all:
                if not isinstance(data_all[service], dict):
                    continue
                settings.setdefault(service, {})
                settings[service].update(data_all[service])
        return settings

    def get_context_data(self, **kwargs):
        env = self.kwargs.get('env', '')
        data = super(PromptView, self).get_context_data(**kwargs)
        if self.db_settings:
            data['yaml_path'] = 'from DB'
        else:
            data['yaml_path'] = 'from FILE'

        last_requests = []
        for item in RequestLog.get(env):
            if item['result'] == 'success':
                anchor = '%s-%s%s' % (item['service'], item['request']['method'], item.get('pattern', item['request']['path']),)
                name = '[%s] %s#%s' % (item['service'], item['request']['method'], item.get('pattern', item['request']['path']),)
                if anchor in data['form'].anchors:
                    last_request = (anchor, name, )
                    if last_request not in last_requests:
                        last_requests.append(last_request)

        data['env'] = env
        data['last_requests'] = last_requests
        return data


class PromptAPIView(View):
    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        return super(PromptAPIView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        env = self.kwargs.get('env', '')
        return HttpResponse(Prompt.get_value(env) or '')

    def post(self, request, *args, **kwargs):
        env = self.kwargs.get('env', '')
        value = ' '.join(clean_prompt(request.body or ''))
        Prompt.set_value(env, value)
        return HttpResponse('')

    def delete(self, request, *args, **kwargs):
        env = self.kwargs.get('env', '')
        Prompt.delete_value(env)
        return HttpResponse('')
