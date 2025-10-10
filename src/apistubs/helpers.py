import os
import yaml

from urllib.parse import (
    urlparse,
    urlunparse,
)
import json
from jinja2 import Environment, BaseLoader

__all__ = (
    'get_path',
    'replace_host',
    'render_params',
    'parse_preset_response',
    'clear_comments',
    'load_apistubs_yaml',
)


def get_path(data, *args):
    attr = data
    for arg in args:
        if attr and arg in attr:
            if not isinstance(attr, dict):
                return None
            attr = attr[arg]
        else:
            return None
    return attr


def replace_host(url, netloc, scheme=None):
    parsed_url = list(urlparse(url.strip()))
    parsed_url[1] = netloc
    if scheme:
        parsed_url[0] = scheme
    return urlunparse(parsed_url)


def render_params(value, request):
    if '{{' not in value or '}}' not in value:
        return value
    context = {}
    context.update(request.GET.dict())
    context.update(request.POST.dict())

    """
    fixed = {}
    for key in context:
        if '.' in key:
            fixed[key.replace('.', '_')] = context[key]
    import sys
    sys.stdout.write(json.dumps(fixed))
    context.update(fixed)
    """

    template = Environment(loader=BaseLoader).from_string(value)
    return template.render(**context)


def parse_preset_response(value, prompt=None):
    requested_status = None
    requested_example = None
    requested_content = None
    requested_headers = None

    if isinstance(value, dict):
        status_aliases = list(value.keys())
        status_alias = None
        if prompt:
            status_alias = prompt.use_alias(status_aliases)
        if status_alias is None:
            status_alias = status_aliases[0]
        payload = value[status_alias]
        if isinstance(status_alias, str):
            status_props = status_alias.split('-')
            requested_status = int(status_props[0])
            if len(status_props) > 1:
                requested_example = status_props[-1]
        else:
            requested_status = status_alias
        if isinstance(payload, dict):
            payload = payload.copy()
            requested_headers = payload.pop('HEADERS', None)
        requested_content = payload
    else:
        try:
            value = int(value)
        except ValueError:
            value = value.split('-')[:2]
            if len(value) == 2:
                status, example = value
                try:
                    example = int(example)
                except ValueError:
                    try:
                        payload = json.loads(example)
                        payload = payload.copy()
                    except:
                        pass
                    else:
                        if isinstance(payload, dict):
                            requested_headers = payload.pop('HEADERS', None)
                        requested_status = int(status)
                        requested_content = payload

                requested_status = int(status)
                requested_example = example
        else:
            requested_status = value

    return requested_status, requested_example, requested_content, requested_headers


def clear_comments(data, dep=0):
    # clear commented nodes ("_ ...")
    if dep == 3:
        return

    if not data or not isinstance(data, dict):
        return

    remove_nodes = []
    for app in data:
        if str(app)[0] == '_':
            remove_nodes.append(app)
        clear_comments(data[app], dep=dep + 1)

    for app in remove_nodes:
        data.pop(app)


__file_cache = {}
__file_cache_timestamp = {}


def load_apistubs_yaml(path):
    modefied = os.path.getctime(path)
    if __file_cache_timestamp.get(path) == modefied and path in __file_cache:
        return __file_cache[path]
    with open(path, 'r', encoding='utf-8') as f:
        if path.endswith('.json'):
            data = json.loads(f.read())
        else:
            data = yaml.safe_load(f)
    data.pop('apistubs', None)
    clear_comments(data)
    __file_cache[path] = data
    __file_cache_timestamp[path] = modefied
    return data
