"""Per-receipt public domain projection; classification and async driver are supplied."""
from .wire_support import receipt_kind
class ReceiptProjection:
    def payload(self,receipt):
        """Project each receipt's own identity and typed domain fields without inventing tool output."""
        raise NotImplementedError
