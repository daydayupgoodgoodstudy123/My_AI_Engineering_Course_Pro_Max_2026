import asyncio
import math
import struct
from time import perf_counter
import pytest
from adapterforge.service import AdapterService
from adapterforge.models import Adapter
from adapterforge.archive import AdapterArchive,encode_adapter,decode_adapter
from adapterforge.quant import quantize,dequantize,pack_codes,unpack_codes
from adapterforge.stream import stream_modules
from adapterforge.wire import parse_frames
from adapterforge.tree_models import Linear,Module,Wrapped,leaves
from adapterforge.tree import inject,parameter_report,merge_tree

def sample(path="model.层.q_proj"):
    return Adapter(path,((1.0000000000000002,-0.0),(1e-200,-2.25),(3.5,4.0)),((0.0,-0.0,1.25,2.0),(2.5,1e-200,-1.0,0.0)),1.0000000000000002)

def bits(artifact):
    values=[artifact.alpha]+[v for row in artifact.A for v in row]+[v for row in artifact.B for v in row]
    return artifact.path,len(artifact.A),artifact.rank,len(artifact.B[0]),struct.pack(">"+"d"*len(values),*values)

def workload():
    ni,no,nr=384,512,192
    base=tuple(tuple(((i+j)%7-3)/32 for j in range(no)) for i in range(ni))
    A=tuple(tuple(((i+2*j)%11-5)/16 for j in range(nr)) for i in range(ni))
    B=tuple(tuple(((3*i+j)%13-6)/32 for j in range(no)) for i in range(nr))
    vector=tuple((i%5-2)/8 for i in range(ni))
    service=AdapterService(base,tuple((j%3)/16 for j in range(no)),{"path":"block.q_proj","A":A,"B":B,"alpha":96.0})
    return service,vector

@pytest.mark.skip("Part 1")
def test_adapter_forward_and_merge():
    """Load row-vector factors, preserve scaling/bias, merge once and evaluate a wide adapter."""
    base=((1,0,2,1),(0,1,-1,-2),(2,1,0,3));bias=(.25,-.5,.75,1.0)
    record={"path":"block.q_proj","A":((1,2),(3,4),(5,6)),"B":((1,0,-1,2),(0,2,1,-1)),"alpha":3}
    service=AdapterService(base,bias,record)
    output=service.forward((1,0,-1))
    assert output==pytest.approx((-6.75,-13.5,2.75,-7.0)), "a rectangular row-vector adapter retains its declared alpha/rank residual and base bias"
    before=service.forward((2,-1,.5));service.merge()
    assert service.forward((2,-1,.5))==pytest.approx(before), "merged and separate adapter evaluation agree for the same input"
    merged=service.base;service.merge()
    assert service.base==merged and service.forward((2,-1,.5))==pytest.approx(before), "merging an already merged adapter preserves the complete output"
    zero=AdapterService(base,bias,{**record,"B":((0,0,0,0),(0,0,0,0))})
    assert zero.forward((1,0,-1))==(-.75,-1.5,2.75,-1.0), "a valid zero residual still evaluates its nonzero frozen base and bias"
    inactive=AdapterService(base,bias,{**record,"alpha":0.0})
    negative=AdapterService(base,bias,{**record,"alpha":-3.0})
    assert inactive.forward((1,0,-1))==(-.75,-1.5,2.75,-1.0) and negative.forward((1,0,-1))==pytest.approx((5.25,10.5,2.75,5.0)), "finite zero and negative alpha retain their declared residual scale"
    wide,vector=workload();started=perf_counter();result=wide.forward(vector);elapsed=perf_counter()-started
    assert elapsed<0.1, "wide adapter requests should stay responsive"
    assert len(result)==512 and all(math.isfinite(v) for v in result) and sum(abs(v) for v in result)>1, "wide evaluation retains the complete nonzero base-plus-adapter output"
    for j in (0,127,511):
        expected=sum(vector[i]*wide.base[i][j] for i in range(len(vector)))+wide.bias[j]+wide.adapter.alpha/wide.adapter.rank*sum(vector[i]*wide.adapter.A[i][k]*wide.adapter.B[k][j] for i in range(len(vector)) for k in range(wide.adapter.rank))
        assert result[j]==pytest.approx(expected,rel=1e-12,abs=1e-12), "wide output coordinates retain the declared complete adapter algebra"
    changed=wide.forward(tuple(-v for v in vector))
    assert all(a+b==pytest.approx(2*bias) for a,b,bias in zip(result,changed,wide.bias)), "different vectors receive their own adapter residual and the original base bias"
    assert len(record["A"])==3 and record["B"][0]==(1,0,-1,2), "forward and merge leave the caller's adapter record unchanged"

@pytest.mark.skip("Part 2")
def test_binary_adapter_archive(tmp_path):
    """Reopen a named rectangular adapter with exact binary64 values and complete framing."""
    original=sample();store=AdapterArchive(tmp_path/"adapter.bin");store.save(original)
    restored=AdapterArchive(store.path).load()
    assert bits(restored)==bits(original), "archive reopening preserves module identity, distinct factor shapes and every binary64 bit"
    assert encode_adapter(restored)==store.path.read_bytes(), "the complete adapter archive has a deterministic exact representation"
    zero=Adapter("zero.B",((1.,),(2.,)),((0.,-0.),),-0.0);store.save(zero)
    assert bits(store.load())==bits(zero), "zero-initialized B and signed-zero alpha remain valid persisted adapter values"
    raw=encode_adapter(original)
    for damaged in (raw[:9],raw[:-1],raw+b"x",b"BAD!"+raw[4:]):
        with pytest.raises(ValueError):decode_adapter(damaged)
    nm=struct.unpack_from(">I",raw,4)[0]
    broken=bytearray(raw);struct.pack_into(">I",broken,8,8)
    with pytest.raises(ValueError):decode_adapter(bytes(broken))
    assert nm==len(raw[12:12+nm]) and len(raw)>12+nm, "named metadata and all numeric factor payload bytes belong to the same archive"

@pytest.mark.skip("Part 3")
def test_uniform_int4_blocks():
    """Quantize independent padded blocks with course scales, signed nibbles and original shape."""
    codes=(-8,-7,-1,0,1,6,7)
    assert pack_codes(codes)==bytes.fromhex("89f01670") and unpack_codes(pack_codes(codes),7)==codes, "packed teaching codes retain signed values and high-nibble-first ordering"
    with pytest.raises(ValueError):pack_codes([8])
    q=quantize(((0.,0.,0.,0.,14.),(-14.,2.,-2.,1.,-1.)),4)
    assert q.shape==(2,5) and q.pad==2 and q.scales==pytest.approx((1e-8,2.,1/7)), "each padded block retains its own absmax scale and original matrix extent"
    assert unpack_codes(q.payload,12)==(0,0,0,0,7,-7,1,-1,7,-7,0,0), "codes use each block's scale rather than a shared tensor scale"
    restored=dequantize(q)
    assert len(restored)==2 and all(len(row)==5 for row in restored) and restored[1][-1]==pytest.approx(-1), "dequantization removes only numerical padding and restores the original shape"
    ties=quantize(((14.,1.,-1.,3.,5.),),5)
    assert ties.pad==0, "a complete last block is retained when no padding was added"
    assert unpack_codes(ties.payload,5)==(7,0,0,2,2), "halfway values follow the declared ties-to-even teaching quantizer"
    exact=quantize(((7.,-7.,0.,1.),),4)
    assert exact.pad==0 and dequantize(exact)==((7.,-7.,0.,1.),), "a complete last block is retained when no padding was added"
    zeros=quantize(((0.,0.,0.),),3)
    assert zeros.scales==(1e-8,) and dequantize(zeros)==((0.,0.,0.),), "all-zero blocks have a finite positive scale and reconstruct as zero"
    for size in (0,-1,True):
        with pytest.raises(ValueError):quantize(((1.,),),size)
    negative_only=quantize(((-7.,-1.),),2)
    assert negative_only.scales==(1.,) and unpack_codes(negative_only.payload,2)==(-7,-1) and dequantize(negative_only)==((-7.,-1.),), "an all-negative block retains its own magnitude scale and signed coordinates"

@pytest.mark.skip("Part 4")
def test_incremental_module_frames():
    """Publish each completed module's own adapter snapshot before reading future modules."""
    async def exercise():
        first=sample("encoder.层.q_proj");second=Adapter("decoder.μ.v_proj",((2.,),(3.,)),((0.,-0.,0.),),7.25)
        state={"pulled":0,"closed":False}
        async def source():
            try:
                for adapter in (first,second):
                    state["pulled"]+=1;yield adapter
            finally:state["closed"]=True
        stream=stream_modules(source());one=await stream.__anext__()
        records=parse_frames(one)
        assert state["pulled"]==1 and len(records)==1 and records[0][0]==first.path and bits(decode_adapter(records[0][1]))==bits(first), "the completed first module is observable before a future module is pulled"
        two=await stream.__anext__();both=parse_frames(one+two)
        assert [path for path,_ in both]==[first.path,second.path] and [bits(decode_adapter(payload)) for _,payload in both]==[bits(first),bits(second)], "each frame retains its own path, rank, factors and alpha including a valid zero B"
        with pytest.raises(StopAsyncIteration):await stream.__anext__()
        assert state=={"pulled":2,"closed":True}, "normal exhaustion closes the module source"
        state.update(pulled=0,closed=False);early=stream_modules(source());await early.__anext__();await early.aclose()
        assert state=={"pulled":1,"closed":True}, "client closure preserves the boundary before the next module"
        async def empty():
            if False:yield first
        assert [piece async for piece in stream_modules(empty())]==[], "an empty module source emits no fabricated artifact"
    asyncio.run(exercise())

@pytest.mark.skip("Part 5")
def test_targeted_module_graph():
    """Inject exact targets across aliases, count physical parameters and merge each wrapper once."""
    shared=Linear(((1.,2.),(3.,4.),(5.,6.)),(.25,-.5))
    other=Linear(((1.,),(2.,)),(.75,));near=Linear(((3.,),),(.5,))
    root=Module({"encoder":Module({"q_proj":shared,"q_projection":near}),"decoder":Module({"alias":shared,"k_proj":other})})
    calls=[]
    def factory(path,ni,no,rank,alpha):
        calls.append(path)
        return Adapter(path,tuple((float(i+1),) for i in range(ni)),(tuple(float(2*(j+1)) for j in range(no)),),alpha)
    selected=inject(root,{"encoder.q_proj"},1,2.,factory)
    assert list(selected)==["encoder.q_proj","decoder.alias"] and len(calls)==1 and selected["encoder.q_proj"] is selected["decoder.alias"], "a selected physical module is wrapped once and every alias preserves shared identity"
    assert isinstance(root.children["encoder"].children["q_projection"],Linear) and isinstance(root.children["decoder"].children["k_proj"],Linear), "exact target selection does not wrap a containing substring or an unrelated leaf"
    assert shared.frozen and other.frozen and near.frozen, "all physical base layers remain frozen after adapter injection"
    assert parameter_report(root)=={"total":18,"trainable":5,"frozen":13,"aliases":["encoder.q_proj","decoder.alias"]}, "parameter counts distinguish physical base and adapter storage from repeated module paths"
    original=selected["encoder.q_proj"]
    again=inject(root,{"q_proj"},1,2.,factory)
    assert len(calls)==1 and again["encoder.q_proj"] is original and again["decoder.alias"] is original, "an existing wrapper remains intact during a repeated graph injection"
    report=merge_tree(root)
    assert root.children["encoder"].children["q_proj"] is shared and root.children["decoder"].children["alias"] is shared and shared.weight==((5.,10.),(11.,20.),(17.,30.)) and shared.bias==(.25,-.5), "merging replaces every wrapper alias with the same once-updated frozen base"
    assert report=={"total":13,"trainable":0,"frozen":13,"aliases":[]} and merge_tree(root)==report, "a merged graph has no adapter parameters and a second merge preserves its structure"
    fresh=Module({"nested":Module({"q_proj":Linear(((1.,),),(.0,))}),"q_projection":Linear(((2.,),),(.0,))})
    assert list(inject(fresh,{"q_proj"},1,2.,factory))==["nested.q_proj"], "a leaf-name target selects the exact suffix at any nesting depth"
    left=Linear(((1.,),),(.25,));right=Linear(((2.,),(3.,)),(-.5,))
    repeated=Module({"left":Module({"q_proj":left}),"right":Module({"q_proj":right})})
    both=inject(repeated,{"q_proj"},1,2.,factory)
    assert list(both)==["left.q_proj","right.q_proj"] and both["left.q_proj"] is not both["right.q_proj"] and both["left.q_proj"].base is left and both["right.q_proj"].base is right, "distinct physical modules with the same selected leaf name each retain their own adapter"
    direct=Linear(((4.,),),(.75,));nested=Linear(((5.,),),(-.25,))
    mixed=Module({"q_proj":direct,"block":Module({"q_proj":nested})})
    installed=inject(mixed,{"q_proj"},1,2.,factory)
    assert list(installed)==["q_proj","block.q_proj"] and mixed.children["q_proj"] is installed["q_proj"] and mixed.children["block"].children["q_proj"] is installed["block.q_proj"], "a direct root child and a nested matching leaf are both installed at their declared paths"
    manual_base=Linear(((1.,),),(.0,))
    manual_adapter=Adapter("q_proj",((1.,),),((0.,),),2.)
    manual_wrapper=Wrapped(manual_base,manual_adapter);manual_root=Module({"q_proj":manual_wrapper})
    retained=inject(manual_root,{"q_proj"},1,2.,factory)
    assert manual_base.frozen and retained["q_proj"] is manual_wrapper and manual_root.children["q_proj"] is manual_wrapper and manual_wrapper.base is manual_base and manual_wrapper.adapter is manual_adapter, "an existing wrapper keeps its original base and adapter identities while freezing its base"
