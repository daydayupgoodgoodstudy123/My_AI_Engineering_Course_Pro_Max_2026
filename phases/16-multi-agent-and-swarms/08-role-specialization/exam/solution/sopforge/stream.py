"""Domain JUnit case evidence from the completed deterministic verifier."""
from .models import CaseEntry
from .trusted import outcome_kind
class SOPProjection:
    def case_entries(self,bundle):
        """Project every executed verifier case; critic prose cannot manufacture a case result.

        Use the supplied classification and XML writer. Success has no issue
        child; value mismatch retains expected/got and exceptions retain type
        and original message, including an empty message. No execution here.
        """
        if not bundle.verifier.executed:return ()
        result=[]
        for case in bundle.verifier.cases:
            kind=outcome_kind(case);body='';message=''
            if kind=='failure':message=f'expected {case.expected!r}, got {case.got!r}';body=f'args={case.args!r}'
            elif kind=='error':message=case.error_type+': '+case.error_message;body=f'args={case.args!r}'
            result.append(CaseEntry(bundle.spec.spec_id+'@'+str(bundle.spec.revision)+':'+bundle.spec.task_name,case.case_id,kind,message,body))
        return tuple(result)
