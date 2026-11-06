import asyncio
import json
import time
import pytest
from delegate.model import WorkUnit, Proof, Handoff
from delegate.plan import conflicts, delegation_plan
from delegate.evidence import EvidenceStore, _encode, _decode
from delegate.integrate import review_handoff, integrate
from delegate.stream import handoff_lines
from delegate.ownership import audit_ownership


def unit(name, paths=(), deps=(), read_only=False, owner=None):
    return WorkUnit(name, 'worker-' + name if owner is None else owner, tuple(paths), tuple(deps), 'test ' + name, read_only)


def receipt(name, changed=(), exit_code=0, output='passed', claimed=True, command=None):
    return Handoff(name, tuple(changed), Proof(command or 'test ' + name, exit_code, output), claimed)


def gate(code=0, output='all passed', command='full gate'):
    return Proof(command, code, output)


def collect(agen):
    async def drain():
        return [line async for line in agen]
    return asyncio.run(drain())


@pytest.mark.skip('Part 1')
def test_isolated_ownership_plan() -> None:
    """Normalize claims before reporting exclusive write ownership conflicts."""
    assert conflicts([unit('a', ('./app//api/',)), unit('b', ('app/api/routes.py',))]) == [('a', 'b', 'app/api', 'app/api/routes.py')], 'overlap reports must use normalized path components'
    assert conflicts([unit('a', ('app/api',)), unit('research', ('app/',), read_only=True)]) == [], 'read-only inspection does not claim write ownership'
    repeated = [unit('a', ('app/api',)), unit('a', ('app/api',)), unit('b', ('app/api/routes.py',))]
    assert conflicts(repeated) == [('a', 'b', 'app/api', 'app/api/routes.py')], 'duplicate ids do not duplicate an overlap finding'
    invalid = delegation_plan([unit('orphan', ('x',), owner='  ')])
    assert invalid['status'] == 'blocked' and invalid['missing_owner'] == ['orphan'], 'every work unit needs a nonblank accountable owner'
    duplicate = delegation_plan(repeated)
    assert duplicate['duplicate_ids'] == ['a'] and duplicate['waves'] == [], 'duplicate unit ids still block the plan'
    good = [unit('api', ('app/api',)), unit('web', ('app/web',)), unit('review', (), ('api', 'web'), True)]
    assert conflicts(good) == [], 'sibling claims are not overlapping writes'
    assert conflicts([unit('a', ('app/api',)), unit('b', ('app/apiary',))]) == [], 'a textual prefix is not a path-component prefix'
    assert delegation_plan(good)['waves'] == [['api', 'web'], ['review']], 'independent work precedes integration'
    bad_dep = delegation_plan([unit('x', ('x',), ('missing',))])
    assert bad_dep['status'] == 'blocked' and bad_dep['issues'] and bad_dep['waves'] == [], 'provided dependency validation remains intact'
    large = [unit(str(i), tuple(f'pkg/{i}/file{j}.py' for j in range(12))) for i in range(450)]
    start = time.perf_counter()
    result = conflicts(large)
    assert time.perf_counter() - start < 0.1, 'ownership checks must index unrelated path branches'
    assert result == [], 'indexing must retain the disjoint-claim result'


@pytest.mark.skip('Part 2')
def test_evidence_isolation_roundtrip(tmp_path) -> None:
    """Evidence files are created once and remain separate across arbitrary unit ids."""
    store = EvidenceStore(tmp_path)
    payload = bytes(range(256)) + b'\x00\xff\n'
    ids = ['api/一号', 'api%2F一号', 'worker: a b', 'z', 'A', '😀', 'h', '\x00']
    assert len({_encode(name).casefold() for name in ids}) == len(ids), 'opaque name encodings stay distinct after case folding'
    assert all(_decode(_encode(name)) == name for name in ids), 'provided name encoding is reversible for every opaque id'
    for index, name in enumerate(ids):
        store.write(name, 'proof / output.bin', payload + bytes([index]))
        store.write(name, 'empty', b'')
    store.write('h', 'proof', b'one')
    store.write('\x00', 'proof', b'two')
    assert store.read('h', 'proof') == b'one' and store.read('\x00', 'proof') == b'two', 'case-fold-sensitive opaque ids retain independent evidence bytes'
    store.write(ids[0], '😀', b'emoji')
    store.write(ids[0], 'trailing', b'\nline\n\n')
    assert store.read(ids[0], 'trailing') == b'\nline\n\n', 'trailing newline bytes remain evidence'
    for index, name in enumerate(ids):
        assert store.read(name, 'proof / output.bin') == payload + bytes([index]), 'evidence bytes round-trip exactly per isolated unit'
    with pytest.raises(FileExistsError):
        store.write(ids[0], 'proof / output.bin', b'replacement')
    with pytest.raises(FileExistsError):
        store.write(ids[0], 'empty', b'not empty')
    reopened = EvidenceStore(tmp_path)
    assert reopened.units() == sorted(ids), 'decode unit names before sorting their ids'
    assert reopened.read('h', 'proof') == b'one' and reopened.read('\x00', 'proof') == b'two', 'independent opaque-id evidence survives reopening'
    assert reopened.files(ids[0]) == ['empty', 'proof / output.bin', 'trailing', '😀'], 'evidence names are reversible and sorted'
    assert reopened.read(ids[0], 'empty') == b'' and reopened.read(ids[0], 'proof / output.bin') == payload + b'\x00', 'failed replacement preserves previous evidence'
    with pytest.raises(FileNotFoundError):
        reopened.read('missing', 'proof')


@pytest.mark.skip('Part 3')
def test_material_handoff_integration() -> None:
    """Integration reads material proofs, preserves dependency order and records conflicts."""
    units = [unit('a', ('app/a',)), unit('b', ('docs/b',)), unit('c', ('tests/c',), ('a', 'b'))]
    handoffs = [receipt('c', ('tests/c/check.py',)), receipt('b', ('docs/b/guide.md',)), receipt('a', ('app/a/main.py',))]
    files = ['tests/c/check.py', 'docs/b/guide.md', 'app/a/main.py']
    result = integrate(units, handoffs, files, gate(), 'full gate')
    assert result == {'status': 'ready', 'merge_order': ['a', 'b', 'c'], 'rejected': {}, 'decisions': [], 'diff_mismatch': [], 'gate_ok': True}, 'merge by dependency waves and id rather than receipt order'
    bad = [receipt('a', ('app/a/main.py',), exit_code=1, claimed=True), handoffs[1], handoffs[0]]
    result = integrate(units, bad, ['docs/b/guide.md'], gate(), 'full gate')
    assert result['rejected'] == {'a': 'proof', 'c': 'dependency'} and result['merge_order'] == ['b'], 'worker success summaries do not override proof failures or unblock dependants'
    assert review_handoff(units[0], receipt('wrong', ('escape',), exit_code=1)) == 'identity', 'handoff identity is checked before scope and proof'
    assert review_handoff(units[0], receipt('a', ('app/a/main.py',), exit_code=None)) == 'proof', 'missing proof exit status is not success'
    assert review_handoff(units[0], receipt('a', ('app/a/main.py',), claimed=False)) is None, 'material proof remains authoritative when the worker summary is negative'
    assert review_handoff(units[0], receipt('a', ('app/apiary/escape.py',))) == 'scope', 'changed files must remain under the assigned component prefix'
    assert review_handoff(units[0], receipt('a', ('app/a/main.py',), command='test other')) == 'proof', 'proof command must match the assignment'
    assert review_handoff(units[0], receipt('a', ('app/a/main.py',), output='  ')) == 'proof', 'read actual nonblank proof output'
    assert review_handoff(unit('r', ('app',), read_only=True), receipt('r', ('app/file.py',))) == 'scope', 'read-only workers cannot return writes'
    assert integrate(units, handoffs, [*files, 'secret.txt'], gate(), 'full gate')['diff_mismatch'] == ['secret.txt'], 'the final cross-unit diff catches hidden writes'
    assert integrate(units, handoffs, files[:-1], gate(), 'full gate')['status'] == 'blocked', 'missing proposed files also fail the final diff gate'
    assert not integrate(units, handoffs, files, gate(1), 'full gate')['gate_ok'], 'the full gate must pass after unit proofs'
    assert not integrate(units, handoffs, files, gate(output=' \n'), 'full gate')['gate_ok'], 'the full gate needs captured nonblank output'
    assert not integrate(units, handoffs, files, gate(command='different gate'), 'full gate')['gate_ok'], 'a different full-gate command is insufficient'
    shared = [unit('one', ('shared/api.py',)), unit('two', ('shared/api.py',)), unit('after', ('tests',), ('one', 'two'))]
    result = integrate(shared, [receipt('one', ('shared/api.py',)), receipt('two', ('shared/api.py',)), receipt('after', ('tests/test.py',))], [], gate(), 'full gate')
    assert result['decisions'] == [{'path': 'shared/api.py', 'units': ['one', 'two']}] and result['merge_order'] == [], 'conflicting shared interfaces require an explicit decision naming every unit'
    assert result['rejected'] == {'one': 'decision', 'two': 'decision', 'after': 'dependency'}, 'unresolved decisions block downstream merges'
    invalid_collision = integrate(shared, [receipt('one', ('shared/api.py',), exit_code=1), receipt('two', ('shared/api.py',)), receipt('after', ('tests/test.py',))], ['shared/api.py'], gate(), 'full gate')
    assert invalid_collision['decisions'] == [] and invalid_collision['merge_order'] == ['two'] and invalid_collision['rejected'] == {'one': 'proof', 'after': 'dependency'}, 'rejected proof material does not create a shared-interface decision'
    missing = integrate(units, handoffs[1:], ['app/a/main.py', 'docs/b/guide.md'], gate(), 'full gate')
    assert missing['rejected'] == {'c': 'missing'}, 'missing worker handoffs cannot disappear from the integration gate'


@pytest.mark.skip('Part 4')
def test_online_handoff_verdicts() -> None:
    """Interleaved worker receipts cross the dependency barrier before NDJSON output."""
    units = [unit('parent', ('app',)), unit('child', ('tests',), ('parent',)), unit('later', ('docs',))]
    events = [receipt('child', ('tests/x.py',)), receipt('parent', ('app/x.py',)), receipt('later', ('docs/x.md',))]
    pulled = []
    async def source():
        for event in events:
            pulled.append(event.unit)
            yield event
    async def probe():
        out = handoff_lines(units, source())
        first = await out.__anext__()
        assert first.endswith('\n') and first.count('\n') == 1, 'one complete JSON line per verdict'
        assert json.loads(first) == {'unit': 'parent', 'status': 'accepted', 'reason': None}, 'hold early child receipts until the parent verdict'
        assert pulled == ['child', 'parent'], 'emit as soon as the dependency barrier opens'
        assert json.loads(await out.__anext__()) == {'unit': 'child', 'status': 'accepted', 'reason': None} and len(pulled) == 2, 'resolve the current receipt wave before pulling future work'
        await out.aclose()
    asyncio.run(probe())
    assert pulled == ['child', 'parent'], 'cancelled consumers do not read future worker output'
    async def failed():
        yield receipt('child', ('tests/x.py',))
        yield receipt('parent', ('app/x.py',), exit_code=2)
    subset = units[:2]
    assert [json.loads(line) for line in collect(handoff_lines(subset, failed()))] == [{'unit': 'parent', 'status': 'rejected', 'reason': 'proof'}, {'unit': 'child', 'status': 'rejected', 'reason': 'dependency'}], 'rejected material proof blocks held dependants'
    async def outside_scope():
        yield receipt('child', ('tests/x.py',))
        yield receipt('parent', ('outside.py',))
    assert [json.loads(line) for line in collect(handoff_lines(subset, outside_scope()))] == [{'unit': 'parent', 'status': 'rejected', 'reason': 'scope'}, {'unit': 'child', 'status': 'rejected', 'reason': 'dependency'}], 'online integration reviews scope as well as proof exit'
    fork = [unit('a', ('a',)), unit('z', ('z',)), unit('join', ('join',), ('a', 'z'))]
    async def fork_receipts():
        yield receipt('join', ('join/x',))
        yield receipt('a', ('a/x',))
        yield receipt('z', ('z/x',))
    assert [json.loads(line)['unit'] for line in collect(handoff_lines(fork, fork_receipts()))] == ['a', 'z', 'join'], 'wait for all prerequisite verdicts before releasing a child'
    async def missing():
        yield receipt('child', ('tests/x.py',))
    assert [json.loads(line) for line in collect(handoff_lines(subset, missing()))] == [{'unit': 'parent', 'status': 'rejected', 'reason': 'missing'}, {'unit': 'child', 'status': 'rejected', 'reason': 'dependency'}], 'stream closure reports missing receipts before dependent rejection'
    async def unknown():
        yield receipt('unknown')
    rows = [json.loads(line) for line in collect(handoff_lines([], unknown()))]
    assert rows == [{'unit': 'unknown', 'status': 'rejected', 'reason': 'unknown'}], 'unknown workers are not silently dropped'


@pytest.mark.skip('Part 5')
def test_nested_ownership_and_parallelism() -> None:
    """All nested claimants remain visible and overlapping writers require serial order."""
    units = [unit('a', ('app/', 'app/api')), unit('b', ('./app//api/',), ('a',)), unit('c', ('app/api',), ('b',)), unit('d', ('app/api',)), unit('research', ('.',), read_only=True)]
    result = audit_ownership(units, ['app/api/routes.py', 'app/web.py', 'app2/file.py', 'app/api/routes.py'])
    assert result['owners'] == {'app/api/routes.py': ['a', 'b', 'c', 'd'], 'app/web.py': ['a'], 'app2/file.py': []}, 'retain every ancestor and exact claimant without duplicating one unit'
    assert result['unowned'] == ['app2/file.py'], 'unowned writes must remain visible'
    assert result['parallel_conflicts'] == [('app/api/routes.py', 'a', 'd'), ('app/api/routes.py', 'b', 'd'), ('app/api/routes.py', 'c', 'd')], 'only transitive dependency order permits shared write claims'
    assert audit_ownership(units[:3], ['app/api/x.py'])['parallel_conflicts'] == [], 'transitively ordered owners can reuse the same scope'
    assert audit_ownership([unit('root', ('.',)), unit('other', ('docs',), ('root',))], ['README.md', 'docs/a.md'])['owners'] == {'README.md': ['root'], 'docs/a.md': ['other', 'root']}, 'a repository-root claim participates in every nested owner query'
    assert audit_ownership([unit('z', ('shared',)), unit('a', ('shared',), ('z',))], ['shared/x'])['parallel_conflicts'] == [], 'serial dependency works in either lexical owner direction'
    assert audit_ownership([unit('single', ('app/api.py',))], ['app/api.py'])['owners'] == {'app/api.py': ['single']}, 'an exact file claim is an owner too'
    parallel = [unit(name, ('shared',)) for name in ('x', 'y', 'z')]
    assert audit_ownership(parallel, ['shared/file'])['parallel_conflicts'] == [('shared/file', 'x', 'y'), ('shared/file', 'x', 'z'), ('shared/file', 'y', 'z')], 'report every simultaneous owner pair on the same file'
    assert audit_ownership([unit('a', ('app/api',))], ['app/apiary/x.py'])['unowned'] == ['app/apiary/x.py'], 'prefix-tree lookup respects whole path components'
