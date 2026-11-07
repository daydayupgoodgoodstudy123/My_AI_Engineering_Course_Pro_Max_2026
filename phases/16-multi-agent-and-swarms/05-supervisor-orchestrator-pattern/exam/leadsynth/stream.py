"""Worker-domain Markdown projection; the async driver is supplied."""
from .wire_support import worker_markdown,lead_markdown

class WorkerProjection:
    def worker_block(self,event):
        """Encode this subquestion's completion or explicit missing-subanswer outcome.

        Ignore private working_context. Failure body is the original error text;
        completed/cut body is the exact worker summary, including line endings.
        """
        raise NotImplementedError
    def lead_block(self,report):
        """Encode supported, unverified and conflicting sections distinctly."""
        raise NotImplementedError
