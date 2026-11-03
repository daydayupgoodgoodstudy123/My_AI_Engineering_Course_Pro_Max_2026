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
        if name not in ('notes_create', 'notes_get'):
            return {'ok': False, 'error': 'unknown_tool'}
        key = 'title' if name == 'notes_create' else 'id'
        if not isinstance(args, dict) or set(args) != {key}:
            return {'ok': False, 'error': 'invalid_arguments'}
        v = args[key]
        if name == 'notes_create':
            if not isinstance(v, str) or not 1 <= len(v.strip()) <= 80:
                return {'ok': False, 'error': 'invalid_arguments'}
            note = {'id': self.next_id, 'title': v.strip()}
            self.notes[self.next_id] = note
            self.next_id += 1
        else:
            if type(v) is not int:
                return {'ok': False, 'error': 'invalid_arguments'}
            if v not in self.notes:
                return {'ok': False, 'error': 'not_found'}
            note = self.notes[v]
        return {'ok': True, 'value': note.copy()}

    def list_tools(self):
        return ['notes_create', 'notes_get']

    def search(self, query):
        return [n.copy() for _, n in sorted(self.notes.items()) if query.casefold() in n['title'].casefold()]
