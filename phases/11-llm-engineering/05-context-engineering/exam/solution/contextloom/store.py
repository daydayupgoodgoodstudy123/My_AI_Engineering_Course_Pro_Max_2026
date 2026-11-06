"""Append-only component revisions with a compact current-state checkpoint."""
from pathlib import Path
import json
from .codec import encode_component, decode_component

class ComponentLog:
    def __init__(self, path):
        self.path = Path(path)
        self.checkpoint_path = self.path.with_suffix(self.path.suffix + ".checkpoint.json")

    def replay(self):
        """Return latest live components in first-seen slot order.

        Read checkpoint before log; covered older revisions are ignored.
        A record equal in revision to the current live value must have the
        same contents, otherwise ValueError. This is state replay, not a
        complete historical revision-integrity audit.
        Updates replace a slot without moving it or duplicating its tokens.
        Preserve supplied codec text, role, revision and provenance exactly.
        """
        state = {}
        encoded = []
        if self.checkpoint_path.exists():
            encoded.extend(json.loads(self.checkpoint_path.read_text(encoding="utf-8"))["components"])
        if self.path.exists():
            encoded.extend(json.loads(line) for line in self.path.read_text(encoding="utf-8").split("\n") if line)
        for value in encoded:
            component = decode_component(value)
            previous = state.get(component.key)
            if previous is not None and component.revision < previous.revision:
                continue
            if previous is not None and component.revision == previous.revision and component != previous:
                raise ValueError("conflicting component revision")
            state[component.key] = component
        return list(state.values())

    def append(self, component):
        """Validate then append one strictly newer revision; stale writes fail.

        One UTF-8 JSON line per component. A new process replays committed
        text; successful append closes its file before returning.
        """
        value = encode_component(component)
        current = {row.key: row for row in self.replay()}
        if component.key in current and component.revision <= current[component.key].revision:
            raise ValueError("component revision must increase")
        with self.path.open("a", encoding="utf-8", newline="\n") as file:
            file.write(json.dumps(value, ensure_ascii=False) + "\n")

    def checkpoint(self):
        """Write ordered live state, then clear covered log entries.

        Replay tolerates old covered lines if a checkpoint/log-clear gap is
        observed. No transaction, fsync/crash durability or partial-line repair
        is promised by this local exercise format.
        """
        state = [encode_component(row) for row in self.replay()]
        self.checkpoint_path.write_text(json.dumps({"components": state}, ensure_ascii=False), encoding="utf-8")
        self.path.write_text("", encoding="utf-8")
