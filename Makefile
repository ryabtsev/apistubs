yaml2json:
	python -c 'import yaml; stubs = yaml.safe_load(open("./apistubs/data/specs/ministubs.openapi.yaml").read()); import json; open("./apistubs/data/specs/ministubs.openapi.json", "w").write(json.dumps(stubs, indent=2))'

json2yaml:
	python -c 'import json; stubs = json.loads(open("./apistubs/data/specs/ministubs.json").read()); import yaml; open("./apistubs/data/specs/ministubs.yaml", "w").write(yaml.dump(stubs))'
