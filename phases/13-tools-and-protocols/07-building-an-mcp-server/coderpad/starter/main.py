"""Original Phase 13 / Lesson 07 CoderPad practice.

Lesson source: 07-building-an-mcp-server/docs/en.md (local course snapshot).
The precise exercise contract is defined in coderpad/PROMPT.md.
Python 3.10+, stdlib only, no network or API keys.
"""
class NotesServer:

    def __init__(self):
        self.notes = {}
        self.next_id = 1

    def call(self, name, args):
        raise NotImplementedError("TODO 1: NotesServer.call; see PROMPT.md")

    def list_tools(self):
        raise NotImplementedError("TODO 2: NotesServer.list_tools; see PROMPT.md")

    def search(self, query):
        raise NotImplementedError("TODO 3: NotesServer.search; see PROMPT.md")
