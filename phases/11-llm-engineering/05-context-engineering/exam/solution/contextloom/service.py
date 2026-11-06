"""Given service wiring; P1 filtering/reporting does not implement placement."""
from .filtering import build_retrieved
from .budget import assemble_priority
from .placement import zigzag_documents
from .models import component_value

class ContextService:
    def preview(self, documents, scores, threshold):
        return build_retrieved(documents, scores, threshold)
    def layout(self, system, query, items, max_tokens, reserve):
        ordered = zigzag_documents(items)
        return assemble_priority(system, query, [(item.component.key, item.component.text) for item in ordered], max_tokens, reserve)

class ContextSession:
    """Given coherent update->full-budget snapshot for completed local updates."""
    def __init__(self, system, query, max_tokens, reserve):
        self.system, self.query = system, query
        self.max_tokens, self.reserve = max_tokens, reserve
        self.components = {}
        self.revision = 0
    def apply(self, component):
        component_value(component)
        old = self.components.get(component.key)
        if old is not None and component.revision <= old.revision:
            raise ValueError("component revision must increase")
        self.components[component.key] = component
        self.revision += 1
        snapshot = assemble_priority(self.system, self.query, [(key, row.text) for key, row in self.components.items()], self.max_tokens, self.reserve)
        return dict(snapshot, revision=self.revision)
