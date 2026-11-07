"""Structural critic and deterministic verifier for already-complete specifications."""
import ast
from .models import CriticReport
from .trusted import compile_trusted_artifact,callable_lookup,run_case,make_verifier_report,ExecutionSession

def critic(spec,artifact):
    """Review declared module-level function structure without executing tests.

    This finite structural critic requires a named def with a return statement;
    literal/comment text is not a definition. Approval does not prove behavior.
    """
    try:tree=ast.parse(artifact.code)
    except SyntaxError:notes=('invalid Python syntax',)
    else:
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==spec.task_name]
        notes=() if functions and any(isinstance(n,ast.Return) for n in ast.walk(functions[0])) else ('missing declared function with return',)
    return CriticReport(spec.spec_id,spec.revision,artifact.artifact_id,artifact.revision,not notes,notes)

def verifier(spec,artifact):
    """Execute one trusted artifact in one fresh namespace, then all declared cases.

    Bind the spec's actual function, retain every success/failure/exception and
    never reuse another artifact's namespace. Compile once per verification.
    """
    session=ExecutionSession(artifact)
    program=compile_trusted_artifact(artifact);fn=callable_lookup(program,spec.task_name,session)
    results=[]
    for case in spec.cases:
        item=run_case(fn,case);results.append(item)
    return make_verifier_report(spec,artifact,results)
