"""Public domain decision evidence; private selector prompts do not belong on the wire."""
from .logfmt_support import delta_text
class DecisionProjection:
    def payload(self,observation):
        """Project each actual classified outcome's own fields without inventing a committed speaker."""
        raise NotImplementedError
