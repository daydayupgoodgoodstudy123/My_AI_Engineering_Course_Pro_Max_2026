from . import add, ok, bad

add("environment", "开发环境探针汇总", "environment_report(probes, required)",
    "probes maps probe names to {'exit_code':int,'output':str}. For each sorted unique required name, mark missing if absent or failed unless exit_code==0 and output.strip() is nonempty. Return {'ready':bool,'missing':sorted names,'failed':sorted names}. No command is run.",
    """missing=sorted(set(required)-set(probes));failed=sorted(n for n in set(required)&set(probes) if probes[n]['exit_code']!=0 or not probes[n]['output'].strip())
return {'ready':not missing and not failed,'missing':missing,'failed':failed}""",
    [ok(({'python':{'exit_code':0,'output':'3.12'}},['python']),{'ready':True,'missing':[],'failed':[]}),ok(({},['python']),{'ready':False,'missing':['python'],'failed':[]}),ok(({'x':{'exit_code':1,'output':'bad'}},['x']),{'ready':False,'missing':[],'failed':['x']}),ok(({},[]),{'ready':True,'missing':[],'failed':[]}),ok(({'x':{'exit_code':0,'output':' '}},['x']),{'ready':False,'missing':[],'failed':['x']}),ok(({},['b','a','a']),{'ready':False,'missing':['a','b'],'failed':[]})])

add("git_plan", "Git 变更分类", "git_plan(changes)",
    "Each change has path and status among added,modified,deleted. Return dict status->sorted paths for all three categories. Duplicate paths or unknown status raises ValueError. This function plans only; no git command executes.",
    """result={s:[] for s in ('added','modified','deleted')};seen=set()
for c in changes:
    if c['status'] not in result or c['path'] in seen:raise ValueError('changes')
    seen.add(c['path']);result[c['status']].append(c['path'])
return {s:sorted(paths) for s,paths in result.items()}""",
    [ok(([{'path':'a','status':'added'}],),{'added':['a'],'modified':[],'deleted':[]}),ok(([],),{'added':[],'modified':[],'deleted':[]}),ok(([{'path':'z','status':'modified'},{'path':'a','status':'modified'}],),{'added':[],'modified':['a','z'],'deleted':[]}),bad(([{'path':'a','status':'unknown'}],)),bad(([{'path':'a','status':'added'},{'path':'a','status':'deleted'}],)),ok(([{'path':'a b','status':'deleted'}],),{'added':[],'modified':[],'deleted':['a b']})])

add("split", "可复现数据划分", "split_records(records, train_count, validation_count)",
    "Preserve record order. Counts are exact nonnegative ints and their sum cannot exceed input length. Return {'train':prefix,'validation':next records,'test':remainder}. Return copies of list slices; invalid counts raise ValueError.",
    """if any(type(x) is not int or x<0 for x in (train_count,validation_count)) or train_count+validation_count>len(records):raise ValueError('split')
return {'train':records[:train_count],'validation':records[train_count:train_count+validation_count],'test':records[train_count+validation_count:]}""",
    [ok(([1,2,3,4],2,1),{'train':[1,2],'validation':[3],'test':[4]}),ok(([],0,0),{'train':[],'validation':[],'test':[]}),ok(([1],0,0),{'train':[],'validation':[],'test':[1]}),ok(([1],1,0),{'train':[1],'validation':[],'test':[]}),bad(([1],1,1)),bad(([1],True,0))])

add("path", "词法路径包含边界", "contained_path(root, relative)",
    "Use POSIX lexical paths only: root must be absolute, relative must not be absolute. Normalize '.' and '..'; reject any attempt to pop above root with ValueError. Return normalized absolute path string. No filesystem or symlink checks are made. root is already normalized without trailing slash except '/'.",
    """if not root.startswith('/') or relative.startswith('/'):raise ValueError('path')
parts=[]
for part in relative.split('/'):
    if part in ('','.'):continue
    if part=='..':
        if not parts:raise ValueError('escape')
        parts.pop()
    else:parts.append(part)
return root.rstrip('/')+('/'+'/'.join(parts) if parts else '') or '/'""",
    [ok(('/work','a/../b'),'/work/b'),ok(('/work','.'),'/work'),ok(('/','a'),'/a'),bad(('/work','../x')),bad(('/work','/secret')),ok(('/work','a b'),' /work/a b'.strip())])

add("argv", "精确命令策略", "command_review(argv, allowlist)",
    "Return True only for a nonempty list of strings whose entire sequence exactly matches one allowlist list. Reject shell strings, non-string entries and extra flags by returning False. This is a pure comparison; execute nothing.",
    "return isinstance(argv,list) and bool(argv) and all(isinstance(x,str) for x in argv) and argv in allowlist",
    [ok((['python3','check.py'],[['python3','check.py']]),True),ok((['python3','check.py','--upload'],[['python3','check.py']]),False),ok(('python3 check.py',[['python3','check.py']]),False),ok(([],[[]]),False),ok(([1],[[1]]),False),ok((['x'],[]),False)])

add("versions", "版本兼容判断", "compatible_version(version, minimum, maximum_major)",
    "version and minimum are strings of exactly three nonnegative decimal components separated by dots. Reject malformed strings with ValueError. Return version tuple>=minimum tuple and version major<=maximum_major; maximum_major is an exact nonnegative integer or raises ValueError.",
    r"""if type(maximum_major) is not int or maximum_major<0:raise ValueError('major')
def parse(s):
    if not isinstance(s,str) or re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',s) is None:raise ValueError('version')
    return tuple(int(x) for x in s.split('.'))
v,m=parse(version),parse(minimum)
return v>=m and v[0]<=maximum_major""",
    [ok(('3.12.1','3.10.0',3),True),ok(('3.9.9','3.10.0',3),False),ok(('4.0.0','3.10.0',3),False),ok(('3.10.0','3.10.0',3),True),bad(('3.10','3.0.0',3)),bad(('3.1.0-beta','3.0.0',3))])

add("manifest", "内容指纹与漂移", "manifest(files)",
    "files maps relative path strings to text. Return path->SHA256 hex of UTF-8 content, with keys inserted in sorted path order. Reject absolute paths or any '..' path component with ValueError. Do not read disk.",
    """if any(p.startswith('/') or '..' in p.split('/') for p in files):raise ValueError('path')
return {p:hashlib.sha256(files[p].encode()).hexdigest() for p in sorted(files)}""",
    [ok(({'a':''},),{'a':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}),ok(({'a':'abc'},),{'a':'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'}),ok(({},),{}),bad(({'../a':''},)),bad(({'/a':''},)),ok(({'a/b':''},),{'a/b':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'})])

add("config", "配置合同校验", "validate_config(config, required, optional)",
    "required and optional are field-name lists. Return {'missing':sorted required absent keys,'unknown':sorted config keys outside required+optional,'valid':no findings}. Values are deliberately not type-checked here. Empty config can be valid.",
    """missing=sorted(set(required)-set(config));unknown=sorted(set(config)-set(required)-set(optional))
return {'missing':missing,'unknown':unknown,'valid':not missing and not unknown}""",
    [ok(({'x':1},['x'],[]),{'missing':[],'unknown':[],'valid':True}),ok(({},['x'],[]),{'missing':['x'],'unknown':[],'valid':False}),ok(({'x':1},[],[]),{'missing':[],'unknown':['x'],'valid':False}),ok(({},[],[]),{'missing':[],'unknown':[],'valid':True}),ok(({'x':None},[],['x']),{'missing':[],'unknown':[],'valid':True}),ok(({'z':1},['b','a'],[]),{'missing':['a','b'],'unknown':['z'],'valid':False})])

add("profile", "耗时聚合", "profile(events)",
    "Events have name,start,end numeric milliseconds. Reject end<start with ValueError. Return name->{'count','total','max'} aggregated over individual durations. Empty input -> {}; overlapping durations are summed, not wall-clock latency.",
    """result={}
for e in events:
    d=e['end']-e['start']
    if d<0:raise ValueError('time')
    r=result.setdefault(e['name'],{'count':0,'total':0,'max':0});r['count']+=1;r['total']+=d;r['max']=max(r['max'],d)
return result""",
    [ok(([{'name':'x','start':0,'end':2},{'name':'x','start':1,'end':4}],),{'x':{'count':2,'total':5,'max':3}}),ok(([],),{}),ok(([{'name':'x','start':1,'end':1}],),{'x':{'count':1,'total':0,'max':0}}),bad(([{'name':'x','start':2,'end':1}],)),ok(([{'name':'a','start':0,'end':1},{'name':'b','start':0,'end':2}],),{'a':{'count':1,'total':1,'max':1},'b':{'count':1,'total':2,'max':2}}),ok(([{'name':'x','start':-1,'end':0}],),{'x':{'count':1,'total':1,'max':1}})])
