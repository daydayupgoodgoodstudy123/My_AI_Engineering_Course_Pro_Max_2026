"""Complete ordered jury configuration fields; numeric codecs and JSON I/O are supplied."""
from .models import FamilySpec,ReadExposure,JuryConfig
from .codec_support import SnapshotDriver,probability_fields,probability_value,decimal_field,decimal_value
from .support import validate_config
class JuryArchive:
    def __init__(self,path):self._driver=SnapshotDriver(path)
    def save(self,config):
        """Persist every declared family block, exposure and separate exact cost setting in order."""
        raise NotImplementedError
    def load(self):
        """Reopen complete family probabilities/multiplicities and actual declared read/generation configuration."""
        raise NotImplementedError
    def close(self):self._driver.close()
