"""Worker-domain Markdown projection; the async driver is supplied."""
from .wire_support import worker_markdown,lead_markdown

class WorkerProjection:
    def worker_block(self,event):
        """Encode this subquestion's completion or explicit missing-subanswer outcome.

        Ignore private working_context. Failure body is the original error text;
        completed/cut body is the exact worker summary, including line endings.
        """
        if event['artifact'] is None:
            status='missing';body=event['error']
        else:
            status='cut' if event['artifact'].cut else 'complete'
            body=event['artifact'].summary
        return worker_markdown(event['question_id'],event['question'],status,body)
    def lead_block(self,report):
        """Encode supported, unverified and conflicting sections distinctly."""
        return lead_markdown({'supported':report['supported'],'unverified':report['unverified'],'conflicting':report['conflicting']})
