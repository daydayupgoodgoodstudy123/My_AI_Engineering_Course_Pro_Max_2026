"""Domain JUnit case evidence from the completed deterministic verifier."""
from .models import CaseEntry
from .trusted import outcome_kind
class SOPProjection:
    def case_entries(self,bundle):
        """Project every executed verifier case; critic prose cannot manufacture a case result.

        Use the supplied classification and XML writer. Success has no issue
        child; value mismatch retains expected/got and exceptions retain type
        and original message, including an empty message. No execution here.
        """
        raise NotImplementedError
