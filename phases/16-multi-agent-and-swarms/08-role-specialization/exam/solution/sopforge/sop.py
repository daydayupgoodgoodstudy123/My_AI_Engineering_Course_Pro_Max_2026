"""Nested SOP role I/O ownership and declared-output audit, not a role/tool selector."""
from .sop_support import SOPCatalog,ROLE_INPUTS,ROLE_OUTPUT

def audit_sop(root,records):
    """Audit typed producer/consumer ports at every stage and expose only declared output.

    Complete catalog resolution and bundle revision/link validation are supplied.
    Candidate work is required role inputs, real output producers/kinds and
    export boundaries at every nested stage. Full record handles are explicit.
    """
    catalog=SOPCatalog(root,records)
    def visit(stage,path):
        issues=[];inputs=dict(stage.inputs);outputs=dict(stage.outputs)
        for port in inputs:
            if port not in ROLE_INPUTS[stage.role]:issues.append((path,'unexpected-input',port))
        for port,(producer,kind) in ROLE_INPUTS[stage.role].items():
            if port not in inputs:issues.append((path,'missing-input',port));continue
            record=catalog.record(inputs[port])
            if record.producer!=producer or record.kind!=kind or catalog.payload_kind(record)!=kind:issues.append((path,'input-contract',port))
        output_port,output_kind=ROLE_OUTPUT[stage.role]
        if output_port not in outputs:issues.append((path,'missing-output',output_port))
        for port,handle in stage.outputs:
            record=catalog.record(handle)
            if port!=output_port or record.producer!=stage.role or record.kind!=output_kind or catalog.payload_kind(record)!=output_kind:issues.append((path,'output-contract',port))
            for problem in catalog.payload_issues(record):issues.append((path,problem,port))
        visible=[]
        for port in stage.exposes:
            if port not in outputs:issues.append((path,'unproduced-export',port));continue
            record=catalog.record(outputs[port])
            if port==output_port and record.producer==stage.role and record.kind==output_kind and catalog.payload_kind(record)==output_kind:visible.append((port,record.handle))
        for problem,port in catalog.stage_link_issues(stage):issues.append((path,problem,port))
        children=tuple(visit(child,catalog.child_path(path,child))for child in stage.children)
        return {'path':path,'role':stage.role,'visible_outputs':tuple(visible),'issues':tuple(issues),'children':children}
    return visit(root,(root.name,))
