"""Original interview practice for 19-capstone-projects/70-task-spec-format.

Local source: phases/19-capstone-projects/70-task-spec-format/docs/en.md (sha256 in SCOPE.json).
Exact narrowed coding contract: coderpad/PROMPT.md.
Python 3.10+, standard library only; no training, network, or API keys.
"""


def validate_config(config, required, optional):
    missing = sorted(set(required) - set(config))
    unknown = sorted(set(config) - set(required) - set(optional))
    return {'missing': missing, 'unknown': unknown, 'valid': not missing and (not unknown)}

def validate_arguments(schema, arguments):
    types = {'string': str, 'integer': int, 'boolean': bool}
    return isinstance(arguments, dict) and set(arguments) == set(schema) and all((kind in types and type(arguments[k]) is types[kind] for k, kind in schema.items()))
