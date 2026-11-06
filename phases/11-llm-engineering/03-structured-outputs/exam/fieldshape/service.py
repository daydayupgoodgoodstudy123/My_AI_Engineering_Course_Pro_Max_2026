"""Given service wiring. Validation is a consumer of generated schemas."""
from .flat import model_to_schema
from .compiler import compile_model
from .validation import validate_schema

class ExtractionService:
    def __init__(self):
        self.schemas = {}
    def validate_flat(self, name, fields, data):
        schema = model_to_schema(name, fields)
        return validate_schema(data, schema)
    def register_model(self, model):
        schema = compile_model(model)
        self.schemas[model.name] = schema
        return schema
    def validate_model(self, name, data):
        return validate_schema(data, self.schemas[name])
