"""Task arrivals, actual worker claims and completed observations as separate domain records."""
class TaskJournal:
    def __init__(self,path):self.path=path
    def append(self,tasks=(),workers=(),events=()):
        """Append complete definitions and ordered observed lifecycle records using supplied framing."""
        raise NotImplementedError
    def load(self):
        """Reopen task/worker definitions and every recorded lifecycle observation in saved order."""
        raise NotImplementedError
    def task_states(self):
        """Replay actual arrival/pull/completion phases; never infer a completion from an arrival."""
        raise NotImplementedError
