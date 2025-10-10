from parse import Parser
from urllib.parse import parse_qs

from apistubs import settings as su_settings
from apistubs.helpers import get_path, replace_host, load_apistubs_yaml

__all__ = (
    'oas_find_path',
    'spec_point',
)


class ExtendedParser(Parser):
    def _handle_field(self, field):
        # handle as path parameter field
        field = field[1:-1]
        path_parameter_field = "{%s:PathParameter}" % field
        return super()._handle_field(path_parameter_field)


class PathParameter:
    name = "PathParameter"
    pattern = r"[^\/]+"

    def __call__(self, text):
        return text


parse_path_parameter = PathParameter()


def search(path_pattern, full_url_pattern) :
    extra_types = {parse_path_parameter.name: parse_path_parameter}
    p = ExtendedParser(path_pattern, extra_types)
    p._expression = '^' + p._expression + '$'
    return p.search(full_url_pattern)


def params_match(request, params):
    if not params or not request:
        return 1

    score = 0
    mack_params = [(key, value[0], ) for key, value in parse_qs(params).items()]
    for key, value in mack_params:
        for km, obj in (
            ('DATA.', request.POST, ),
            ('HEADER.', request.headers, ),
            ('', request.GET, ),
        ):
            if key.startswith(km):
                if obj.get(key[len(km):]) == value:
                    score += 1
                    break
                else:
                    return 0

    return score


def select_path(paths, path, request=None):
    max_path_size = 0
    result = None

    for path_pattern in paths:
        params = path_pattern.split('?')
        pattern = params[0]
        params = params[1] if len(params) > 1 else None

        params_match_score = params_match(request, params)
        if not params_match_score:
            continue

        path_size = len(pattern) + params_match_score
        if path_size > max_path_size and (
            pattern == path or
            search(pattern, path)
        ):
            result = path_pattern
            max_path_size = path_size

    return result


def oas_find_path(spec_name, path):
    spec_file = spec_point.get_spec_file(spec_name)
    spec = spec_point.get_data(spec_file)
    spec_paths = spec.get('paths', {}).keys()
    return select_path(spec_paths, path)


def response_from_spec(request, spec_name, pattern, requested_status, example_number):
    spec_file = spec_point.get_spec_file(spec_name)
    spec = spec_point.get_data(spec_file)
    responses = get_path(spec, 'paths', pattern, request.method.lower(), 'responses')
    if responses:
        for status in sorted(responses.keys()):
            if requested_status and int(status) != requested_status:
                continue

            examples = get_path(responses, status, 'content',  'application/json', 'examples')
            if not examples:
                example = get_path(responses, status, 'content',  'application/json', 'example')
                if example is not None:
                    examples = {'default': {'value': example}}

            if examples:
                headers = {}
                if status == '202':
                    location = get_path(responses, status, 'headers',  'Location', 'schema', 'example')
                    if location:
                        location = replace_host(location, request.get_host(), scheme=request.scheme)
                        headers['Location'] = location

                examples_keys = list(examples.keys())

                if isinstance(example_number, int):
                    if example_number + 1 > len(examples_keys):
                        example_number = 1
                    example = examples[examples_keys[example_number]]
                elif example_number is None:
                    example = list(examples.values())[0]
                else:
                    example = examples.get(example_number, {})

                content = example.get('value', {})
                return status, content, headers


class Spec():
    def __init__(self):
        self.data = {}

    def get_data(self, spec_file):
        if spec_file is None:
            return {}
        return load_apistubs_yaml(spec_file)

    def get_spec_file(self, spec_key):
        spec = su_settings.SPEC_FILES.get(spec_key)
        return spec


spec_point = Spec()
