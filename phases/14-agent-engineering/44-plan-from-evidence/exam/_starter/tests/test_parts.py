import asyncio
import time
import pytest
from evidplan.model import WorkItem, Event
from evidplan.plan import execution_waves, validate, plan_document
from evidplan.support import cycle_members
from evidplan.store import save_plan, load_plan, append_event, load_events
from evidplan.resume import resume_state
from evidplan.stream import progress_lines
from evidplan.split import split_proofs, unresolved_irreversibles


def item(name, deps=(), irreversible=False, resolvers=(), proof=None):
    return WorkItem(name, 'change ' + name, ('app/团队.py:10',), tuple(deps), proof or 'check ' + name, irreversible, tuple(resolvers))


def done(name, proof=None):
    return [Event('proof_ran', name, proof or 'check ' + name, 0), Event('item_done', name)]


def collect(agen):
    async def drain():
        return [line async for line in agen]
    return asyncio.run(drain())


@pytest.mark.skip('Part 1')
def test_validate_and_document() -> None:
    """Invalid plans stay blocked, independent findings remain visible, and exact cycle membership scales."""
    document = plan_document([item('orphan', ('missing',))])
    assert document['status'] == 'blocked' and document['waves'] == [], 'invalid plans never reach scheduling'
    cycle = [item('a', ('b',)), item('b', ('a',)), item('tail', ('b',))]
    assert validate(cycle) == ['cycle: a, b'], 'cycle findings name only actual cycle members'
    mixed = [*cycle, item('orphan', ('missing',))]
    findings = validate(mixed)
    assert 'unknown dependency: orphan: missing' in findings and 'cycle: a, b' in findings, 'unknown references must not hide a separate cycle'
    unsafe = [item('resolve'), item('deploy', irreversible=True, resolvers=('resolve',))]
    assert 'unresolved before deploy: resolve' in validate(unsafe), 'irreversible work waits for its resolver prerequisites'
    safe = [item('resolve'), item('other'), item('deploy', ('resolve', 'other'), True, ('resolve',))]
    assert validate(safe) == [], 'a resolver is a prerequisite, not a dominator of every diagram path'
    valid = [item('contract'), item('impl', ('contract',)), item('docs', ('contract',)), item('gate', ('impl', 'docs'))]
    assert execution_waves(valid) == [['contract'], ['docs', 'impl'], ['gate']], 'a wave contains exactly the currently unblocked items'
    assert execution_waves([item('a'), item('b', ('a', 'a'))]) == [['a'], ['b']], 'repeated dependency ids still mean one prerequisite'
    assert plan_document(cycle)['waves'] == [], 'never break a cycle by dropping dependency edges'
    assert plan_document([item('same'), item('same')])['status'] == 'blocked', 'duplicate item ids block the plan'
    assert validate([WorkItem('empty', 'change', (), (), ' ')]) == ['no evidence: empty', 'no proof: empty'], 'both evidence and proof are required'
    with pytest.raises(ValueError, match='unknown dependency'):
        execution_waves(mixed)
    chain = [item(str(i), (str(i-1),) if i else ()) for i in range(10000)]
    start = time.perf_counter()
    waves = execution_waves(chain)
    assert time.perf_counter() - start < 0.14, 'long plans must not rescan every remaining item per wave'
    assert waves == [[str(i)] for i in range(10000)], 'fast scheduling retains every dependency wave'

    multiple = [
        item('a', ('b', 'b')), item('b', ('a',)),
        item('self', ('self',)),
        item('x', ('y',)), item('y', ('z',)), item('z', ('x',)),
        item('tail', ('b',)), item('tail2', ('tail', 'x')),
        item('isolated'), item('unknown_only', ('missing',)),
    ]
    original = list(multiple)
    assert cycle_members(multiple) == ['a', 'b', 'self', 'x', 'y', 'z'], (
        'cycle membership keeps every disjoint cycle and self-loop, never downstream tails'
    )
    assert multiple == original, 'cycle membership does not rewrite the source plan'
    assert cycle_members([item('alone'), item('orphan', ('missing',))]) == [], (
        'unknown references and isolated vertices do not form a cycle'
    )
    assert validate(multiple) == [
        'unknown dependency: unknown_only: missing', 'cycle: a, b, self, x, y, z'
    ], 'independent findings keep every real cycle without claiming downstream work is cyclic'

    blocked = [item('a', ('b',)), item('b', ('a',))]
    blocked += [item(f't{i:05d}', (f't{i-1:05d}' if i else 'b',)) for i in range(4000)]
    start = time.perf_counter()
    members = cycle_members(blocked)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.1, 'cycle membership stays fast with long blocked tails'
    assert members == ['a', 'b'], 'a long blocked tail is not part of its prerequisite cycle'


@pytest.mark.skip('Part 2')
def test_progress_journal_roundtrip(tmp_path) -> None:
    """JSON source and repeated progress events survive reopening exactly."""
    plan = [WorkItem('contract', '保留 byte contract', ('docs/a b.md:3', 'a:4'), (), 'python -m check\n--strict'), item('deploy', ('contract',), True, ('contract',))]
    events = [Event('item_started', 'contract'), Event('artifact_changed', 'contract', path='docs/团队 rules.md'), Event('proof_ran', 'contract', plan[0].proof, -9, 'line 1\n第二行\n'), Event('proof_ran', 'contract', plan[0].proof, 0, 'ok'), Event('item_done', 'contract'), Event('item_done', 'contract')]
    save_plan(tmp_path, plan)
    assert load_plan(tmp_path) == plan, 'plan values round-trip exactly including tuple fields'
    assert load_events(tmp_path) == [], 'a missing journal means no events'
    for event in events:
        append_event(tmp_path, event)
    assert load_events(tmp_path) == events, 'journal order repeats summaries and integer exits round-trip exactly'
    assert (tmp_path / 'progress.jsonl').read_bytes().count(b'\n') == len(events), 'one physical JSON line per event'
    save_plan(tmp_path, [plan[0]])
    assert load_plan(tmp_path) == [plan[0]], 'saving the source replaces prior records'
    assert load_events(tmp_path) == events, 'source updates leave the journal intact'
    unicode_dir=tmp_path/'unicode'
    unicode_event=Event('proof_ran','contract','check Unicode',0,'left\u2028中间\u0085right')
    append_event(unicode_dir,unicode_event)
    assert load_events(unicode_dir)==[unicode_event], 'Unicode separators in event summaries remain data within one journal record'
    assert (unicode_dir/'progress.jsonl').read_bytes().count(b'\n')==1, 'Unicode string separators do not create physical JSONL records'


@pytest.mark.skip('Part 3')
def test_resume_after_artifact_changes() -> None:
    """Artifact revisions reopen an item and its downstream proofs across sessions."""
    plan = [item('contract'), item('impl', ('contract',)), item('docs', ('contract',)), item('gate', ('impl', 'docs'), True, ('contract',))]
    events = [*done('contract'), *done('impl'), *done('docs'), Event('approved', 'gate'), *done('gate')]
    assert resume_state(plan, events) == {'complete': ['contract', 'docs', 'gate', 'impl'], 'ready': [], 'next': None, 'blocked': {}}, 'fresh exact proofs close the dependency graph'
    assert resume_state(plan, [*events, Event('approved', 'gate')])['complete'] == ['contract', 'docs', 'gate', 'impl'], 'a repeated approval does not revoke the earlier permission'
    changed = [*events, Event('artifact_changed', 'contract', path='api.py')]
    assert resume_state(plan, changed) == {'complete': [], 'ready': ['contract'], 'next': 'contract', 'blocked': {'contract': 'fresh proof', 'impl': 'dependencies', 'docs': 'dependencies', 'gate': 'dependencies'}}, 'an upstream revision invalidates downstream completion'
    renewed = [*changed, *done('contract')]
    state = resume_state(plan, renewed)
    assert state['complete'] == ['contract'] and state['ready'] == ['docs', 'impl'] and state['next'] == 'docs', 'reproving an ancestor does not revive old downstream proofs'
    renewed += [*done('impl'), *done('docs')]
    assert resume_state(plan, renewed)['ready'] == ['gate'], 'integration waits for renewed branch proofs'
    assert resume_state(plan, [*renewed, *done('gate')])['complete'] == ['contract', 'docs', 'gate', 'impl'], 'reprove integration after ancestor changes'
    assert resume_state(plan[:2], [*done('contract'), *done('impl', 'check unrelated')])['complete'] == ['contract'], 'a different successful command is not the item proof'
    assert resume_state(plan[:2], done('impl'))['complete'] == [], 'a local proof cannot close work with unfinished prerequisites'
    failed_latest = [*done('contract'), Event('proof_ran', 'contract', 'check contract', 1), Event('item_done', 'contract')]
    assert resume_state(plan[:1], failed_latest)['complete'] == [], 'use the provided latest proof receipt'
    no_approval = [*done('contract'), *done('impl'), *done('docs'), *done('gate')]
    assert resume_state(plan, no_approval)['blocked']['gate'] == 'approval', 'irreversible work requires approval'
    assert 'gate' not in resume_state(plan, [*no_approval, Event('approved', 'gate')])['complete'], 'approval after done cannot retroactively close the item'
    assert resume_state([item('deploy', irreversible=True)], [])['next'] is None, 'approval blockage produces no runnable item'
    assert resume_state(plan[:1], [Event('item_done', 'contract'), Event('proof_ran', 'contract', 'check contract', 0)])['complete'] == [], 'done must follow its successful proof'


@pytest.mark.skip('Part 4')
def test_online_progress_markdown() -> None:
    """Interleaved worker receipts update a resumable Markdown view immediately."""
    plan = [item('a'), item('b', ('a',))]
    existing = [*done('a'), Event('proof_ran', 'b', 'check b', 0)]
    events = [Event('item_done', 'b'), Event('artifact_changed', 'a', path='a.py'), Event('item_started', 'a')]
    pulled = []
    async def source():
        for event in events:
            pulled.append(event)
            yield event
    async def probe():
        output = progress_lines(plan, existing, source())
        assert await output.__anext__() == '- [x] b — proof: check b (exit 0)\n', 'completed work emits the exact proof line'
        assert len(pulled) == 1, 'emit before pulling the next receipt'
        assert await output.__anext__() == '- [ ] a — blocked by fresh proof\n', 'artifact changes immediately reopen the view'
        assert await output.__anext__() == '- [ ] b — blocked by dependencies\n' and len(pulled) == 2, 'emit all changed lines before reading another event'
        await output.aclose()
    asyncio.run(probe())
    async def empty():
        if False:
            yield Event('item_started', 'a')
    assert collect(progress_lines(plan, [*existing, *events[:2]], empty())) == [], 'resume initializes progress without duplicated output'
    async def repeated():
        yield Event('item_done', 'b')
        yield Event('item_done', 'b')
    assert collect(progress_lines(plan, existing, repeated())) == ['- [x] b — proof: check b (exit 0)\n'], 'unchanged receipts do not repeat checklist lines'
    assert len(pulled) == 2, 'cancellation leaves future input unconsumed'
    async def reopened():
        yield Event('artifact_changed', 'a', path='a.py')
    assert collect(progress_lines(list(reversed(plan)), [*done('a'), *done('b')], reopened())) == ['- [ ] a — blocked by fresh proof\n', '- [ ] b — blocked by dependencies\n'], 'changed lines follow item id order regardless of source-plan order'


@pytest.mark.skip('Part 5')
def test_split_proofs_and_resolver_dependencies() -> None:
    """Split proof obligations without weakening irreversible prerequisites."""
    plan = [item('contract'), item('impl', ('contract',)), item('docs', ('contract',)), item('release', ('impl', 'docs', 'impl'), True, ('impl',))]
    split = split_proofs(plan, {'impl': ('unit proof', 'wire proof')})
    assert [node.id for node in split] == ['contract', 'impl::1', 'impl::2', 'docs', 'release'], 'split ids follow proof order'
    assert [node.proof for node in split[1:3]] == ['unit proof', 'wire proof'], 'one exact proof per replacement'
    assert all(node.depends_on == ('contract',) and node.evidence == plan[1].evidence and node.change == plan[1].change for node in split[1:3]), 'split items inherit prerequisites and receipts'
    assert split[-1].depends_on == ('impl::1', 'impl::2', 'docs') and split[-1].resolvers == ('impl::1', 'impl::2'), 'expand downstream deps and resolvers to all replacement ids once'
    assert split[-1].irreversible, 'retain irreversible annotations'
    overridden = split_proofs(plan, {'impl': ('new exact proof',)})
    assert overridden[1].id == 'impl' and overridden[1].proof == 'new exact proof', 'a single explicit proof replaces the command while keeping the item id'
    assert unresolved_irreversibles(split) == {}, 'expanded resolver dependencies are safe'
    split_release = split_proofs(plan, {'release': ('gate one', 'gate two')})
    assert all(node.irreversible and node.resolvers == ('impl',) for node in split_release[-2:]), 'each split obligation retains irreversible metadata'
    branched = [item('resolve'), item('docs'), item('safe', ('resolve', 'docs'), True, ('resolve',)), item('bad', ('docs',), True, ('resolve',)), item('also-bad', (), True, ('resolve', 'docs'))]
    assert unresolved_irreversibles(branched) == {'bad': ['resolve'], 'also-bad': ['docs', 'resolve']}, 'check all irreversible items by prerequisite ancestry'
    assert unresolved_irreversibles([item('resolve'), item('bridge', ('resolve',)), item('release', ('bridge',), True, ('resolve',))]) == {}, 'transitive resolver prerequisites are sufficient'
    with pytest.raises(ValueError, match='collision'):
        split_proofs([item('a'), item('a::1')], {'a': ('p', 'q')})
    with pytest.raises(ValueError, match='no proof'):
        split_proofs(plan, {'impl': ()})
