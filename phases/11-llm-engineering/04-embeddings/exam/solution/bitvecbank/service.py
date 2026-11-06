"""Given consumers of projected vectors; contracts checked at the card boundary."""
import math
from .metrics import truncate_embedding, norm, binarize

def projection_card(projected):
    """Accept a zero or unit projected vector from the projection producer."""
    length = norm(projected)
    assert length == 0 or math.isclose(length, 1.0, rel_tol=1e-12, abs_tol=1e-12), "projected vectors reach the inspection card at unit length"
    return {"vector": projected, "norm": length, "bits": binarize(projected)}

class VectorService:
    def inspect_projection(self, vector, dimensions):
        projected = truncate_embedding(vector, dimensions)
        return projection_card(projected)
