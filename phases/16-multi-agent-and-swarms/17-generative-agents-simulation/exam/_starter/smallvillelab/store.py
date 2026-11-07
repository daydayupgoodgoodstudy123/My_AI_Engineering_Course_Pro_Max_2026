"""Domain-owned complete per-agent memory/progress/belief/plan snapshot association."""
from .models import Memory,Progress,Belief,Segment,AgentState,TownSnapshot
from .directory_support import DirectoryDriver
class TownArchive:
    def __init__(self,path):self.driver=DirectoryDriver(path)
    def save(self,snapshot):
        """Save the declared agent order and each independent complete state, including progress when beliefs are empty."""
        raise NotImplementedError
    def load(self):
        """Reopen all declared states in manifest order using their own memory, progress and plan records."""
        raise NotImplementedError
    def close(self):self.driver.close()
