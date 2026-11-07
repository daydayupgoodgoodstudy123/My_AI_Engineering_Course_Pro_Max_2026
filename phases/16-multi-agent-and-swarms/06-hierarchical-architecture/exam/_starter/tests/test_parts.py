"""Five sequential 60-minute tasks for a finite offline hierarchy audit.

Part 1: repair typed branch intake, original-question canary and structural fold.
Part 2: persist an ordered ZIP dossier through explicit logical member links.
Part 3: compose obligation mappings, locate drift and compare the canary.
Part 4: project completed provenance events into domain TSV rows.
Part 5: explain typed states and shared citation occurrence paths.
"""
import asyncio,csv,io,json,time
from dataclasses import replace
import pytest
from driftorg.fixture import dossier_fixture,observations,canary_record,inspection_fixture,QUESTION

@pytest.mark.skip('Part 1')
def test_typed_hierarchy_inspection():
    """Typed availability and epistemic evidence remain distinct in complete reports."""
    from driftorg.service import HierarchyDesk
    from driftorg.models import Status
    d=dossier_fixture();desk=HierarchyDesk()
    report=desk.inspect(QUESTION,('absent','eng','empty'),{'eng':('fe','be'),'empty':()},observations(d),d.nodes,d.root_id,canary_record)
    assert tuple(row['availability'] for row in report['branches'])==('missing','verified','unknown'), 'branch availability distinguishes missing, present evidence and empty managers'
    assert report['leaves']==tuple(d.leaves.values()), 'workers retain their declared epistemic evidence and original fields'
    assert report['leaves'][-1].status is Status.UNKNOWN, 'unknown worker evidence remains unknown'
    assert report['canary_question']==QUESTION and report['canary']==canary_record(QUESTION), 'the canary sees the unchanged original question'
    assert report['structure'][-1]=={'node_id':'root','leaf_ids':('be','fe','law'),'citation_ids':('cite/legal','cite/shared','cite/ui'),'leaf_count':3,'citation_count':3}, 'shared citations represent unique structural provenance without extra executions'
    args,expected=inspection_fixture()
    started=time.perf_counter()
    complete=desk.inspect(*args)
    assert complete==expected, 'every manager retains complete leaf, citation, branch and canary report fields'
    elapsed=time.perf_counter()-started
    assert elapsed<0.085, 'complete hierarchy structural reports remain responsive'

@pytest.mark.skip('Part 2')
def test_zip_dossier_links(tmp_path):
    """Archive manifest order and member references own the restored dossier."""
    from driftorg.dossier import save_dossier,load_dossier
    from driftorg.archive_support import Archive,encode_json,decode_json,encode_leaf,encode_node
    d=dossier_fixture();path=tmp_path/'hierarchy.zip';save_dossier(path,d)
    assert load_dossier(path)==d, 'reopening restores every task, typed leaf and summary reference'
    with Archive(path,'r') as archive:manifest=decode_json(archive.get('manifest.json'))
    assert tuple(x[0] for x in manifest['leaves'])==tuple(d.leaves) and tuple(x[0] for x in manifest['nodes'])==tuple(d.nodes), 'manifest preserves declared logical order'
    opaque=tmp_path/'opaque.zip'
    links=[['law','evidence/7'],['fe','evidence/2'],['be','evidence/9']]
    node_links=[[ident,'summaries/'+str(20-i)] for i,ident in enumerate(reversed(d.nodes))]
    with Archive(opaque,'w') as archive:
        for ident,member in reversed(links):archive.put(member,encode_leaf(d.leaves[ident]))
        for ident,member in reversed(node_links):archive.put(member,encode_node(d.nodes[ident]))
        archive.put('source-task',encode_json({'question':d.original_question,'obligations':d.obligations,'root_id':d.root_id}))
        archive.put('manifest.json',encode_json({'task_member':'source-task','leaves':links,'nodes':node_links}))
    restored=load_dossier(opaque)
    assert tuple(restored.leaves)==('law','fe','be') and tuple(restored.nodes)==tuple(reversed(d.nodes)), 'logical order follows manifest links independently of archive insertion and member names'
    assert restored.nodes['eng'].leaf_ids==('fe','be') and restored.nodes['review'].leaf_ids==('fe',) and len(restored.leaves)==3, 'shared leaf references remain links to one sealed evidence record'
    assert restored.leaves['law']==d.leaves['law'] and restored.original_question==QUESTION, 'the supplied typed codec retains complete local evidence'
    with Archive(tmp_path/'bad-id.zip','w') as archive:
        archive.put('one',encode_leaf(d.leaves['fe']));archive.put('task',encode_json({'question':QUESTION,'obligations':[],'root_id':'root'}));archive.put('manifest.json',encode_json({'task_member':'task','leaves':[['not-fe','one']],'nodes':[]}))
    with pytest.raises(ValueError,match='leaf logical id mismatch'):load_dossier(tmp_path/'bad-id.zip')
    with Archive(tmp_path/'bad-ref.zip','w') as archive:
        archive.put('one',encode_node(d.nodes['eng']));archive.put('task',encode_json({'question':QUESTION,'obligations':[],'root_id':'eng'}));archive.put('manifest.json',encode_json({'task_member':'task','leaves':[],'nodes':[['eng','one']]}))
    with pytest.raises(ValueError,match='unknown leaf reference'):load_dossier(tmp_path/'bad-ref.zip')

@pytest.mark.skip('Part 3')
def test_obligation_drift_audit():
    """Semantic obligations follow declared bindings, not structural membership alone."""
    from driftorg.mapping import compose_obligation_mappings,first_divergence_path,audit_decomposition
    from driftorg.models import Status
    d=dossier_fixture();mapped=compose_obligation_mappings(d)
    assert tuple(e['leaf_id'] for e in mapped['build']['evidence'])==('fe','be','fe'), 'local bindings retain every original obligation evidence route'
    assert mapped['contract']['evidence']==[{'leaf_id':'law','path':('root','legal','law'),'state':'unknown'}], 'local obligation identifiers are composed through the manager edge'
    audit=audit_decomposition(d,canary_record(QUESTION))
    assert tuple((r['obligation'],r['hierarchy_state'],r['result']) for r in audit['rows'])==(('build','verified','verified'),('contract','unknown','unknown')), 'complete semantic rows distinguish known and unknown answers'
    wrong_nodes=dict(d.nodes);wrong_nodes['legal']=replace(d.nodes['legal'],department='finance')
    wrong=replace(d,nodes=wrong_nodes);wrong_audit=audit_decomposition(wrong,canary_record(QUESTION))
    assert wrong_audit['rows'][1]['first_divergence']=={'path':('root','legal'),'reason':'wrong-branch'} and wrong_audit['rows'][1]['evidence']==[], 'a finance branch cannot discharge a legal obligation'
    dropped=dict(d.nodes);dropped['root']=replace(d.nodes['root'],bindings=tuple(b for b in d.nodes['root'].bindings if b[0]!='contract'))
    assert audit_decomposition(replace(d,nodes=dropped),canary_record(QUESTION))['rows'][1]['first_divergence']=={'path':('root',),'reason':'unmapped'}, 'missing decomposition is attributed to its first unsupported manager'
    unsupported=dict(d.nodes);unsupported['root']=replace(d.nodes['root'],bindings=tuple((a,b,'invented' if a=='contract' else c) for a,b,c in d.nodes['root'].bindings))
    assert audit_decomposition(replace(d,nodes=unsupported),canary_record(QUESTION))['rows'][1]['hierarchy_state']=='unsupported-mapping', 'undeclared child obligations cannot inherit structural coverage'
    synthetic={'x':{'issues':[{'path':('r','a','b'),'reason':'deep'},{'path':('r',),'reason':'early'},{'path':('s',),'reason':'later-tie'}]}}
    assert first_divergence_path(synthetic)['x']=={'path':('r',),'reason':'early'}, 'earliest drift uses shortest manager path and stable encounter ties'
    known=dict(d.leaves);known['law']=replace(known['law'],status=Status.NEGATIVE)
    compared=audit_decomposition(replace(d,leaves=known),{'question':QUESTION,'states':{'build':'verified','contract':'verified'}})['rows'][1]
    assert (compared['hierarchy_state'],compared['canary_state'],compared['result'])==('negative','verified','canary-mismatch'), 'independent known canary disagreement retains both attributed states'
    with pytest.raises(ValueError,match='canary question mismatch'):audit_decomposition(d,canary_record('legal'))
    with pytest.raises(ValueError,match='unsupported canary obligation'):audit_decomposition(d,{'question':QUESTION,'states':{'extra':'verified'}})
    uncertain=audit_decomposition(d,{'question':QUESTION,'states':{'build':'verified','contract':'verified'}})['rows'][1]
    assert (uncertain['hierarchy_state'],uncertain['canary_state'],uncertain['result'])==('unknown','verified','unknown'), 'unknown hierarchy remains separately attributed beside a known canary'
    tied={'x':{'issues':[{'path':('z',),'reason':'first'},{'path':('a',),'reason':'second'}]}}
    assert first_divergence_path(tied)['x']=={'path':('z',),'reason':'first'}, 'equal depth drift keeps encounter order'
    partial=audit_decomposition(d,{'question':QUESTION,'states':{'build':'verified'}})['rows'][1]
    assert partial['canary_state'] is None and partial['hierarchy_state']=='unknown' and partial['result']=='unknown', 'absent canary evidence is not fabricated from hierarchy state'

@pytest.mark.skip('Part 4')
def test_provenance_tsv_rows():
    """Completed leaf evidence and manager audit rows retain different domain meaning."""
    from driftorg.stream import ProvenanceRows
    from driftorg.wire_support import encode_provenance,HEADER
    d=dossier_fixture();leaf=d.leaves['law']
    events=[{'kind':'leaf','task':'task\t一','path':('root','legal','law'),'original_obligation':'contract','local_obligation':'clause','leaf':leaf},
      {'kind':'branch','task':'task\t二','path':('root','legal'),'audit':{'obligation':'contract','result':'wrong-branch'},'local_obligation':'clause'},
      {'kind':'leaf','task':'task-3','path':('root','eng','fe'),'original_obligation':'build','local_obligation':'front','leaf':d.leaves['fe']}]
    class Source:
        def __init__(self):self.i=0;self.closed=0
        def __aiter__(self):return self
        async def __anext__(self):
            if self.i==len(events):raise StopAsyncIteration
            event=events[self.i];self.i+=1;return event
        async def aclose(self):self.closed+=1
    async def collect():
        source=Source();stream=encode_provenance(source,ProvenanceRows());chunks=[]
        chunks.append(await anext(stream))
        assert source.i==0, 'the supplied header precedes evidence consumption'
        chunks.append(await anext(stream))
        assert source.i==1, 'the supplied driver publishes each completed evidence record'
        async for chunk in stream:chunks.append(chunk)
        assert source.closed==1, 'the supplied driver closes the source once'
        return b''.join(chunks)
    payload=asyncio.run(collect());rows=list(csv.reader(io.StringIO(payload.decode('utf-8')),delimiter='\t'))
    assert rows[0]==list(HEADER), 'the supplied TSV codec emits the declared schema'
    assert rows[1:]==[['task\t一',json.dumps(['root','legal','law'],ensure_ascii=False,separators=(',',':')),'leaf','contract','unknown','law'],['task\t二',json.dumps(['root','legal'],ensure_ascii=False,separators=(',',':')),'branch','contract','wrong-branch',''],['task-3',json.dumps(['root','eng','fe'],ensure_ascii=False,separators=(',',':')),'leaf','build','verified','fe']], 'every row retains its own original obligation, complete path and evidence category'

@pytest.mark.skip('Part 5')
def test_nested_synthesis_explanations():
    """Typed nested explanations retain shared citation paths without repeated execution."""
    from driftorg.mapping import audit_decomposition
    from driftorg.explanation import merge_child_states,explain_synthesis
    from driftorg.models import Status
    d=dossier_fixture();audit=audit_decomposition(d,canary_record(QUESTION));report=explain_synthesis(d,audit)
    assert merge_child_states((Status.VERIFIED,Status.UNKNOWN)) is Status.UNKNOWN and merge_child_states(()) is Status.UNKNOWN, 'unknown evidence survives manager synthesis'
    assert merge_child_states((Status.VERIFIED,Status.NEGATIVE)) is Status.CONFLICT and merge_child_states((Status.MISSING,)) is Status.MISSING, 'missing and conflicting known evidence keep their declared states'
    assert report['tree']['state'] is Status.UNKNOWN and tuple(c['node_id'] for c in report['tree']['children'])==('eng','review','legal'), 'nested manager states reflect every declared branch'
    assert report['tree']['children'][0]['citations'][0]['path']==('root','eng','fe') and report['tree']['children'][1]['citations'][0]['path']==('root','review','fe'), 'shared leaf citations retain each distinct manager occurrence path'
    assert report['unique_leaf_ids']==('be','fe','law'), 'shared provenance does not invent extra worker executions'
    assert report['obligation_paths']['contract']==(('law',('root','legal','law'),'unknown'),) and len(report['obligation_paths']['build'])==3, 'original obligation evidence paths come from the semantic audit'
    changed=dict(d.nodes);changed['legal']=replace(d.nodes['legal'],available=False)
    missing=replace(d,nodes=changed);missing_audit=audit_decomposition(missing,canary_record(QUESTION))
    assert explain_synthesis(missing,missing_audit)['first_drift']['contract']=={'path':('root','legal'),'reason':'missing-branch'}, 'nested explanations retain the attributed first drift from the audit'
    missing_report=explain_synthesis(missing,missing_audit)
    assert missing_report['tree']['children'][2]['state'] is Status.MISSING and missing_report['tree']['state'] is Status.MISSING, 'unavailable manager remains missing through its ancestor synthesis'
    mixed_nodes=dict(d.nodes);mixed_nodes['root']=replace(d.nodes['root'],leaf_ids=('law',))
    mixed=replace(d,nodes=mixed_nodes);mixed_report=explain_synthesis(mixed,audit_decomposition(mixed,canary_record(QUESTION)))
    assert mixed_report['tree']['citations']==[{'leaf_id':'law','path':('root','law'),'state':Status.UNKNOWN}], 'managers retain direct citations alongside nested children'
