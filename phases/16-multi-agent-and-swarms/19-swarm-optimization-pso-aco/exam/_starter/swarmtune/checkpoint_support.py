"""Complete normal-process binary/metadata member resources, not checkpoint field modeling."""
from pathlib import Path
class CheckpointMembers:
    def __init__(self,path):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
    def replace(self,metadata,data):
        (self.path/'state.bin').write_bytes(data);(self.path/'metadata.json').write_text(metadata,encoding='utf-8')
    def read(self):return(self.path/'metadata.json').read_text(encoding='utf-8'),(self.path/'state.bin').read_bytes()
    def close(self):pass
