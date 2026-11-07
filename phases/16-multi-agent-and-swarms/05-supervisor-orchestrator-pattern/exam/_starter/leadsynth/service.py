"""GIVEN complete sealed-completion desk; no thread/LLM execution."""
from .workers import pack_worker_result,apply_worker_cap,DurationMedian

def format_subanswer(artifact):
    """Consume the narrow result contract for the lead's display."""
    return artifact.summary.strip()

class CompletionDesk:
    def record(self,tasks,completions):
        """Return every artifact and timeout diagnostic in actual completion order.

        tasks have unique question ids; completions contain each supplied task once.
        Runtimes are replayed sealed observations, not elapsed local execution.
        The diagnostic threshold is twice the median INCLUDING this completion.
        It does not kill a thread or decide retrospective model quality.
        """
        roster={task.question_id:task for task in tasks}
        mean_cap=sum(task.token_cap for task in tasks)/len(tasks) if tasks else 0
        median=DurationMedian();receipts=[]
        for question_id,observation in completions:
            task=roster[question_id]
            artifact=pack_worker_result(task,observation)
            display=format_subanswer(artifact)
            artifact=apply_worker_cap(artifact,task.token_cap,mean_cap)
            middle=median.observe_duration(artifact.seconds)
            receipts.append({'artifact':artifact,'display':display,'median':middle,'timeout_threshold':2*middle,'slow':artifact.seconds>2*middle})
        return receipts
