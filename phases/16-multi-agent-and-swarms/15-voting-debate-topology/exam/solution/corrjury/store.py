"""Complete ordered jury configuration fields; numeric codecs and JSON I/O are supplied."""
from .models import FamilySpec,ReadExposure,JuryConfig
from .codec_support import SnapshotDriver,probability_fields,probability_value,decimal_field,decimal_value
from .support import validate_config
class JuryArchive:
    def __init__(self,path):self._driver=SnapshotDriver(path)
    def save(self,config):
        """Persist every declared family block, exposure and separate exact cost setting in order."""
        validate_config(config)
        document={'uid':config.uid,'families':[{'uid':f.uid,'probability':probability_fields(f.probability),'seats':f.seats,'generation_tokens':f.generation_tokens}for f in config.families],'reads':[{'uid':e.uid,'reader':e.reader,'sender':e.sender,'tokens':e.tokens}for e in config.reads],'generation_rate':decimal_field(config.generation_rate),'read_rate':decimal_field(config.read_rate)}
        self._driver.save(document)
    def load(self):
        """Reopen complete family probabilities/multiplicities and actual declared read/generation configuration."""
        d=self._driver.load()
        families=tuple(FamilySpec(f['uid'],probability_value(f['probability']),f['seats'],f['generation_tokens'])for f in d['families'])
        reads=tuple(ReadExposure(e['uid'],e['reader'],e['sender'],e['tokens'])for e in d['reads'])
        return validate_config(JuryConfig(d['uid'],families,reads,decimal_value(d['generation_rate']),decimal_value(d['read_rate'])))
    def close(self):self._driver.close()
