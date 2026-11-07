"""Synchronous domain projection of one complete sealed numeric round."""
from .wire_support import scalar_text
class RoundProjection:
    def rows(self,report):
        """Emit agent rows and one diagnostics row from this same sealed vector.

        All rows share that vector's agreement/truth error. Keep initial round0,
        actual per-agent answer/confidence and independent absent truth. The
        supplied driver owns async pulling/publication/closure and CSV quoting.
        """
        raise NotImplementedError
