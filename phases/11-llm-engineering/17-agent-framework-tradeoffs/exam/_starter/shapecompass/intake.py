"""Problem intake, ordered comparison rows and complete batch table formatting."""
from .contracts import Problem,ReportRow,normalized_problem,validate_raw_cases,feature_card,row_text
def decode_problem(raw):
    """Project the normalized JSON descriptor into every Problem field."""
    fields=normalized_problem(raw)
    fields['total_llm_calls']=raw.get('llm_calls')
    return Problem(**fields)
def prepare_cases(raw_cases,recommender):
    """Preserve ordered case identity; recommender is an injected local fixture."""
    rows={}
    for raw in validate_raw_cases(raw_cases):
        problem=decode_problem(raw['problem'])
        card=feature_card(problem)
        row=ReportRow(raw['case_id'],raw['label'],card,recommender(problem))
        rows[row.label]=row
    return tuple(rows.values())
def format_case_table(rows):
    """Return every row, using max(60, longest Python-character label length).

    Prepared rows already contain their recommendation; no policy is run here.
    Empty input returns an empty string. Rows and labels retain their exact order.
    """
    rows=tuple(rows)
    return ''.join(row_text(row,max(60,max(len(other.label) for other in rows)))+'\n' for row in rows)
